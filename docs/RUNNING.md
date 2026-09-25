# Running the loop

Two launchers start a run. They differ only in which program proposes the designs; the
evaluator, C++ writer, guidance writer, validator, orphan guard and bucket copy are shared.

| Launcher | Search | Driver |
|---|---|---|
| `launch_arm.sh` | OpenEvolve 0.3.2 (MAP-Elites with islands) | `run_openevolve.py` |
| `launch_native.sh <search>` | a SkyDiscover native search: `adaevolve`, `evox`, `gepa_native`, `openevolve_native`, `best_of_n`, `topk`, `beam_search` | `run_native.py` |

## 1. Launch

```
cd ~/chia_loop
./launch_arm.sh              <run> <max-change> <search stop> <deadline> gs://<bucket> [driver options]
./launch_native.sh <search>  <run> <max-change> <search stop> <deadline> gs://<bucket> [driver options]
```

- `<run>`: a new name; everything goes to `~/oe_out/<run>`. An existing name is refused.
- `<max-change>`: the most canonical lines a design may change against its closest earlier
  design. `600` switches the limit off in effect, since a whole design may have at most 582.
- `<search stop>`, `<deadline>`: UTC times such as `2026-10-01T22:00:00Z`. The search stops
  proposing at the first. The validator keeps going, two designs at a time from the stop on, never
  starts one it cannot finish by the deadline, and is killed ten minutes after it.
- `gs://<bucket>`: the run is copied there every hour and once more at the end.
- Driver options go last. The ones the runs used:
  - `--ensemble MODEL=WEIGHT,...`: the proposers, one drawn per proposal;
  - `--max-tokens N`, `--llm-timeout S`: the proposer's output cap and timeout;
  - `--traces a,b --warmup N --sim N --iterations N`: for dry runs.

  The launchers already pass temperature 0.7 with no model seed, 2 retries, 2 candidates at a
  time, 2 islands with migration every 50, and a 3-hour cap per candidate.

A launch starts, detached, each with a `.pid` file and a log in the run folder:

1. the search;
2. the held-out validator;
3. with `ADAPT_EVERY` set, the guidance writer;
4. the orphan guard, which ends simulations the search leaves behind when it stops;
5. the hourly copy to the bucket.

## 2. Settings in the environment

| Variable | Default | What it sets |
|---|---|---|
| `ADAPT_EVERY` | unset (no guidance) | rewrite the guidance every K candidates; the runs used 10 |
| `A3_VERTEX_REGION` | `us-central1` | Vertex location for every model call; the Gemini 3.x models need `global` |
| `A3_CPP_MODEL` | `gemini-2.5-pro` | the model that writes, repairs and audits the C++ |
| `A3_GUIDANCE_MODEL` | `gemini-2.5-pro` | the model that writes the guidance paragraph |
| `A3_CPP_MAX_TOKENS`, `A3_CPP_TIMEOUT` | `32000`, `300` | the C++ writer's output cap (reasoning included) and timeout per call |
| `A3_REPAIRS` | `2` | repair calls when an edit does not compile, per attempt |
| `A3_AUDIT` | `1` | `0` turns off the audit call that reverts unrequested C++ changes |
| `A3_MAX_KB` | `48` | the most replacement state a design may declare, in KB |
| `A3_MAX_LINES` | three times the seed (582) | the most canonical lines a design may have |
| `CHIA_WORKERS` | cores − 2 | simulations at once per candidate |
| `EVALUATOR` | `yaml` | `launch_arm.sh` only: `ae` runs the comparison arm where the model writes the C++ itself |
| `VALIDATOR_EXTRA` | empty | extra validator options, for dry runs |

The drivers set `A3_RUN_DIR`, `A3_TRACES`, `A3_WARMUP`, `A3_SIM`, `A3_MAX_CHANGE` and `A3_RESULT`
for the evaluator's workers themselves.

## 3. The runs in `results/`

