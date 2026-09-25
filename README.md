# Evolving cache replacement policies as structured descriptions

A loop that evolves last-level-cache (LLC) replacement policies with LLMs. The proposing model
never edits simulator code. It writes each design as a **structured description in a fixed
vocabulary** (YAML), which it may extend with precisely defined new words. A separate model call
turns the description into ChampSim C++. Each candidate gets back an explanation of *why* it
scored as it did, not only a score. Optionally, the search rewrites part of its own prompt every
10 candidates. Every new best is re-checked automatically on traces the search never sees.

The same evaluator runs under several search algorithms: OpenEvolve, and SkyDiscover's native
AdaEvolve, EvoX, GEPA, OpenEvolve, Best-of-N, Top-K and beam search.

Submitted to the 1st A3 Workshop CHIA Hackathon 2026. Authors: Khoi Le, Sayanti Jana, Matthew
DeLorenzo, Jeyavijayan Rajendran, Paul Gratz (Texas A&M University).

## How it works

| Step | What it does | Code |
|---|---|---|
| **Propose** | A Gemini ensemble (Pro 70% / Flash 30%, temperature 0.7, no seed) writes one design as YAML plus any new words, from a parent design, its feedback and, if enabled, the current guidance. Besides the seed (Mockingjay), the prompt shows LRU, SRRIP, DRRIP and SHiP written in the same vocabulary. | `loop/run_openevolve.py` (OpenEvolve), `loop/run_native.py` (SkyDiscover), `loop/evolver_prompt.py` |
| **Check** | Before any cost: both sections present; at most 582 canonical lines; new words well formed; the description validates against the vocabulary plus its declared words; at most 48 KB of declared replacement state; no redefinition of a word accepted earlier in the run. A refusal takes under a second and its reason goes back to the model. | `champsim/structure_description/`, `loop/design_evaluator.py` |
| **Translate** | A separate model edits the C++ of the closest earlier design for the change; up to 2 repairs if it does not compile, then the same from the seed's C++. An audit call reverts any change the description did not ask for. | `loop/cpp_writer.py`, `loop/seed_cpp/` |
| **Evaluate** | ChampSim, DPC4 single-core configuration (3 MB LLC, 4096 sets × 12 ways, no prefetchers), on 17 training traces at 20M warm-up + 50M instructions, in parallel. The score is the geometric mean over traces of IPC divided by Mockingjay's IPC; the seed scores 1.0. | `champsim/`, `loop/chia_llc_loop.py` |
| **Explain** | Per trace: IPC against Mockingjay, LLC MPKI, the stall profile, the policy's mistakes against Belady's optimal policy on 256 sampled sets, and the storage's area and energy from CACTI. It all goes back to the model as text. | `champsim/feedback/`, `loop/design_evaluator.py` |
| **Adapt** (optional) | Every K candidates, a writer summarises what paid off and what was refused, lists the accepted words, and one capped model call writes a guidance paragraph into every later prompt. | `loop/guidance_writer.py` |
| **Validate** | Every new best at least 0.1% above the last validated one runs on all 33 traces at 50M + 100M instructions, in its own ChampSim tree; 16 of the traces are never seen by the search. Nothing it measures goes back to the search. | `loop/heldout_validator.py` |
| **Operate** | One command starts the search, the validator, the guidance writer, an orphan guard and hourly copies to a bucket; one command stops everything cleanly. | `loop/launch_arm.sh`, `loop/launch_native.sh`, `loop/stop_arm.sh`, `loop/orphan_guard.sh` |

## Layout

```
loop/       the loop: drivers, evaluator, prompt, C++ writer, guidance writer, validator, launch scripts
champsim/   the DPC4 ChampSim fork: vocabulary and validator (structure_description/), feedback
            (feedback/), the build/run node (chia_node/), the Mockingjay port, CACTI (tools/cacti),
            the trace list (selected_traces.txt)
setup/      trace_seconds_50M100M.json (wall time per trace, for the validator)
results/    runs/ (ten runs, every file they wrote), gate/ (translation-check evidence),
            summarize.py (rebuilds every table from runs/), SUMMARY.md (its output), README.md
docs/       SETUP.md, RUNNING.md, OUTPUTS.md, GATE.md
```

## Quick start

