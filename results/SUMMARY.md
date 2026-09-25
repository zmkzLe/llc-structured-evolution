## Runs

| Run | Folder | Search | Proposer models | C++ writer | Hours* | Candidates | Refused | Distinct designs scored | Best on training |
|---|---|---|---|---|---|---|---|---|---|
| OE-2.5 Sep21 | `arm_adaptive` | OpenEvolve + guidance | 2.5 Pro / 2.5 Flash | gemini-2.5-pro | 12.5 | 89 | 44 | 34 | +0.40% `2e5680038f4e` |
| OE-2.5 v3 | `arm_adaptive_v3` | OpenEvolve + guidance | 2.5 Pro / 2.5 Flash | gemini-2.5-pro | 20.6 | 176 | 111 | 55 | +0.40% `311521127a79` |
| OE-2.5 A2 | `arm_A2_gemini25` | OpenEvolve + guidance | 2.5 Pro / 2.5 Flash | gemini-2.5-pro | 15.4 | 113 | 57 | 40 | +0.54% `ea244a758864` |
| OE-3.x B2 | `arm_B2_gemini3` | OpenEvolve + guidance | 3.1 Pro / 3.8 Flash | gemini-3.1-pro-preview | 15.4 | 52 | 3 | 43 | +0.08% `d743d8dd1193` |
| Ada-3.x | `arm_adaevolve_sj4` | AdaEvolve | 3.1 Pro / 3.8 Flash | gemini-3.1-pro-preview | 17.1 | 246 | 197 | 39 | +0.47% `429a3b77e242` |
| Ada+g-3.x | `arm_adaevolve_adapt_gemini3` | AdaEvolve + guidance | 3.1 Pro / 3.8 Flash | gemini-3.1-pro-preview | 7.6 | 139 | 114 | 14 | +0.00% `c41837327dd0` |
| EvoX-2.5 | `arm_evox_gemini25` | EvoX + guidance | 2.5 Pro / 2.5 Flash | gemini-2.5-pro | 15.1 | 494 | 465 | 3 | +0.00% `c41837327dd0` |
| EvoX-3.x | `arm_evox_gemini3` | EvoX + guidance | 3.1 Pro / 3.8 Flash | gemini-3.1-pro-preview | 7.5 | 77 | 66 | 7 | +0.00% `c41837327dd0` |
| GEPA-2.5 | `arm_gepa_gemini25` | GEPA + guidance | 2.5 Pro / 2.5 Flash | gemini-2.5-pro | 15.3 | 363 | 312 | 10 | +0.00% `c41837327dd0` |
| GEPA-3.x | `arm_gepa_gemini3` | GEPA + guidance | 3.1 Pro / 3.8 Flash | gemini-3.1-pro-preview | 7.2 | 105 | 93 | 6 | +0.00% `c41837327dd0` |

*From the first candidate's start to the last one's.

## Refusals by reason

| Reason | OE-2.5 Sep21 | OE-2.5 v3 | OE-2.5 A2 | OE-3.x B2 | Ada-3.x | Ada+g-3.x | EvoX-2.5 | EvoX-3.x | GEPA-2.5 | GEPA-3.x |
|---|---|---|---|---|---|---|---|---|---|---|
| design section is not YAML (e.g. a copied placeholder) | 0 | 0 | 0 | 0 | 7 | 54 | 216 | 21 | 148 | 29 |
| reply missing a section | 1 | 0 | 0 | 0 | 18 | 36 | 168 | 38 | 124 | 48 |
| new words: not written as a list | 7 | 22 | 13 | 0 | 158 | 0 | 0 | 0 | 0 | 0 |
| other structure error | 3 | 2 | 3 | 0 | 1 | 20 | 39 | 4 | 22 | 15 |
| new word: redefines a taken name | 9 | 58 | 16 | 3 | 8 | 1 | 2 | 0 | 2 | 0 |
| new word: name too long or malformed | 3 | 18 | 14 | 0 | 0 | 0 | 5 | 0 | 0 | 0 |
| a word not allowed there, or not declared | 3 | 2 | 2 | 0 | 0 | 0 | 14 | 0 | 5 | 0 |
| design name too long or malformed | 6 | 8 | 3 | 0 | 1 | 0 | 3 | 2 | 1 | 1 |
| duplicate YAML key | 6 | 0 | 4 | 0 | 0 | 1 | 4 | 0 | 6 | 0 |
| new word: other declaration error | 4 | 0 | 0 | 0 | 2 | 1 | 11 | 1 | 1 | 0 |
| over 48 KB of state | 0 | 0 | 1 | 0 | 2 | 1 | 3 | 0 | 2 | 0 |
| procedure declared but never run | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| uses an undeclared word | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| **total** | 44 | 111 | 57 | 3 | 197 | 114 | 465 | 66 | 312 | 93 |