| Run | Launch | Proposers (`--ensemble`, 0.7 / 0.3) | Proposer cap | C++ and guidance model | Region | `ADAPT_EVERY` |
|---|---|---|---|---|---|---|
| `arm_adaptive` | `launch_arm.sh`* | gemini-2.5-pro / gemini-2.5-flash | 32,000 tokens, 300 s | gemini-2.5-pro | us-central1 | 10 |
| `arm_adaptive_v3` | `launch_arm.sh` | gemini-2.5-pro / gemini-2.5-flash | 32,000, 300 s | gemini-2.5-pro | us-central1 | 10 |
| `arm_A2_gemini25` | `launch_arm.sh` | gemini-2.5-pro / gemini-2.5-flash | 64,000, 900 s | gemini-2.5-pro | global | 10 |
| `arm_B2_gemini3` | `launch_arm.sh` | gemini-3.1-pro-preview / gemini-3.8-flash | 64,000, 900 s | gemini-3.1-pro-preview | global | 10 |
| `arm_adaevolve_sj4` | `launch_native.sh adaevolve` | gemini-3.1-pro-preview / gemini-3.8-flash | 64,000, 900 s | gemini-3.1-pro-preview | global | — |
| `arm_adaevolve_adapt_gemini3` | `launch_native.sh adaevolve` | gemini-3.1-pro-preview / gemini-3.8-flash | 64,000, 900 s | gemini-3.1-pro-preview | global | 10 |
| `arm_evox_gemini25` | `launch_native.sh evox` | gemini-2.5-pro / gemini-2.5-flash | 32,000, 900 s | gemini-2.5-pro | global | 10 |
| `arm_evox_gemini3` | `launch_native.sh evox` | gemini-3.1-pro-preview / gemini-3.8-flash | 64,000, 900 s | gemini-3.1-pro-preview | — | yes |
| `arm_gepa_gemini25` | `launch_native.sh gepa_native` | gemini-2.5-pro / gemini-2.5-flash | 32,000, 900 s | gemini-2.5-pro | global | 10 |
| `arm_gepa_gemini3` | `launch_native.sh gepa_native` | gemini-3.1-pro-preview / gemini-3.8-flash | 64,000, 900 s | gemini-3.1-pro-preview | — | yes |

All ten used `<max-change>` 600. These settings are read from each run's `search.log`,
`adapt.log` and call logs; "—" means the copy of the run does not record it. The C++ writer's cap
is not recorded in the run files: A2 and B2 used 64,000 tokens and 900 s, and v3 and the Sep 21
run used 32,000 and 300 s.

\* The Sep 21 run predates several fixes and a change of score (`results/README.md`); today's
code does not reproduce it exactly.

For example, run A2 again with today's code:

```
A3_VERTEX_REGION=global A3_CPP_MODEL=gemini-2.5-pro A3_GUIDANCE_MODEL=gemini-2.5-pro \
A3_CPP_MAX_TOKENS=64000 A3_CPP_TIMEOUT=900 ADAPT_EVERY=10 \
  ./launch_arm.sh my_a2 600 <stop> <deadline> gs://<bucket> \
  --ensemble gemini-2.5-pro=0.7,gemini-2.5-flash=0.3 --max-tokens 64000 --llm-timeout 900
```

and AdaEvolve on the 3.x models as `arm_adaevolve_sj4` ran:

```
A3_VERTEX_REGION=global A3_CPP_MODEL=gemini-3.1-pro-preview \
  ./launch_native.sh adaevolve my_ada 600 <stop> <deadline> gs://<bucket> \
  --ensemble gemini-3.1-pro-preview=0.7,gemini-3.8-flash=0.3 --max-tokens 64000 --llm-timeout 900
```

## 4. Watch and stop

```
O=~/oe_out/<run>
tail -f $O/search.log                        # the search
tail -f $O/validator.log                     # started / validated / superseded / deferred
wc -l < $O/yaml_run/records.jsonl            # candidates so far; the seed is the first
tail -3 $O/adapt.log                         # guidance versions, with ADAPT_EVERY
tail -3 $O/copy.log                          # "copied <time>" every hour
python3 <this repository>/results/summarize.py $O   # every table, from the files so far
```

Stop a run with `./stop_arm.sh <run>`; it refuses while a validation is running, unless given
`--kill-validation`. It stops the search, lets the orphan guard end what the search left, stops
the guidance writer and the validator with its simulations, waits for the copy loop's final copy,
checks that nothing of the run is left, and removes leftover `/tmp/chia_run_*` binaries.

At its stop time the search stops proposing but may not exit: the drivers wait for candidates
still being evaluated. Run `stop_arm.sh` once the validator is done.

## 5. A dry run

The whole launch at toy length (2 traces, 1M + 5M instructions, 3 proposals), for plumbing only;
the scores mean nothing at this length:

```
VALIDATOR_EXTRA='--traces 429.mcf-192B,483.xalancbmk-127B --warmup 1000000 --sim 5000000' \
ADAPT_EVERY=3 ./launch_arm.sh dry1 600 <20 minutes from now> <35 minutes from now> gs://<bucket> \
  --traces 429.mcf-192B,483.xalancbmk-127B --warmup 1000000 --sim 5000000 --iterations 3 \
  --ensemble gemini-2.5-pro=0.7,gemini-2.5-flash=0.3
```

Never run a dry run on a machine where a real run is live: its orphan guard ends every simulation
that is not its own validator's once its search stops.