1. **Set up a machine** as in [`docs/SETUP.md`](docs/SETUP.md): a Linux VM with Gemini through
   Vertex AI, ChampSim built twice, the 33 traces, and a Cloud Storage bucket.
2. **Launch a run** as in [`docs/RUNNING.md`](docs/RUNNING.md). OpenEvolve with adaptive guidance:
   ```
   cd ~/chia_loop
   ADAPT_EVERY=10 ./launch_arm.sh my_run 600 2026-10-01T22:00:00Z 2026-10-02T04:00:00Z gs://my-bucket \
       --ensemble gemini-2.5-pro=0.7,gemini-2.5-flash=0.3
   ```
   A SkyDiscover algorithm instead, for example AdaEvolve:
   ```
   ./launch_native.sh adaevolve my_run 600 2026-10-01T22:00:00Z 2026-10-02T04:00:00Z gs://my-bucket \
       --ensemble gemini-2.5-pro=0.7,gemini-2.5-flash=0.3
   ```
3. **Stop it** with `./stop_arm.sh my_run`.
4. **Read what it wrote** with [`docs/OUTPUTS.md`](docs/OUTPUTS.md), and tabulate it with
   `python3 results/summarize.py ~/oe_out/my_run`.

## Results

Best design of each run, chosen by its held-out score. The scores are geometric means of IPC over
Mockingjay's at 50M + 100M instructions. The full tables, with 95% bootstrap intervals, are in
[`results/SUMMARY.md`](results/SUMMARY.md); [`results/README.md`](results/README.md) says what each
run was.

| Run | Search | Proposer models | Best design | Held out (16) | All (33) | Area (22 nm) | State |
|---|---|---|---|---|---|---|---|
| `arm_adaptive_v3` | OpenEvolve + guidance | Gemini 2.5 Pro / Flash | `311521127a79` | 1.0093 | 1.0059 | 0.0394 mm² | 47.875 KB |
| `arm_A2_gemini25` | OpenEvolve + guidance | Gemini 2.5 Pro / Flash | `b88d6375ef26` | 1.0030 | 1.0026 | 0.0379 mm² | 47.375 KB |
| `arm_B2_gemini3` | OpenEvolve + guidance | Gemini 3.1 Pro / 3.8 Flash | none validated | — | — | | |
| `arm_adaevolve_sj4` | AdaEvolve | Gemini 3.1 Pro / 3.8 Flash | `90a333eded10` | 1.0051 | 1.0026 | 0.0387 mm² | 47.812 KB |
| `arm_adaevolve_adapt_gemini3` | AdaEvolve + guidance | Gemini 3.1 Pro / 3.8 Flash | none validated | — | — | | |
| `arm_evox_gemini25`, `arm_evox_gemini3` | EvoX + guidance | 2.5 / 3.x | none validated | — | — | | |
| `arm_gepa_gemini25`, `arm_gepa_gemini3` | GEPA + guidance | 2.5 / 3.x | none validated | — | — | | |

Mockingjay itself declares 47.375 KB (0.0379 mm²). "None validated" means no design beat the
0.1% bar on the training traces. Read these as observations, not established improvements:

- each run is a single sample of a noisy search, with 50–500 candidates;
- the gains are under 1%, and every held-out 95% interval includes zero;
- the runs differ in length, models and settings;
- the EvoX and GEPA runs lost most of their candidates to a mismatch between the reply format and
  how the reply was parsed (see [`results/README.md`](results/README.md)).

Faithfulness: before the runs, C++ written from the Mockingjay description alone made the same
eviction and bypass decisions as our Mockingjay port in all 4,096 LLC sets, with identical cycle
counts ([`docs/GATE.md`](docs/GATE.md)). For evolved designs, the C++ is only required to build
and to finish every trace.

## Credits and license

`loop/` builds on Sayanti Jana's CHIA loop: `run_openevolve.py`, `chia_llc_loop.py`,
`candidate.py`, `ae_evaluator.py`, `build_baseline.py`, `fidelity_probe.py` and `data/` began in
her repository, and `run_native.py`, `launch_native.sh` and `check_native.py` are hers. ChampSim is used under its own license (`champsim/LICENSE`) and is
modified here. The Mockingjay policy is ported from its authors' code. The searches use
OpenEvolve 0.3.2 and SkyDiscover. The rest of this repository does not carry a license yet.
