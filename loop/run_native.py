"""Evolve an LLC policy design with one of skydiscover's own search algorithms.

The seed, the prompt, the evaluator, the C++ writer and the records are the ones
run_openevolve.py uses with `--evaluator yaml`, so an arm run here differs from
Khoi's only in which algorithm proposes the next design:

    python3 run_native.py --search adaevolve --vertex --iterations 100000

`--search` takes a type skydiscover registers natively (adaevolve, gepa_native,
openevolve_native, evox, topk, beam_search, best_of_n). These are a different
contract from the external backends: they have no `run()` to call, and are
reached through run_discovery() and the registry instead. The external
`openevolve` type is deliberately refused here -- run_openevolve.py drives it,
and routing it through this file would change the evaluator loading and the
missing-score fallback while claiming to change only the algorithm.

`--guidance FILE` is the adaptive arm, as in Khoi's runs: guidance_writer.py
rewrites the file beside the search and every proposal's prompt carries it as it
stands at that moment. His arm patches OpenEvolve's PromptSampler; here the same
rule rides the native controllers' shared seam, _call_llm.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# Vertex plumbing is the search's, not OpenEvolve's: the token refresh, the
# usage log and the check that a request carries the sampling asked for all work
# on any client built from the openai package, which skydiscover's LLM is
# (llm/openai.py).
from run_openevolve import (AI_STUDIO_BASE, VERTEX_REGION,  # noqa: E402
                            install_refreshing_auth, must_set, vertex_base,
                            vertex_credentials)

#: Native types, by what each is. The registry accepts more; these are the ones
#: whose config this file knows how to fill.
NATIVE = {
    "adaevolve": "adaptive multi-island evolution, intensity per island",
    "gepa_native": "guided evolution, acceptance gating and LLM merge",
    "openevolve_native": "MAP-Elites with islands: the controlled comparison",
    "evox": "co-evolves the search strategy beside the solutions",
    "topk": "keep the best k",
    "beam_search": "beam search",
    "best_of_n": "sample n, keep the best",
}


def database_fields(search: str, args) -> dict:
    """Per-algorithm `search.database` settings.

    Only what the arm needs: a population, the islands, and which metric is the
    fitness and which way is better. Everything else stays at the algorithm's
    own default, so an arm is that algorithm as its authors tuned it rather than
    as this file guessed.
    """
    if search == "adaevolve":
        # AdaEvolve is the one that asks which metric is the fitness; the rest
        # read combined_score through utils.metrics.get_score, which prefers it
        # already and falls back to the mean of the numeric metrics. Naming it
        # here anyway would raise, since no other database config has the field.
        return {"fitness_key": "combined_score",
                "higher_is_better": {"combined_score": True},
                "population_size": args.population, "num_islands": args.islands,
                "migration_interval": args.migration_interval}
    if search == "gepa_native":
        # Reflective prompting puts the evaluator's diagnostics in the next
        # prompt; ours is the "why" artifact, which is why design_evaluator
        # answers in skydiscover's EvaluationResult (as_result) under this arm.
        return {"population_size": args.population, "acceptance_gating": True}
    if search == "openevolve_native":
        return {"population_size": args.population, "num_islands": args.islands,
                "migration_interval": args.migration_interval}
    return {}


def install_marker_extraction(search: str) -> None:
    """Take the candidate from its markers, not from a code fence.

    parse_full_rewrite looks for a fenced block and, finding none, returns the
    whole reply (utils/code_utils.py). Our candidate is delimited by
    `===== STRUCTURE_DESCRIPTION =====` and `===== NEW_WORDS =====` and the
    prompt never asks for a fence, so a model that answers exactly as asked has
    its entire reply handed to the evaluator -- prose, echoed prompt and all --
    which is refused as "missing section(s)" a second later. Three of the first
    five candidates went that way.

    So the reply is cut from the first marker to the end, and only a reply with
    no marker at all is left to the original.
    """
    import importlib

    from skydiscover.utils import code_utils
    from candidate import MARKER, STRUCTURE_DESCRIPTION

    opening = MARKER.format(STRUCTURE_DESCRIPTION)
    original = code_utils.parse_full_rewrite

    import yaml

    words_marker = MARKER.format("NEW_WORDS")

    def from_markers(llm_response: str, language=None):
        # The LAST occurrence: a reply that echoes the prompt carries the
        # prompt's own format example (and the parent program), both of which
        # open with this marker, before the model's actual answer.
        start = llm_response.rfind(opening)
        if start == -1:
            return original(llm_response, language)
        text = llm_response[start:]
        # A model that fences the sections anyway leaves the closing ``` behind.
        fence = text.rfind("```")
        if fence != -1:
            text = text[:fence]
        # Prose after the words list lands inside the NEW_WORDS section, whose
        # YAML parse then fails and the whole design is refused -- 21 of the
        # first 24 candidates went that way, over a list that was often fine.
        # Keep the longest prefix of the section that parses; what is dropped is
        # commentary, since a real word past the prose would not parse either.
        cut = text.find(words_marker)
        if cut != -1:
            head = text[:cut + len(words_marker)]
            lines = text[cut + len(words_marker):].splitlines()
            while lines:
                # Only a shape the evaluator accepts ends the trim: a line of
                # prose on its own parses happily as a YAML *string*, and the
                # design then dies on "the new words must be a YAML list".
                try:
                    parsed = yaml.safe_load("\n".join(lines))
                except yaml.YAMLError:
                    lines.pop()
                    continue
                if parsed is None or isinstance(parsed, list):
                    break
                lines.pop()
            return (head + "\n" + "\n".join(lines)).strip()
        return text.strip()

    # Each controller does `from ...code_utils import parse_full_rewrite`, which
    # binds the function in its own module at import. Rebinding it only where it
    # is defined leaves those copies pointing at the original -- adaevolve's
    # controller calls its own (controller.py:736,739), which is why patching
    # default_discovery_controller alone changed nothing.
    code_utils.parse_full_rewrite = from_markers
    patched = ["skydiscover.utils.code_utils"]
    for name in ("skydiscover.search.default_discovery_controller",
                 "skydiscover.search.adaevolve.controller",
                 "skydiscover.search.gepa_native.controller",
                 "skydiscover.search.evox.controller"):
        try:
            module = importlib.import_module(name)
        except ImportError:
            continue
        if getattr(module, "parse_full_rewrite", None) is not None:
            module.parse_full_rewrite = from_markers
            patched.append(name)
    # The controller that will actually run has to be one of them. Missing it is
    # silent: the whole reply becomes the candidate and is refused a second
    # later as "missing section(s)", so the run proposes and refuses for hours.
    mine = f"skydiscover.search.{search}.controller"
    assert mine in patched or search not in ("adaevolve", "gepa_native"), \
        f"{search} has its own parse_full_rewrite and it was not patched: {patched}"
    print(f"candidate taken from its markers in: "
          f"{', '.join(p.rsplit('.', 2)[-2] + '.' + p.rsplit('.', 1)[-1] for p in patched)}")


def guided_system(system: str, fixed: str, path: Path, rebuild) -> str:
    """The system message a proposal should carry, given the guidance file now.

    Only the fixed prompt is rebuilt: the controller sends other system messages
    too (the paradigm writer's, the judge's), and those are not proposals. This
    is Khoi's rule from the OpenEvolve arm, on skydiscover's seam.
    """
    if system != fixed:
        return system
    return rebuild(guidance=path.read_text() if path.exists() else "")


def install_guidance_native(path: Path, fixed: str) -> None:
    """Every proposal's prompt carries the guidance file as it stands at that
    moment (guidance_writer.py rewrites it beside the search).

    Khoi's adaptive arm does this by patching OpenEvolve's PromptSampler, which
    native algorithms never touch. Their one shared seam is
    DiscoveryController._call_llm(system, user): every controller inherits it,
    and every proposal reaches it with the fixed prompt as its system message.
    """
    import evolver_prompt
    from skydiscover.search.default_discovery_controller import DiscoveryController

    original = DiscoveryController._call_llm

    async def with_guidance(self, system_message: str, user_message: str, **kwargs):
        return await original(
            self, guided_system(system_message, fixed, path, evolver_prompt.instructions),
            user_message, **kwargs)

    DiscoveryController._call_llm = with_guidance


def set_llm(config, proposers, api_base: str, api_key: str, args) -> None:
    """The three model lists the controller builds a pool from.

    It makes one LLMPool per list and each raises on an empty one, before a
    single proposal. LLMConfig.__post_init__ does fill the evaluator's and the
    guide's lists from `models` -- but when the Config is built, so a `models`
    assigned afterwards leaves the other two empty. AdaEvolve died on
    guide_models exactly that way: the pool that writes a paradigm when an
    island stagnates. check_native calls this, so the arrangement the driver
    uses is the one that gets checked.
    """
    from skydiscover.config import LLMModelConfig

    must_set(config.llm, "api_base", api_base)
    must_set(config.llm, "temperature", args.temperature)
    must_set(config.llm, "max_tokens", args.max_tokens)
    must_set(config.llm, "timeout", args.llm_timeout)
    must_set(config.llm, "retries", args.llm_retries)
    models = [LLMModelConfig(name=n, weight=w, api_key=api_key, api_base=api_base,
                             temperature=args.temperature, max_tokens=args.max_tokens,
                             timeout=args.llm_timeout, retries=args.llm_retries)
              for n, w in proposers]
    must_set(config.llm, "models", models)
    must_set(config.llm, "evaluator_models", list(models))
    must_set(config.llm, "guide_models", list(models))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--search", required=True, choices=sorted(NATIVE),
                    help="; ".join(f"{k}: {v}" for k, v in sorted(NATIVE.items())))
    ap.add_argument("--iterations", type=int, default=100000)
    ap.add_argument("--seed", default="mockingjay")
    ap.add_argument("--model", default="gemini-2.5-pro")
    ap.add_argument("--ensemble", help="model=weight,model=weight; one drawn per proposal")
    ap.add_argument("--vertex", action="store_true",
                    help="call Gemini through Vertex (bills the project's credit)")
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--max-tokens", type=int, default=32_000)
    ap.add_argument("--llm-timeout", type=int, default=600)
    ap.add_argument("--llm-retries", type=int, default=2)
    ap.add_argument("--population", type=int, default=40)
    ap.add_argument("--islands", type=int, default=2)
    ap.add_argument("--migration-interval", type=int, default=50)
    ap.add_argument("--parallel", type=int, default=2,
                    help="candidates evaluated at once")
    ap.add_argument("--eval-timeout", type=int, default=10800,
                    help="seconds for one candidate: a build plus a simulation per trace")
    ap.add_argument("--traces", help="comma-separated stems; the training set by default")
    ap.add_argument("--warmup", type=int)
    ap.add_argument("--sim", type=int)
    ap.add_argument("--max-change", type=int,
                    help="canonical lines a proposal may change")
    ap.add_argument("--guidance", type=Path,
                    help="a file whose text goes into every proposal's prompt, read at "
                         "each one (guidance_writer.py rewrites it beside the search). "
                         "Absent, the prompt is the fixed one")
    ap.add_argument("--run-dir", type=Path,
                    help="where records.jsonl and the candidates go; <out>/yaml_run by default")
    ap.add_argument("--out", type=Path, default=Path.home() / "oe_out")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    # The evaluator reads these, and so does the prompt, so they are set before
    # evolver_prompt is imported and before any worker is forked.
    os.environ["A3_RUN_DIR"] = str(args.run_dir or args.out / "yaml_run")
    # design_evaluator answers in whichever framework is driving; this one is not
    # OpenEvolve, and the wrong EvaluationResult loses combined_score silently.
    os.environ["A3_RESULT"] = "skydiscover"
    for flag, var in (("traces", "A3_TRACES"), ("warmup", "A3_WARMUP"), ("sim", "A3_SIM"),
                      ("max_change", "A3_MAX_CHANGE")):
        if getattr(args, flag):
            os.environ[var] = str(getattr(args, flag))

    import evolver_prompt
    from chia_llc_loop import EXPLORE, absent

    group = args.traces.split(",") if args.traces else EXPLORE
    missing = absent(group)
    if missing:
        print(f"{len(missing)} trace(s) not on this machine: {', '.join(missing)}")
        return 1

    instructions = evolver_prompt.instructions()
    if args.max_change:
        assert f"at most {args.max_change} canonical lines" in instructions, \
            "the prompt does not carry the step limit"

    proposers = [(args.model, 1.0)]
    if args.ensemble:
        proposers = []
        for item in args.ensemble.split(","):
            name, _, weight = item.strip().partition("=")
            assert name and weight, f"--ensemble item {item!r}: write model=weight"
            proposers.append((name, float(weight)))
        assert all(w > 0 for _, w in proposers) and len({n for n, _ in proposers}) == len(proposers), \
            "--ensemble: weights must be positive and model names distinct"

    if args.vertex:
        api_key, project = vertex_credentials()
        api_base = vertex_base(project)
        proposers = [(n if "/" in n else f"google/{n}", w) for n, w in proposers]
        expect = {"temperature": args.temperature, "seed": None}
        install_refreshing_auth(args.out / "llm_calls.jsonl", expect)
        print(f"LLM: {', '.join(f'{n} (weight {w:g})' for n, w in proposers)} via Vertex "
              f"({project}, {VERTEX_REGION}); usage bills that project's credit, "
              f"token refreshed per request")
    else:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            print("set GEMINI_API_KEY, or pass --vertex to use the GCP credit")
            return 1
        api_base = AI_STUDIO_BASE
        print(f"LLM: {', '.join(f'{n} (weight {w:g})' for n, w in proposers)} via AI Studio")

    program = args.out / "seed_candidate.txt"
    program.write_text(evolver_prompt.packed_seed(args.seed))
    from design_evaluator import NEW_WORDS, STRUCTURE_DESCRIPTION, split_candidate
    parts = split_candidate(program.read_text())
    assert parts.get(STRUCTURE_DESCRIPTION, "").strip() and NEW_WORDS in parts, \
        f"the seed candidate does not split into its two sections: {sorted(parts)}"
    evaluator_path = HERE / "design_evaluator.py"
    assert evaluator_path.exists(), evaluator_path
    print(f"seed written to {program} ({program.stat().st_size} B); "
          f"evaluator {evaluator_path.name}")

    # Before the controller is built, so the parse it uses is this one.
    install_marker_extraction(args.search)
    if args.guidance:
        import evolver_prompt as _ep
        install_guidance_native(args.guidance, _ep.instructions())
        print(f"guidance: every proposal's prompt carries {args.guidance} as it stands at that moment")

    from skydiscover.api import run_discovery
    from skydiscover.config import Config, LLMModelConfig

    config = Config()
    must_set(config, "max_iterations", args.iterations)
    # The candidate is a structure description and its new words, not Python.
    must_set(config, "file_suffix", ".txt")
    must_set(config, "system_prompt_override", instructions)
    must_set(config, "max_solution_length", 200_000)

    must_set(config.search, "type", args.search)
    must_set(config.evaluator, "timeout", args.eval_timeout)
    # A candidate is proposed whole, as the prompt asks for. Left at its default
    # the model is asked for a diff instead, and every reply dies unparsed.
    must_set(config, "diff_based_generation", False)
    # Cascade evaluation expects the evaluator to offer a cheap first stage
    # (evaluate_stage1); design_evaluator has one gate, the schema, and applies
    # it itself in milliseconds.
    must_set(config.evaluator, "cascade_evaluation", False)
    # Candidates evaluated at once. The name is the top-level one, not
    # OpenEvolve's evaluator.parallel_evaluations, which skydiscover has no
    # field for.
    must_set(config, "max_parallel_iterations", args.parallel)

    set_llm(config, proposers, api_base, api_key, args)

    # search.database is a different dataclass per algorithm
    # (config._DB_CONFIG_BY_TYPE), and a bare Config() builds the base one. The
    # class has to be swapped before its fields are set: apply_overrides swaps it
    # too, but only once run_discovery is under way, which would replace this
    # object and take every field set on it with it.
    from skydiscover.config import _DB_CONFIG_BY_TYPE
    db_cls = _DB_CONFIG_BY_TYPE.get(args.search)
    if db_cls is not None and not isinstance(config.search.database, db_cls):
        config.search.database = db_cls()
    # must_set refuses a name this algorithm's config does not have, rather than
    # quietly attaching one that nothing reads.
    for field, value in database_fields(args.search, args).items():
        must_set(config.search.database, field, value)

    print(f"effective config: search {config.search.type} "
          f"({NATIVE[args.search]}), iterations {config.max_iterations}, "
          f"evaluator timeout {config.evaluator.timeout}s, "
          f"parallel {config.max_parallel_iterations}, "
          f"diff_based_generation {config.diff_based_generation}, "
          f"cascade {config.evaluator.cascade_evaluation}, "
          f"temperature {config.llm.models[0].temperature}, "
          f"max_tokens {config.llm.models[0].max_tokens}, "
          f"llm timeout {config.llm.models[0].timeout}s, "
          f"retries {config.llm.models[0].retries}, "
          f"proposers {[(m.name, m.weight) for m in config.llm.models]}, "
          f"database {type(config.search.database).__name__}"
          f"{ {k: getattr(config.search.database, k) for k in database_fields(args.search, args)} }")
    print(f"running {args.search} for {args.iterations} iterations")

    result = run_discovery(
        evaluator=str(evaluator_path),
        initial_program=str(program),
        config=config,
        search=args.search,
        iterations=args.iterations,
        output_dir=str(args.out),
        system_prompt=instructions,
        cleanup=False,
    )
    print("\n=== result ===")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
