# Results

`runs/` holds ten runs, all from September 21–23, 2026, one Google Cloud VM each. Every file each
run wrote is included except the `.pid` files and simulation leftovers; `docs/OUTPUTS.md` says
what each file is. `summarize.py` recomputes every table from these files, and `SUMMARY.md` is its
output.

All runs share the machine (DPC4 single core, 3 MB LLC, no prefetchers), the traces (17 training
at 20M + 50M, all 33 for validation at 50M + 100M), the seed (Mockingjay) and the evaluator. They
differ in the search, the models, the settings and
their length, so no two rows are a controlled comparison.

| Folder | Search | Models (proposers) | Code | Notes |
|---|---|---|---|---|
| `arm_adaptive` | OpenEvolve + guidance | Gemini 2.5 Pro / Flash | an earlier version (September 21) | Stopped after 12.5 h to fix the issues listed below. It was scored against LRU, not Mockingjay; that ranks designs identically, since the two differ by a constant factor. `summarize.py` re-expresses it against Mockingjay. |
| `arm_adaptive_v3` | OpenEvolve + guidance | Gemini 2.5 Pro / Flash | `loop/` before two later fixes | Proposer cap 32,000 tokens. Its best design, `311521127a79`, has the highest held-out score of all runs. |
| `arm_A2_gemini25` | OpenEvolve + guidance | Gemini 2.5 Pro / Flash | `loop/`, with the C++ writer at 64,000 tokens / 900 s | matched with B2: only the models differ |
| `arm_B2_gemini3` | OpenEvolve + guidance | Gemini 3.1 Pro / 3.8 Flash | the same as A2 | 16 of 69 proposer calls rate-limited: several runs shared the project's quota |
| `arm_adaevolve_sj4` | AdaEvolve | Gemini 3.1 Pro / 3.8 Flash | `loop/` (native launcher) | no guidance |
| `arm_adaevolve_adapt_gemini3` | AdaEvolve + guidance | Gemini 3.1 Pro / 3.8 Flash | `loop/` (native launcher) | |
| `arm_evox_gemini25`, `arm_evox_gemini3` | EvoX + guidance | 2.5 / 3.x | `loop/` (native launcher) | most candidates refused: see below |
| `arm_gepa_gemini25`, `arm_gepa_gemini3` | GEPA + guidance | 2.5 / 3.x | `loop/` (native launcher) | most candidates refused: see below |

`arm_evox_gemini3` and `arm_gepa_gemini3` hold the records, logs and validations only. The exact
commit each SkyDiscover run used is not recorded in its files; `loop/` is the latest version of
that code.

**Fixed after `arm_adaptive`:**
- workers only saw the feedback of the first 100 programs in the database;
- new words were registered before the storage and step checks;
- the guidance offered words of designs never scored;
- three prompt lines referred to outside work.

**Fixed after `arm_adaptive_v3`:**
- a design copied to the other island lost its feedback;
- the C++ writer gave up on a rate-limited call instead of waiting.

**Why most EvoX and GEPA candidates were refused.** In `arm_evox_gemini25` and
`arm_gepa_gemini25`, about three quarters of the candidates either had a placeholder instead of a
design in the design section (216 and 148), or had no section markers at all (168 and 124). The
OpenEvolve runs had no placeholder designs and at most one reply missing a section. Under
SkyDiscover the candidate is cut out of the reply from the first section marker it contains, so a
reply that restates the format before its answer is cut at the restatement. That is the likely
cause, not yet confirmed against the raw replies. These runs therefore scored very few designs (3 and 10 distinct), and say little about EvoX or GEPA
as search algorithms.

**How to read the numbers.** Every score is IPC relative to Mockingjay on the same trace, as a
geometric mean over traces. Each run is one sample of a noisy search, and the gains found are under
1%. Every held-out 95% bootstrap interval includes zero. For evolved designs, the C++ was only
required to build and finish every trace. The description's faithfulness to the C++ was proven for
the seed (`docs/GATE.md`), and the storage and area figures are computed from the description.

`gate/` holds the evidence of the translation check for Gemini 3.1 Pro (`docs/GATE.md`).
