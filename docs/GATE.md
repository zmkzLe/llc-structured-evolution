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


## What this does and does not cover

In a run, the C++ writer never translates from scratch. It edits the C++ of the closest earlier
design based on the change in the description. The chain of edits starts from the 2.5 Pro translation
that passed (`loop/seed_cpp/`).

A candidate makes at most seven C++ calls, usually two.

Faithfulness is proven for the seed only. For every other design, the checks are that its C++
compiles and that every trace finishes. The storage and area figures are computed from the
description, so they describe the C++ only as far as the translation is faithful.
