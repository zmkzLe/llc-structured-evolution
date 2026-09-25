"""What has to hold before an arm is launched under a native search algorithm.

    python3 check_native.py --search adaevolve

Runs in seconds and calls no model and no simulator. It exists because the ways
this can fail are all quiet: a score that never reaches the search reads as a
policy that lost, a config field that does not exist reads as a setting that was
applied, and a run of a hundred candidates then completes having learnt nothing.
Each check below is one of those, made loud.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

OK, BAD = "ok  ", "FAIL"
failures: list[str] = []


def report(name: str, good: bool, detail: str = "") -> bool:
    print(f"  [{OK if good else BAD}] {name}{': ' + detail if detail else ''}")
    if not good:
        failures.append(name)
    return good


def check_registry(search: str) -> None:
    """The algorithm has to be one the registry knows, and its database class
    has to be the one whose fields the driver sets."""
    from skydiscover.config import _DB_CONFIG_BY_TYPE
    from skydiscover.search import route  # noqa: F401 -- registers everything
    from skydiscover.search.registry import _CONTROLLER_REGISTRY, _DATABASE_REGISTRY

    db = _DATABASE_REGISTRY.get(search)
    if search == "evox" and db is None:
        # EvoX's registry entry is its controller ("evox") plus a meta-level
        # database ("evox_meta"); the solution database is loaded at runtime
        # from EvoxDatabaseConfig.database_file_path, which defaults to the
        # built-in initial strategy. The right existence check is that file.
        from skydiscover.config import EvoxDatabaseConfig
        path = EvoxDatabaseConfig().database_file_path
        report("evox: the strategy file its database loads from exists",
               bool(path) and Path(path).exists(), str(path))
    else:
        report(f"{search}: a database is registered", db is not None,
               db.__name__ if db else "nothing registered; the run would fail at startup")
    ctrl = _CONTROLLER_REGISTRY.get(search)
    print(f"  [    ] {search}: controller "
          f"{ctrl.__name__ if ctrl else 'DiscoveryController (the default)'}")
    cfg = _DB_CONFIG_BY_TYPE.get(search)
    report(f"{search}: a config class is mapped", cfg is not None,
           cfg.__name__ if cfg else "falls back to DatabaseConfig")


def check_config(search: str) -> None:
    """Every field the driver sets has to exist. must_set raises on one that does
    not, so this is the same check made before a VM is booked rather than after."""
    from run_native import database_fields
    from skydiscover.config import Config, _DB_CONFIG_BY_TYPE

    class Args:
        population, islands, migration_interval = 40, 2, 50

    config = Config()
    cls = _DB_CONFIG_BY_TYPE.get(search)
    if cls is not None:
        config.search.database = cls()
    wanted = database_fields(search, Args)
    missing = [f for f in wanted if not hasattr(config.search.database, f)]
    report(f"{search}: the {len(wanted)} database field(s) exist", not missing,
           ", ".join(missing) if missing else ", ".join(sorted(wanted)) or "none needed")

    for obj, name in ((config, "max_parallel_iterations"), (config, "diff_based_generation"),
                      (config, "system_prompt_override"), (config, "file_suffix"),
                      (config.evaluator, "cascade_evaluation"), (config.evaluator, "timeout")):
        report(f"Config{'' if obj is config else '.evaluator'}.{name} exists",
               hasattr(obj, name))

    # The driver's own arrangement, so what is checked is what runs: the
    # controller builds one LLMPool per list and raises on an empty one, before
    # a single proposal. AdaEvolve died on guide_models this way.
    from run_native import set_llm

    class LLMArgs:
        temperature, max_tokens, llm_timeout, llm_retries = 0.7, 32_000, 900, 2

    set_llm(config, [("google/probe", 1.0)], "https://example.invalid", "key", LLMArgs)
    for name in ("models", "evaluator_models", "guide_models"):
        pool = getattr(config.llm, name)
        report(f"config.llm.{name} is non-empty", bool(pool),
               f"{len(pool)} model(s)" if pool else "LLMPool would raise on this")


def check_extraction(search: str) -> None:
    """The reply has to be cut at its markers, in the module that will read it.

    A controller binds parse_full_rewrite in its own namespace at import, so a
    patch applied only where the function is defined leaves that copy pointing
    at the original -- which, finding no code fence, returns the whole reply.
    The evaluator then refuses it as "missing section(s)" a second later, and
    the run proposes and refuses for hours at no cost but the proposals.
    """
    import importlib

    from candidate import MARKER, STRUCTURE_DESCRIPTION
    from run_native import install_marker_extraction

    install_marker_extraction(search)
    module = importlib.import_module(f"skydiscover.search.{search}.controller") \
        if search in ("adaevolve", "gepa_native") else \
        importlib.import_module("skydiscover.search.default_discovery_controller")
    parse = module.parse_full_rewrite

    reply = ("Here is my design.\n\n"
             f"{MARKER.format(STRUCTURE_DESCRIPTION)}\nname: probe\n"
             f"{MARKER.format('NEW_WORDS')}\n[]\n")
    got = parse(reply, None)
    report(f"{search}'s controller cuts the reply at the marker",
           got.startswith(MARKER.format(STRUCTURE_DESCRIPTION)),
           f"starts {got[:38]!r}")
    report("both sections survive",
           MARKER.format(STRUCTURE_DESCRIPTION) in got and MARKER.format("NEW_WORDS") in got)


def check_guidance(search: str) -> None:
    """The guidance rewrite has to hit proposals and only proposals.

    The seam is DiscoveryController._call_llm, which every native controller
    inherits; the rule (Khoi's, from the OpenEvolve arm) is that only a system
    message equal to the fixed prompt is rebuilt, so the paradigm writer's and
    the judge's calls pass through untouched.
    """
    import tempfile

    from run_native import guided_system

    rebuild = lambda guidance="": f"FIXED with [{guidance}]"  # noqa: E731
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "guidance.txt"
        path.write_text("STEER LEFT")
        got = guided_system("FIXED", "FIXED", path, rebuild)
        report("a proposal's prompt carries the guidance text", "STEER LEFT" in got, got)
        other = guided_system("the paradigm writer's message", "FIXED", path, rebuild)
        report("another caller's message passes untouched",
               other == "the paradigm writer's message")
        absent = Path(d) / "never_written.txt"
        report("a missing guidance file means an empty section",
               guided_system("FIXED", "FIXED", absent, rebuild) == "FIXED with []")


def check_result_shape() -> None:
    """The evaluator's answer has to keep combined_score on the way to the search.

    This is the one that cost a whole run: openevolve and skydiscover each define
    an EvaluationResult, neither recognises the other's, and skydiscover's
    normaliser turns a stranger into {"error": 0.0} without complaint. Every
    candidate then scores zero and the search climbs a flat landscape to the end.
    """
    os.environ["A3_RESULT"] = "skydiscover"
    from design_evaluator import as_result
    from skydiscover.evaluation.evaluation_result import EvaluationResult
    from skydiscover.utils.metrics import get_score

    metrics = {"combined_score": 1.0042, "status": "ok"}
    result = as_result(metrics, "why text")
    report("the evaluator answers in skydiscover's EvaluationResult",
           isinstance(result, EvaluationResult), type(result).__module__)

    # The path a real result takes through the evaluator, without running one.
    from skydiscover.evaluation.evaluator import Evaluator
    normalised = Evaluator._normalize_result(None, result)
    score = get_score(normalised.metrics)
    report("combined_score survives normalisation", score == 1.0042,
           f"{score} (the evaluator returned {metrics['combined_score']})")
    # The key decides whether the text is ever rendered: skydiscover's context
    # builders look for "feedback" and ignore other keys, so "why" would reach
    # the database and never a prompt -- the model would see scores without
    # reasons for the whole run.
    arts = getattr(normalised, "artifacts", None) or {}
    report("the feedback survives under the key the context builder reads",
           "feedback" in arts, str(sorted(arts)))


def check_seed_and_traces(traces: str | None) -> None:
    """The seed has to split into the sections the evaluator reads, and every
    trace of the group has to be on this machine."""
    import evolver_prompt
    from chia_llc_loop import EXPLORE, absent
    from design_evaluator import NEW_WORDS, STRUCTURE_DESCRIPTION, split_candidate

    parts = split_candidate(evolver_prompt.packed_seed())
    report("the seed splits into its two sections",
           bool(parts.get(STRUCTURE_DESCRIPTION, "").strip()) and NEW_WORDS in parts,
           ", ".join(sorted(parts)))

    group = traces.split(",") if traces else EXPLORE
    missing = absent(group)
    report(f"all {len(group)} trace(s) are on this machine", not missing,
           ", ".join(missing) if missing else f"{len(group)} present")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--search", default="adaevolve")
    ap.add_argument("--traces", help="comma-separated stems; the training set by default")
    args = ap.parse_args()

    print(f"checking the {args.search} arm\n")
    for name, fn in (("registry", lambda: check_registry(args.search)),
                     ("config", lambda: check_config(args.search)),
                     ("candidate extraction", lambda: check_extraction(args.search)),
                     ("guidance", lambda: check_guidance(args.search)),
                     ("evaluator result", check_result_shape),
                     ("seed and traces", lambda: check_seed_and_traces(args.traces))):
        print(f"{name}:")
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 -- a check that cannot run is a failure
            report(f"{name} checks ran", False, f"{type(exc).__name__}: {exc}")
        print()

    if failures:
        print(f"{len(failures)} check(s) failed:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("every check passed; the arm can be launched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
