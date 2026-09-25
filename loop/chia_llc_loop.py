"""An LLC replacement-policy evolution loop on one machine (CHIA hackathon).

The agent is shown a policy's structure description (YAML) and the ChampSim
C++ that implements it, and proposes the next design. Each candidate passes two
cheap gates before it costs a simulation: the closed schema validator, then the
build. A candidate scores as the geometric mean of its IPC *relative to LRU* over
the explore benchmarks, so the number means the same thing on either benchmark
group; the winner is re-run on the held-out group, where a drop is overfitting
rather than an artefact of which traces landed where.

    python3 chia_llc_loop.py --baseline            # measure LRU once, cache it
    python3 chia_llc_loop.py --dry-run             # score the seed, no model call
    python3 chia_llc_loop.py --iterations 2        # evolve with AlphaEvolve

Traces within a group run concurrently: ChampSim is a subprocess, so a thread per
trace keeps all the machine's cores busy instead of one.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CHAMPSIM = Path(os.environ.get("CHAMPSIM_ROOT") or Path.home() / "champsim")  # the tree the search builds in
sys.path.insert(0, str(CHAMPSIM))

from chia_node.champsim import build_replacement, run_simulation  # noqa: E402
from feedback.area_energy import (DEFAULT_NODE_NM, CactiError, energy,  # noqa: E402,F401
                                  parse_json_run, price_policy)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from candidate import MODULE, seed_sources  # noqa: E402

TRACES = Path.home() / "traces"
POLICIES = CHAMPSIM / "structure_description" / "policies"
VALIDATOR = CHAMPSIM / "structure_description" / "validate.py"
WEIGHTS = CHAMPSIM / "weights.txt"
SELECTED = CHAMPSIM / "selected_traces.txt"
BASELINE_JSON = Path.home() / "loop_out" / "lru_baseline.json"

def load_selected() -> tuple[list[str], list[str]]:
    """The training and held-out trace lists from the DPC4 repo's shortlist.

    Two columns, the trace stem and the set it belongs to: one slice per
    benchmark, the one with the highest LLC MPKI under LRU, split by program
    family so both suites of a program stay on the same side. Every listed
    trace is kept; a run refuses a group with traces missing (see absent).
    """
    training, held_out = [], []
    if not SELECTED.exists():
        return training, held_out
    for line in SELECTED.read_text().splitlines():
        fields = line.split("#", 1)[0].split()
        if len(fields) < 2:
            continue
        stem, group = fields[0], fields[1]
        (training if group == "training" else held_out).append(stem)
    return training, held_out


# Search and selection happen on EXPLORE; VALIDATE is only for checking a design
# that already looks good, so a gap between them is overfitting rather than an
# artefact of which traces landed where.
EXPLORE, VALIDATE = load_selected()

# Three tiers, each at the fidelity its job needs. Searching at 5M/10M was not
# merely noisy but misleading -- gcc read as a 0.2% loss at that length and is a
# 15% win at 20M/50M, while lbm read as the best trace and is nearly flat. Every
# baseline is fidelity-specific, so each tier keeps its own.
EXPLORE_WARMUP, EXPLORE_SIM = 20_000_000, 50_000_000      # every candidate
VALIDATE_WARMUP, VALIDATE_SIM = 50_000_000, 100_000_000   # promoted designs
FINAL_WARMUP, FINAL_SIM = 50_000_000, 200_000_000         # winner and baselines

WARMUP, SIM = EXPLORE_WARMUP, EXPLORE_SIM
OPT_SETS = 256  # a multiple of 64, up to 4096
# Traces of one candidate at a time: cores - 2 (CHIA_WORKERS overrides), so a candidate's 17
# traces start in one wave on any machine with 19 cores or more.
WORKERS = int(os.environ.get("CHIA_WORKERS") or max(1, (os.cpu_count() or 4) - 2))


def trace_path(stem: str) -> str:
    return str(TRACES / f"{stem}.champsimtrace.xz")


def absent(group: list[str]) -> list[str]:
    """The traces of a group that are not on this machine."""
    return [s for s in group if not Path(trace_path(s)).exists()]


def geomean(xs) -> float:
    xs = [x for x in xs if x and x > 0]
    return math.exp(sum(math.log(x) for x in xs) / len(xs)) if xs else 0.0


def structure_description_is_legal(structure_description_yaml: str) -> tuple[bool, str]:
    """The closed schema, in milliseconds, before a candidate costs a build."""
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as fh:
        fh.write(structure_description_yaml)
        path = fh.name
    try:
        done = subprocess.run([sys.executable, str(VALIDATOR), path],
                              capture_output=True, text=True, timeout=60)
        return done.returncode == 0, (done.stdout + done.stderr).strip()
    finally:
        Path(path).unlink(missing_ok=True)


#: run_simulation defaults to 3600s, which the three largest traces (the two
#: mcf slices and 602.gcc_s, all 2-3x the typical 384 MB) exceed when a dozen
#: simulations compete for the machine -- they finish comfortably when run
#: alone. A timeout returns no IPC, and since a missing trace is skipped rather
#: than fatal, the quiet result is a candidate scored without mcf: the very
#: benchmark carrying the largest speedups.
SIM_TIMEOUT_S = 10_800


def run_traces(binary: bytes, group: list[str], *, opt_log_dir: Path | None = None,
               tag: str = "", warmup: int = WARMUP, sim: int = SIM,
               timeout_s: int = SIM_TIMEOUT_S) -> dict:
    """Run one binary over a benchmark group, one thread per trace; each
    trace's whole RunResult, statistics included.

    The fidelity is an argument because each tier needs a different one and a
    baseline only means anything at the length it was measured at.
    """
    missing = absent(group)
    if missing:
        raise FileNotFoundError(f"{len(missing)} trace(s) not on this machine: "
                                f"{', '.join(missing)}")

    def one(stem: str):
        # --opt-sets is only meaningful with a log; run_command rejects the pair
        # when the log is absent, so send neither for a scoring-only run.
        opt = ({"opt_log": str(opt_log_dir / f"{tag}.{stem}.opt.log"),
                "opt_sets": OPT_SETS} if opt_log_dir else {})
        return stem, run_simulation(binary, trace_path(stem), warmup_instructions=warmup,
                                    simulation_instructions=sim, timeout_s=timeout_s, **opt)

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        return dict(pool.map(one, group))


def run_group(binary: bytes, group: list[str], **kw) -> dict[str, float | None]:
    """IPC per trace, None where a run failed."""
    return {stem: (run.ipc if run.success else None)
            for stem, run in run_traces(binary, group, **kw).items()}


def cacti_metrics(structure_description_yaml: str, config: dict, runs: dict, words=None) -> dict:
    """The metadata the structure description declares, priced by CACTI at the
    built LLC.

    Priced from the structure description, not the C++; nothing checks that the
    two agree. Energy is each trace's LLC accesses x read energy plus leakage x
    simulated time, summed over the traces. Reported, not scored. `words` are the
    candidate's declared new words, which hold no storage of their own.
    """
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as fh:
        fh.write(structure_description_yaml)
        path = fh.name
    try:
        llc = config["LLC"]
        priced = price_policy(path, llc["sets"], llc["ways"], config["num_cores"],
                              DEFAULT_NODE_NM, words=words)
    finally:
        Path(path).unlink(missing_ok=True)
    hz = config["ooo_cpu"][0]["frequency"] * 1e6
    energy_nj = 0.0
    for run in runs.values():
        stats = parse_json_run(run.stats)
        seconds = stats.cycles / hz
        energy_nj += sum(energy(a, stats.accesses["LLC"], seconds)["energy_nj"]
                         for a in priced["arrays"])
    return {"metadata_kb": priced["sram_bits"] / 8192,
            "metadata_flipflop_bits": priced["register_bits"],
            "metadata_bits_per_line": priced["array_bits_per_line"],
            "metadata_area_mm2": priced["area_um2"] / 1e6,
            "metadata_energy_uj": energy_nj / 1e3,
            "cacti_node_nm": DEFAULT_NODE_NM}


def build(module: str, sources: dict[str, str]):
    """Builds of one tree take turns on the node's own lock, across threads and
    processes, so no lock is needed here."""
    return build_replacement(str(CHAMPSIM), module, sources)


# --------------------------------------------------------------------------
# LRU baseline: the denominator that makes explore and validate comparable.
# --------------------------------------------------------------------------
#: The baseline module's name must not contain "lru": the rename below rewrites
#: every occurrence of that substring, so a name like "lru_base" would turn the
#: already-renamed include into "lru_base_base.h" and the build would fail.
BASELINE_MODULE = "basis_policy"


def renamed_lru(module: str) -> dict[str, str]:
    """ChampSim's LRU under another name, renamed the way smoke_test.py does it:
    the include guard first (it is upper case), then the include, then the bare
    identifier. Renaming the identifier first leaves a half-renamed class and the
    build fails on an incomplete type."""
    out = {}
    for name in ("lru.h", "lru.cc"):
        text = (CHAMPSIM / "replacement" / "lru" / name).read_text()
        text = text.replace("REPLACEMENT_LRU_H", f"REPLACEMENT_{module.upper()}_H")
        text = text.replace('"lru.h"', f'"{module}.h"').replace("lru", module)
        out[name.replace("lru", module)] = text
    return out


def measure_baseline() -> dict:
    print(f"measuring the LRU baseline on all {len(EXPLORE) + len(VALIDATE)} traces "
          f"({WORKERS} at a time)")
    built = build(BASELINE_MODULE, renamed_lru(BASELINE_MODULE))
    if not built.success:
        print(f"  build failed:\n{built.build_diagnostics[-2000:]}")
        raise SystemExit(1)
    t0 = time.time()
    ipcs = run_group(built.binary, EXPLORE + VALIDATE, tag="lru")
    BASELINE_JSON.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_JSON.write_text(json.dumps(ipcs, indent=2))
    print(f"  done in {time.time() - t0:.0f}s -> {BASELINE_JSON}")
    for stem, ipc in ipcs.items():
        print(f"    {stem:28s} {ipc if ipc is None else f'{ipc:.4f}'}")
    return ipcs


def load_baseline() -> dict:
    if not BASELINE_JSON.exists():
        print(f"no baseline at {BASELINE_JSON}; run with --baseline first")
        raise SystemExit(1)
    return json.loads(BASELINE_JSON.read_text())


def benchmark_of(stem: str) -> str:
    """The benchmark a slice belongs to: 602.gcc_s-734B -> 602.gcc_s."""
    return re.sub(r"-\d+B$", "", stem)


def load_weights() -> dict[str, float]:
    """SimPoint weight per slice, from the DPC4 repo's weights.txt.

    Every slice of a benchmark is listed and the weights sum to 1; the shortlist
    in selected_traces.txt keeps one slice per benchmark.
    """
    out: dict[str, float] = {}
    if not WEIGHTS.exists():
        return out
    for line in WEIGHTS.read_text().splitlines():
        name, _, value = line.partition(":")
        if value.strip():
            out[name.strip()] = float(value)
    return out


def score(ipcs: dict, baseline: dict,
          weights: dict | None = None) -> tuple[float, dict, dict]:
    """Per-slice speedup, folded per benchmark, then the geometric mean.

    A benchmark counts once however many slices represent it. Today's shortlist
    has one slice per benchmark, so the fold changes nothing; with several, the
    slices are combined by SimPoint weight, renormalised over the slices actually
    run, so a benchmark is not discounted by whatever its dropped tail carried.
    """
    rel = {}
    for stem, ipc in ipcs.items():
        base = baseline.get(stem)
        rel[stem] = (ipc / base) if (ipc and base) else None

    weights = load_weights() if weights is None else weights
    slices: dict[str, list[tuple[float, float, float]]] = {}
    for stem, ipc in ipcs.items():
        base = baseline.get(stem)
        if ipc and base:
            # An unlisted slice falls back to equal weight, which is the right
            # default for the SPEC2017 set we ran before the shortlist existed.
            slices.setdefault(benchmark_of(stem), []).append(
                (ipc, base, weights.get(stem, 1.0)))

    per_benchmark = {}
    for bench, items in slices.items():
        total = sum(w for _, _, w in items)
        if total <= 0:
            continue
        # IPC is a rate, so the SimPoint reconstruction of a whole benchmark is
        # the weighted HARMONIC mean of its slices: the program spends
        # w_i of its instructions at CPI_i, giving CPI = sum(w_i * CPI_i) and
        # IPC = 1 / that. Averaging the slice IPCs arithmetically, or averaging
        # their speedup ratios, both overstate the result -- the slowest slice
        # is where the cycles actually go, and a rate average understates its
        # cost. Reconstruct each policy separately, then divide.
        policy_ipc = total / sum(w / ipc for ipc, _, w in items if ipc > 0)
        lru_ipc = total / sum(w / base for _, base, w in items if base > 0)
        per_benchmark[bench] = policy_ipc / lru_ipc
    return geomean(per_benchmark.values()), rel, per_benchmark


def evaluate(module: str, sources: dict[str, str], group: list[str],
             baseline: dict) -> dict:
    built = build(module, sources)
    if not built.success:
        return {"status": "build_error", "score": 0.0,
                "diagnostics": built.build_diagnostics[-4000:]}
    ipcs = run_group(built.binary, group, tag=module)
    s, rel, per_benchmark = score(ipcs, baseline)
    llc = built.config["LLC"]
    return {"status": "ok" if any(rel.values()) else "all_runs_failed", "score": s,
            "ipc": ipcs, "relative": rel, "benchmark": per_benchmark,
            "llc": f"{llc['sets']}x{llc['ways']}", "build_s": built.build_duration_s}


def show(label: str, res: dict) -> None:
    print(f"  {label}: {res['status']}  geomean IPC vs LRU {res['score']:.4f}"
          f"{'  LLC ' + res['llc'] if res.get('llc') else ''}")
    for stem, r in (res.get("relative") or {}).items():
        ipc = (res.get("ipc") or {}).get(stem)
        print(f"    {stem:28s} IPC {ipc if ipc is None else f'{ipc:.4f}'}"
              f"   x{'--' if r is None else f'{r:.4f}'}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--iterations", type=int, default=2)
    ap.add_argument("--seed", default="mockingjay")
    ap.add_argument("--baseline", action="store_true", help="measure LRU and exit")
    ap.add_argument("--dry-run", action="store_true", help="score the seed, no model call")
    args = ap.parse_args()

    if args.baseline:
        measure_baseline()
        return 0

    baseline = load_baseline()
    structure_description = (POLICIES / f"{args.seed}.yaml").read_text()
    sources = seed_sources(args.seed)
    legal, why = structure_description_is_legal(structure_description)
    print(f"seed {args.seed}: schema {'ok' if legal else 'REJECTED'}  {why}")

    missing = absent(EXPLORE)
    if missing:
        print(f"{len(missing)} training trace(s) not on this machine: {', '.join(missing)}")
        return 1

    print(f"\nexplore group, {len(EXPLORE)} traces, {WORKERS} at a time")
    t0 = time.time()
    best = evaluate(MODULE, sources, EXPLORE, baseline)
    show("seed", best)
    print(f"  ({time.time() - t0:.0f}s)")

    if not args.dry_run:
        print("\nAlphaEvolve wiring is not in this file yet; use --dry-run")

    held = None
    missing = absent(VALIDATE)
    if missing:
        print(f"\nheld-out group: {len(missing)} of {len(VALIDATE)} traces not on this "
              f"machine, validation not run: {', '.join(missing)}")
    else:
        print(f"\nheld-out group, {len(VALIDATE)} traces")
        held = evaluate(MODULE, sources, VALIDATE, baseline)
        show("held-out", held)
        print(f"\n  explore  {best['score']:.4f}   held-out {held['score']:.4f}"
              f"   gap {best['score'] - held['score']:+.4f}")

    out = Path.home() / "loop_out" / "result.json"
    out.write_text(json.dumps({"explore": best, "validate": held}, indent=2, default=str))
    print(f"  wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
