# The translation check ("the gate")

The loop assumes a design's YAML describes the C++ that runs. Before a model was used to write C++
in a run, it had to show that on the seed. From the Mockingjay description alone, with the word
meanings and LRU as an interface example but no Mockingjay code, it writes a ChampSim module.
That module and our Mockingjay port then run the same traces with the OPT log on all 4,096 LLC
sets. The log records every LLC reference and, for every fill, the way chosen or a bypass. Identical
logs and identical cycle counts mean identical decisions. The tool is `loop/translation_check.py`.

Our port was checked separately against the authors' Mockingjay code, by replaying the ChampSim
calls it received through their code: all 17,058 evictions were identical at this cache's size
(4,096 × 12). The bypass rule was compared by reading, and by a replay at 2,048 × 16 (402 bypasses
identical); the replay at 4,096 × 12 exercised no bypass.

## Gemini 2.5 Pro (passed 2026-09-19)

- **Three fresh translations** at 1M + 5M instructions on 429.mcf-192B, 483.xalancbmk-127B and
  450.soplex-247B: 799,908 / 343,144 / 254,497 log lines, **0 differing**, cycles identical, no
  repair. Two of the three replies were byte-identical, so there were two distinct translations.
- **Both distinct translations at 10M + 50M** on seven traces (mcf, xalancbmk, soplex, milc, lbm,
  xz_s-2302B, GemsFDTD-1491B): **25,970,760 log lines, 0 differing**, cycles identical, each.
- The logs were deleted after the pass; these figures are from the check's reports.

## Gemini 3.1 Pro preview (passed 2026-09-23)

- **Three fresh translations** at 1M + 5M on the same three traces: 799,908 / 343,144 / 254,497
  log lines, **0 differing**, cycles identical, no repair. Translations 1 and 3 are identical and 2
  differs, so again two distinct translations.
- The seven-trace check at 10M + 50M was not run for 3.1 Pro.
- Evidence: `results/gate/gemini-3.1-pro_2026-09-23/` (each translation's reply, C++, build output
  and report).

## What this does and does not cover

In a run, the C++ writer never translates from scratch. It edits the C++ of the closest earlier
design for the change in the description. The chain of edits starts from the 2.5 Pro translation
that passed (`loop/seed_cpp/`).
- **If the edit does not compile,** the compiler's messages go back to the model for up to two
  repair calls.
- **If it still does not compile,** a second attempt edits the seed's validated C++ instead, again
  with up to two repairs.
- **If that fails too,** the candidate is discarded as `cpp_failed` and the seed's C++ is restored.
- **Once an edit builds,** an audit call reverts any change the description did not ask for. Its
  result is kept only if it builds and changes fewer lines than the edit, and more than none.

A candidate makes at most seven C++ calls, usually two.

Faithfulness is proven for the seed only. For every other design, the checks are that its C++
compiles and that every trace finishes. The storage and area figures are computed from the
description, so they describe the C++ only as far as the translation is faithful.
