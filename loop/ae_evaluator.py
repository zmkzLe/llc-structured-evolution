"""Score one AlphaEvolve candidate: a packed structure description and its C++.

AlphaEvolve's skydiscover adapter hands an evaluator a single file, but a
ChampSim replacement module is a .cc and a .h. A candidate is therefore one
file carrying three sections, and this splits them back out:

    ===== STRUCTURE_DESCRIPTION =====
    <structure description YAML>
    ===== HEADER =====
    <module>.h
    ===== SOURCE =====
    <module>.cc

The structure description meets the closed schema validator first, which costs
milliseconds and rejects a malformed design before it costs a build and the
simulations. Survivors are built and run over the explore group; the score is
the geometric mean of IPC relative to Mockingjay, the seed, so it means the same
thing here, on the held-out group later, and in the yaml arm this one is
compared against.

Every scored candidate leaves a line in records.jsonl and its C++ in store/,
which is the whole interface heldout_validator.py reads: it takes each design
that sets a new top training score and re-runs it on the held-out traces.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from chia_llc_loop import (  # noqa: E402
    EXPLORE,
    WARMUP,
    SIM,
    CactiError,
    absent,
    build,
    cacti_metrics,
    structure_description_is_legal,
    run_traces,
)

from candidate import (  # noqa: E402
    HEADER,
    MODULE,
    SOURCE,
    STRUCTURE_DESCRIPTION,
    module_sources,
)

# Built from the same three names the prompt tells the model to write, so the
# reader and the instruction cannot drift apart.
_SECTION = re.compile(
    rf"^=====\s*({STRUCTURE_DESCRIPTION}|{HEADER}|{SOURCE})\s*=====\s*$", re.M)


def split_candidate(text: str) -> dict[str, str]:
    """Pull the three sections out of a packed candidate."""
    parts, marks = {}, list(_SECTION.finditer(text))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        parts[m.group(1)] = text[m.end():end].strip("\n")
    return parts


# The run directory: store/ and records.jsonl, the two things the validator
# reads. A3_RUN_DIR is the same variable the yaml evaluator takes, so a launch
# script sets it once for either arm.
RUN = Path(os.environ.get("A3_RUN_DIR") or Path.home() / "ae_run")
STORE, RECORDS = RUN / "store", RUN / "records.jsonl"


def design_id(header: str, source: str) -> str:
    """A candidate's identity is its C++: the same policy proposed twice is one
    design, and the validator re-runs it once."""
    return hashlib.sha256(f"{header}\n{source}".encode()).hexdigest()[:12]


def reference_ipcs() -> dict | None:
    """Mockingjay's IPC per trace, from the first scored record of this run.

    Every score is a ratio against the seed, so the seed reads exactly 1.0 and
    the number means the same thing as in the yaml arm. None means this
    candidate is the first: it is the seed and defines the reference.
    """
    if not RECORDS.exists():
        return None
    for line in RECORDS.read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("status") == "ok" and rec.get("ipc") \
                and rec.get("lengths") == [WARMUP, SIM] and rec.get("traces") == EXPLORE:
            return rec["ipc"]
    return None


def vs_mockingjay(ipcs: dict, reference: dict) -> tuple[float, dict]:
    """The score and the ratio per trace, against Mockingjay on the same trace.

    Copied from design_evaluator.vs_mockingjay so both arms compute the number
    the same way; a difference here would be invisible and would void the
    comparison the two arms exist to make.
    """
    ratios = {s: ipcs[s] / reference[s] for s in EXPLORE}
    return math.exp(sum(math.log(r) for r in ratios.values()) / len(ratios)), ratios


def remember(did: str, sources: dict[str, str], metrics: dict) -> None:
    """One line in records.jsonl, and the design in store/<id>/ for the validator
    to rebuild from under its own module name.

    Refused candidates are recorded too, without a store entry: they cost a
    proposal each, and the share of them is how the arms' efficiency is compared.
    """
    if sources:
        design = STORE / did
        design.mkdir(parents=True, exist_ok=True)
        for name, text in sources.items():
            path = design / name
            if not path.exists():
                path.write_text(text)
    RECORDS.parent.mkdir(parents=True, exist_ok=True)
    with RECORDS.open("a") as fh:
        fh.write(json.dumps({"id": did, "at": round(time.time(), 1),
                             "lengths": [WARMUP, SIM], "traces": EXPLORE,
                             **metrics}) + "\n")


def refused(metrics: dict, parts: dict | None = None) -> dict:
    """Record a candidate that never reached a score, and hand it back unchanged."""
    text = "".join((parts or {}).get(k, "") for k in (STRUCTURE_DESCRIPTION, HEADER, SOURCE))
    remember(hashlib.sha256(text.encode()).hexdigest()[:12], {}, metrics)
    return metrics


def evaluate(program_path: str) -> dict:
    """The contract skydiscover's AlphaEvolve adapter calls."""
    text = Path(program_path).read_text()
    parts = split_candidate(text)

    sections = (STRUCTURE_DESCRIPTION, HEADER, SOURCE)
    missing = [s for s in sections if not parts.get(s)]
    if missing:
        return refused({"combined_score": 0.0, "status": "malformed",
                        "error": f"candidate is missing section(s): {', '.join(missing)}"}, parts)

    legal, why = structure_description_is_legal(parts[STRUCTURE_DESCRIPTION])
    if not legal:
        return refused({"combined_score": 0.0, "status": "schema_rejected", "error": why}, parts)

    missing = absent(EXPLORE)
    if missing:
        return refused({"combined_score": 0.0, "status": "missing_traces",
                        "error": f"{len(missing)} training trace(s) not on this machine: "
                                 f"{', '.join(missing)}"}, parts)

    built = build(MODULE, module_sources(parts[HEADER], parts[SOURCE]))
    if not built.success:
        return refused({"combined_score": 0.0, "status": "build_error",
                        "error": built.build_diagnostics[-3000:]}, parts)

    runs = run_traces(built.binary, EXPLORE, tag=built.source_id)
    ipcs = {stem: (run.ipc if run.success else None) for stem, run in runs.items()}

    # A trace that did not finish is skipped by score(), so a candidate whose
    # mcf run timed out would be ranked on the traces that did complete --
    # against rivals scored with mcf included, and mcf carries the largest
    # speedups in the set. Scores built from different trace sets are not
    # comparable, so refuse the candidate instead of quietly ranking it.
    failed = sorted(s for s, v in ipcs.items() if not v)
    if failed:
        return refused({"combined_score": 0.0, "status": "incomplete",
                        "error": f"{len(failed)} of {len(EXPLORE)} traces did not finish: "
                                 f"{', '.join(failed)}",
                        "ipc": ipcs}, parts)

    # The first scored candidate is the seed and is its own reference, so it
    # scores exactly 1.0; every later one is a ratio against its IPCs.
    reference = reference_ipcs() or ipcs
    combined, relative = vs_mockingjay(ipcs, reference)
    # A design CACTI cannot price still has a valid IPC; the error goes back as
    # text in place of the numbers.
    try:
        cost = cacti_metrics(parts[STRUCTURE_DESCRIPTION], built.config, runs)
    except CactiError as exc:
        cost = {"cacti_error": str(exc)[:500]}
    metrics = {"combined_score": combined, "status": "ok", **cost,
               "ipc": ipcs, "relative": relative,
               "llc": f"{built.config['LLC']['sets']}x{built.config['LLC']['ways']}"}
    # score is the name the validator reads; combined_score is the search's. The
    # structure description travels with the C++ so a design can be re-priced
    # later without deriving it again.
    remember(design_id(parts[HEADER], parts[SOURCE]),
             {"policy.h": parts[HEADER], "policy.cc": parts[SOURCE],
              "description.yaml": parts[STRUCTURE_DESCRIPTION]},
             {"score": combined, **metrics})
    return metrics


if __name__ == "__main__":
    import json
    print(json.dumps(evaluate(sys.argv[1]), indent=2, default=str))