## Model calls and tokens

| Run | Role | Model | Calls | Input tokens | Output tokens (incl. reasoning) |
|---|---|---|---|---|---|
| OE-2.5 Sep21 | proposer | gemini-2.5-flash | 37 | 870,912 | 262,206 |
| OE-2.5 Sep21 | proposer | gemini-2.5-pro | 53 | 1,235,195 | 645,902 |
| OE-2.5 Sep21 | proposer | (rate-limited, retried) | 4 | | |
| OE-2.5 Sep21 | C++ writer | gemini-2.5-pro | 66 | 1,177,226 | 756,741 |
| OE-2.5 v3 | proposer | gemini-2.5-flash | 40 | 1,082,118 | 318,729 |
| OE-2.5 v3 | proposer | gemini-2.5-pro | 137 | 3,632,807 | 1,669,589 |
| OE-2.5 v3 | proposer | (rate-limited, retried) | 11 | | |
| OE-2.5 v3 | C++ writer | gemini-2.5-pro | 109 | 2,094,225 | 1,294,099 |
| OE-2.5 A2 | proposer | gemini-2.5-flash | 25 | 598,790 | 157,283 |
| OE-2.5 A2 | proposer | gemini-2.5-pro | 89 | 2,103,287 | 958,817 |
| OE-2.5 A2 | proposer | (rate-limited, retried) | 4 | | |
| OE-2.5 A2 | C++ writer | gemini-2.5-pro | 80 | 1,378,805 | 857,653 |
| OE-3.x B2 | proposer | gemini-3.1-pro-preview | 38 | 858,909 | 620,915 |
| OE-3.x B2 | proposer | gemini-3.8-flash | 15 | 326,684 | 378,153 |
| OE-3.x B2 | proposer | (rate-limited, retried) | 16 | | |
| OE-3.x B2 | C++ writer | gemini-3.1-pro-preview | 83 | 1,404,557 | 829,502 |
| Ada-3.x | proposer | gemini-3.1-pro-preview | 194 | 4,298,322 | 2,907,801 |
| Ada-3.x | proposer | gemini-3.8-flash | 72 | 1,581,385 | 736,235 |
| Ada-3.x | proposer | (rate-limited, retried) | 37 | | |
| Ada-3.x | C++ writer | gemini-3.1-pro-preview | 71 | 1,410,909 | 792,768 |
| Ada+g-3.x | proposer | gemini-3.1-pro-preview | 112 | 2,239,062 | 1,931,859 |
| Ada+g-3.x | proposer | gemini-3.8-flash | 35 | 715,568 | 352,412 |
| Ada+g-3.x | proposer | (rate-limited, retried) | 62 | | |
| Ada+g-3.x | C++ writer | gemini-3.1-pro-preview | 25 | 446,610 | 309,818 |
| EvoX-2.5 | proposer | gemini-2.5-flash | 152 | 3,027,886 | 2,207,760 |
| EvoX-2.5 | proposer | gemini-2.5-pro | 340 | 6,805,028 | 4,268,647 |
| EvoX-2.5 | proposer | (rate-limited, retried) | 12 | | |
| EvoX-2.5 | C++ writer | gemini-2.5-pro | 3 | 53,744 | 37,361 |
| EvoX-3.x | proposer | gemini-3.1-pro-preview | 61 | 994,791 | 1,226,519 |
| EvoX-3.x | proposer | gemini-3.8-flash | 14 | 226,600 | 103,931 |
| EvoX-3.x | proposer | (rate-limited, retried) | 21 | | |
| EvoX-3.x | C++ writer | gemini-3.1-pro-preview | 11 | 155,447 | 85,992 |
| GEPA-2.5 | proposer | gemini-2.5-flash | 114 | 1,892,252 | 1,729,995 |
| GEPA-2.5 | proposer | gemini-2.5-pro | 247 | 4,117,634 | 2,740,173 |
| GEPA-2.5 | proposer | (rate-limited, retried) | 13 | | |
| GEPA-2.5 | C++ writer | gemini-2.5-pro | 17 | 296,648 | 204,566 |
| GEPA-3.x | proposer | gemini-3.1-pro-preview | 64 | 971,441 | 1,245,208 |
| GEPA-3.x | proposer | gemini-3.8-flash | 39 | 600,740 | 301,403 |
| GEPA-3.x | proposer | (rate-limited, retried) | 15 | | |
| GEPA-3.x | C++ writer | gemini-3.1-pro-preview | 10 | 173,809 | 98,291 |

## Held-out validations (against Mockingjay, 33 traces at 50M + 100M; 95% bootstrap over traces)

| Run | Design | Score in the search | All 33 | Training 17 | Held out 16 | Held-out traces up |
|---|---|---|---|---|---|---|
| OE-2.5 Sep21 | `c8957d2b2855` | +0.16% | +0.07% [-0.80%, +0.88%] | -0.26% [-1.50%, +0.82%] | +0.41% [-0.78%, +1.58%] | 10/16 |
| OE-2.5 Sep21 | `2e5680038f4e` | +0.40% | +0.37% [+0.09%, +0.73%] | +0.39% [+0.07%, +0.84%] | +0.34% [-0.04%, +0.94%] | 8/16 |
| OE-2.5 v3 | `e10d4a832a77` | +0.24% | +0.10% [-0.62%, +0.72%] | -0.25% [-1.40%, +0.59%] | +0.48% [-0.31%, +1.31%] | 8/16 |
| OE-2.5 v3 | `311521127a79` | +0.40% | +0.59% [-0.15%, +1.32%] | +0.27% [-0.78%, +1.25%] | +0.93% [-0.05%, +1.98%] | 9/16 |
| OE-2.5 A2 | `3714da345231` | +0.18% | +0.07% [-0.05%, +0.24%] | +0.15% [-0.04%, +0.46%] | -0.02% [-0.12%, +0.05%] | 4/16 |
| OE-2.5 A2 | `b88d6375ef26` | +0.43% | +0.26% [-0.20%, +0.72%] | +0.22% [-0.07%, +0.56%] | +0.30% [-0.60%, +1.20%] | 9/16 |
| OE-2.5 A2 | `ea244a758864` | +0.54% | +0.21% [-0.22%, +0.66%] | +0.40% [+0.04%, +0.86%] | +0.02% [-0.77%, +0.78%] | 8/16 |
| Ada-3.x | `90a333eded10` | +0.25% | +0.26% [-0.65%, +1.15%] | +0.02% [-1.39%, +1.26%] | +0.51% [-0.57%, +1.74%] | 7/16 |
| Ada-3.x | `429a3b77e242` | +0.47% | +0.07% [-0.95%, +1.06%] | +0.17% [-1.26%, +1.43%] | -0.03% [-1.49%, +1.43%] | 7/16 |

## Best design per run, chosen by its held-out score

| Run | Search | Models | Design | Held out 16 | All 33 | Metadata area (22 nm) | Declared metadata |
|---|---|---|---|---|---|---|---|
| OE-2.5 Sep21 | OpenEvolve + guidance | 2.5 Pro / 2.5 Flash | `c8957d2b2855` | 1.0041 | 1.0007 | 0.0394 mm² | 47.875 KB |
| OE-2.5 v3 | OpenEvolve + guidance | 2.5 Pro / 2.5 Flash | `311521127a79` | 1.0093 | 1.0059 | 0.0394 mm² | 47.875 KB |
| OE-2.5 A2 | OpenEvolve + guidance | 2.5 Pro / 2.5 Flash | `b88d6375ef26` | 1.0030 | 1.0026 | 0.0379 mm² | 47.375 KB |
| OE-3.x B2 | OpenEvolve + guidance | 3.1 Pro / 3.8 Flash | only the seed was validated | 1.0000 | 1.0000 | | |
| Ada-3.x | AdaEvolve | 3.1 Pro / 3.8 Flash | `90a333eded10` | 1.0051 | 1.0026 | 0.0387 mm² | 47.812 KB |
| Ada+g-3.x | AdaEvolve + guidance | 3.1 Pro / 3.8 Flash | only the seed was validated | 1.0000 | 1.0000 | | |
| EvoX-2.5 | EvoX + guidance | 2.5 Pro / 2.5 Flash | only the seed was validated | 1.0000 | 1.0000 | | |
| EvoX-3.x | EvoX + guidance | 3.1 Pro / 3.8 Flash | only the seed was validated | 1.0000 | 1.0000 | | |
| GEPA-2.5 | GEPA + guidance | 2.5 Pro / 2.5 Flash | only the seed was validated | 1.0000 | 1.0000 | | |
| GEPA-3.x | GEPA + guidance | 3.1 Pro / 3.8 Flash | only the seed was validated | 1.0000 | 1.0000 | | |

The seed's (Mockingjay's) IPCs at 20M + 50M are identical on all 17 training traces in every run: **True**.
