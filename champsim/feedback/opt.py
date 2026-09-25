"""OPT feedback: how far a candidate's LLC decisions are from Belady's MIN.

Reads the access log DPC4-ChampSim writes for sampled LLC sets when run with
`--opt-log <file>` (one line per reference and per fill in those sets), runs
Belady's MIN per set on the same reference stream, and reports:

- MIN misses against the candidate's misses on the sampled sets (ROI only),
  with and without bypass, and the headroom that leaves;
- every eviction the candidate made on a full set, judged against the line
  MIN would have evicted from the candidate's own set contents at that moment,
  and classified when they differ;
- with `--parent <report or log>`, the same figures for the parent design and
  the change from parent to child, so a design step's effect is read off
  directly.

MIN is decided per set, so on the sampled sets it is exact for this stream. It
bounds misses on the stream the candidate produced, not IPC. The stream is
replayed from the start of the run so MIN is warm at the ROI; only ROI
references and fills are counted.

Log format (written by CACHE in cache.cc):
    H <sets> <ways> <block> <sampled>  once, when the log is opened: the
                                      geometry, the line size in bytes and the
                                      number of sampled sets
    S <set> ...                       the sampled sets, ascending; ChampSim
                                      draws them (the same pages per page
                                      position, fixed seed), this file only
                                      reads the list
    P <warmup>                        at each phase start: 1 warm-up, 0 ROI
    A <set> <addr> <type> <hit>       a reference: hit at tag check, or a miss
                                      once it is accepted (merged or allocated)
    F <set> <way> <addr> <evicted> <type>   a fill; way == ways is a bypass,
                                      evicted is '-' when the way held no line

Every address is the identity ChampSim's tag check compares: the byte address
with the block offset cleared. A log with an address that is not block-aligned
is refused: it was written by a ChampSim that logged raw byte addresses, and
replaying it would split one line into several. A log without the S line is
refused too: its sets were chosen by set % stride, which kept only the first
line of each 4 KB page.
"""

from __future__ import annotations

import argparse
import bisect
import json
import sys
from collections import defaultdict
from pathlib import Path

INF = float("inf")
WRITE = 3  # access_type::WRITE; writes may not bypass in ChampSim
TYPE_NAMES = {0: "LOAD", 1: "RFO", 2: "PREFETCH", 3: "WRITE", 4: "TRANSLATION"}
CLASSES = ("optimal", "should_bypass", "kept_dead", "evicted_sooner", "wrong_bypass")
GEOMETRY = ("sets", "ways", "block", "sampled")
# Two runs of one trace see almost the same sampled stream: across the four policies on the
# six quick-check slices, MIN misses differed by at most 0.12%. A larger difference means
# another trace, or a stream that diverged too far for the deltas to mean anything.
STREAM_TOLERANCE = 0.01


class Log:
    def __init__(self, sets: int, ways: int, block: int, sampled_count: int):
        self.sets, self.ways, self.block, self.sampled_count = sets, ways, block, sampled_count
        self.sampled: list[int] | None = None  # the sampled sets, ascending, from the S line
        self.events: dict[int, list] = defaultdict(list)  # set -> ordered events
        self.phases = 0


OLD_LOG = ("its sets were chosen by set % stride (page-start lines only), or it holds byte addresses; "
           "written before the sampling fix. Re-run it.")


def parse_log(path: str | Path) -> Log:
    log = None
    roi = False

    def line_addr(field: str, n: int) -> int:
        addr = int(field, 16)
        if addr % log.block:
            raise ValueError(f"{path}:{n}: address {field} is not aligned to the {log.block}-byte line")
        return addr

    def sampled_sets(fields: list[str], n: int) -> list[int]:
        sets = [int(x) for x in fields]
        if len(sets) != log.sampled_count:
            raise ValueError(f"{path}:{n}: S lists {len(sets)} sets, the header says {log.sampled_count}")
        if sets != sorted(set(sets)) or not sets or sets[0] < 0 or sets[-1] >= log.sets:
            raise ValueError(f"{path}:{n}: S must list distinct sets below {log.sets} in ascending order")
        return sets

    with open(path) as fh:
        for n, line in enumerate(fh, 1):
            f = line.split()
            if not f:
                continue
            if f[0] == "H":
                if len(f) != 5:
                    raise ValueError(f"{path}:{n}: header has {len(f) - 1} fields, not 4: {OLD_LOG}")
                block = int(f[3])
                if block < 1 or block & (block - 1):
                    raise ValueError(f"{path}:{n}: line size {block} is not a power of two")
                log = Log(int(f[1]), int(f[2]), block, int(f[4]))
            elif log is None:
                raise ValueError(f"{path}:{n}: log does not start with an H line")
            elif f[0] == "S":
                if log.sampled is not None:
                    raise ValueError(f"{path}:{n}: a second S line")
                log.sampled = sampled_sets(f[1:], n)
            elif log.sampled is None:
                raise ValueError(f"{path}:{n}: no S line before the first record: {OLD_LOG}")
            elif f[0] == "P":
                roi = f[1] == "0"
                log.phases += 1
            elif f[0] == "A":
                log.events[int(f[1])].append(("A", line_addr(f[2], n), int(f[3]), f[4] == "1", roi))
            elif f[0] == "F":
                evicted = None if f[4] == "-" else line_addr(f[4], n)
                log.events[int(f[1])].append(("F", int(f[2]), line_addr(f[3], n), evicted, int(f[5]), roi))
            else:
                raise ValueError(f"{path}:{n}: unknown record {f[0]!r}")
    if log is None:
        raise ValueError(f"{path}: empty log")
    if log.sampled is None:
        raise ValueError(f"{path}: no S line: {OLD_LOG}")
    if log.phases == 0:
        raise ValueError(f"{path}: no phase marker; nothing can be attributed to the ROI")
    sampled = set(log.sampled)
    for s in log.events:
        if s not in sampled:
            raise ValueError(f"{path}: set {s} has records but is not in the S line")
    return log


def _positions(refs: list) -> dict[int, list[int]]:
    """addr -> sorted reference indices."""
    pos: dict[int, list[int]] = defaultdict(list)
    for i, (addr, _t, _h, _r) in enumerate(refs):
        pos[addr].append(i)
    return pos


def _next_use(pos: dict[int, list[int]], addr: int, after: int) -> float:
    """Index of the first reference to addr at or after `after`, or INF."""
    lst = pos.get(addr)
    if not lst:
        return INF
    k = bisect.bisect_left(lst, after)
    return lst[k] if k < len(lst) else INF


def min_misses(refs: list, ways: int, allow_bypass: bool) -> tuple[int, int]:
    """Belady's MIN on one set's reference stream: (ROI misses, ROI bypasses).

    A miss is served by evicting the resident line whose next use is farthest,
    or, when allowed, by not allocating the incoming line if its own next use is
    farthest. Writes are always allocated, as in ChampSim.
    """
    pos = _positions(refs)
    nxt: dict[int, float] = {}  # resident addr -> next use index
    misses = bypasses = 0
    for i, (addr, typ, _hit, roi) in enumerate(refs):
        after = _next_use(pos, addr, i + 1)
        if addr in nxt:
            nxt[addr] = after
            continue
        if roi:
            misses += 1
        if len(nxt) < ways:
            nxt[addr] = after
            continue
        victim, far = max(nxt.items(), key=lambda kv: kv[1])
        if allow_bypass and typ != WRITE and after >= far:
            if roi:
                bypasses += 1
            continue
        del nxt[victim]
        nxt[addr] = after
    return misses, bypasses


def judge_fills(events: list, ways: int) -> tuple[dict, int]:
    """Classify each ROI fill on a full set against MIN's choice for the
    candidate's own contents. Returns (class counts, inconsistent fills)."""
    refs = [e[1:] for e in events if e[0] == "A"]
    pos = _positions(refs)
    contents: list[int | None] = [None] * ways
    counts = {c: 0 for c in CLASSES}
    inconsistent = 0
    seen = 0  # references processed so far; a fill's "now" is the next reference index
    for e in events:
        if e[0] == "A":
            seen += 1
            continue
        _f, way, addr, evicted, typ, roi = e
        if way >= ways:  # bypass
            if roi:
                far = max((_next_use(pos, r, seen) for r in contents if r is not None), default=INF)
                counts["optimal" if _next_use(pos, addr, seen) >= far else "wrong_bypass"] += 1
            continue
        resident = contents[way]
        if resident != evicted:
            inconsistent += 1
        if roi and evicted is not None and all(r is not None for r in contents):
            incoming = _next_use(pos, addr, seen)
            nexts = {r: _next_use(pos, r, seen) for r in contents}
            far = max(max(nexts.values()), incoming)
            victim_next = nexts[evicted] if evicted in nexts else _next_use(pos, evicted, seen)
            others_dead = any(v == INF for r, v in nexts.items() if r != evicted)
            if victim_next >= far:
                counts["optimal"] += 1
            elif typ != WRITE and incoming >= far:
                counts["should_bypass"] += 1
            elif others_dead:
                counts["kept_dead"] += 1
            else:
                counts["evicted_sooner"] += 1
        contents[way] = addr
    return counts, inconsistent


def analyse(log: Log) -> dict:
    total = {"references": 0, "candidate_misses": 0, "candidate_hits": 0,
             "min_misses": 0, "min_bypasses": 0, "min_misses_no_bypass": 0}
    decisions = {c: 0 for c in CLASSES}
    inconsistent = 0
    per_set = []
    for s, events in sorted(log.events.items()):
        refs = [e[1:] for e in events if e[0] == "A"]
        roi_refs = [r for r in refs if r[3]]
        cand_misses = sum(1 for r in roi_refs if not r[2])
        mm, mb = min_misses(refs, log.ways, allow_bypass=True)
        mn, _ = min_misses(refs, log.ways, allow_bypass=False)
        counts, bad = judge_fills(events, log.ways)
        total["references"] += len(roi_refs)
        total["candidate_misses"] += cand_misses
        total["candidate_hits"] += len(roi_refs) - cand_misses
        total["min_misses"] += mm
        total["min_bypasses"] += mb
        total["min_misses_no_bypass"] += mn
        for c in CLASSES:
            decisions[c] += counts[c]
        inconsistent += bad
        per_set.append({"set": s, "references": len(roi_refs), "candidate_misses": cand_misses,
                        "min_misses": mm, "gap": cand_misses - mm})
    cm, mm = total["candidate_misses"], total["min_misses"]
    compared = sum(decisions.values())
    summary = {
        "sampled_sets": len(log.sampled),
        "sets": log.sets, "ways": log.ways, "block": log.block, "sampled": log.sampled,
        **total,
        "candidate_miss_ratio": cm / total["references"] if total["references"] else None,
        "min_miss_ratio": mm / total["references"] if total["references"] else None,
        "gap": cm - mm,
        "headroom": (cm - mm) / cm if cm else 0.0,
        "headroom_no_bypass": (cm - total["min_misses_no_bypass"]) / cm if cm else 0.0,
        "decisions": {"compared": compared, **decisions,
                      "suboptimal_fraction": (compared - decisions["optimal"]) / compared if compared else None},
        "inconsistent_fills": inconsistent,
        "worst_sets": sorted(per_set, key=lambda d: -d["gap"])[:5],
    }
    return summary


def _rel(child: int, parent: int) -> float | None:
    return (child - parent) / parent if parent else None


def compare(child: dict, parent: dict) -> dict:
    """The parent's key figures and the change from parent to child.

    Deltas are child minus parent. The two must be the same cache and sampling;
    `comparable` is false when the streams differ by more than STREAM_TOLERANCE,
    and the deltas are then reported but mean nothing.
    """
    for side, r in (("child", child), ("parent", parent)):
        if "sampled" not in r:
            raise ValueError(f"the {side} report has no sampled-set list: {OLD_LOG}")
    differ = [k for k in GEOMETRY if child[k] != parent[k]]
    if differ:
        parts = []
        for k in differ:
            if k == "sampled":
                parts.append(f"sampled sets {len(child[k])} vs {len(parent[k])}"
                             + (", not the same sets" if len(child[k]) == len(parent[k]) else ""))
            else:
                parts.append(f"{k} {child[k]} vs {parent[k]}")
        raise ValueError("child and parent were sampled on different geometry: " + ", ".join(parts))
    refs_diff = abs(child["references"] - parent["references"]) / max(parent["references"], 1)
    min_diff = abs(child["min_misses"] - parent["min_misses"]) / max(parent["min_misses"], 1)
    comparable = refs_diff <= STREAM_TOLERANCE and min_diff <= STREAM_TOLERANCE
    reason = None if comparable else (
        f"not the same stream: references {parent['references']} vs {child['references']}, "
        f"MIN misses {parent['min_misses']} vs {child['min_misses']} (more than {100 * STREAM_TOLERANCE:.0f}% apart)"
    )

    def figures(r: dict) -> dict:
        d = r["decisions"]
        return {
            "candidate_misses": r["candidate_misses"],
            "headroom": r["headroom"],
            "headroom_no_bypass": r["headroom_no_bypass"],
            "mistakes": d["compared"] - d["optimal"],
            "decisions": {k: d[k] for k in ("compared", *CLASSES, "suboptimal_fraction")},
        }

    c, p = figures(child), figures(parent)
    delta = {k: c[k] - p[k] for k in ("candidate_misses", "headroom", "headroom_no_bypass", "mistakes")}
    delta["candidate_misses_rel"] = _rel(c["candidate_misses"], p["candidate_misses"])
    delta["decisions"] = {
        k: (None if c["decisions"][k] is None or p["decisions"][k] is None else c["decisions"][k] - p["decisions"][k])
        for k in c["decisions"]
    }
    return {
        "comparable": comparable,
        "reason": reason,
        "parent_references": parent["references"],
        "parent_min_misses": parent["min_misses"],
        "references_rel_diff": refs_diff,
        "min_misses_rel_diff": min_diff,
        "parent": p,
        "delta": delta,
    }


def load_result(path: str | Path) -> dict:
    """A run's OPT figures, from its JSON report or from its --opt-log file."""
    with open(path) as fh:
        first = fh.read(1)
    if first == "{":
        return json.loads(Path(path).read_text())
    return analyse(parse_log(path))


def report(r: dict) -> str:
    d = r["decisions"]
    lines = [f"OPT on {r['sampled_sets']} of {r['sets']} sets ({r['ways']} ways, {r['block']}-byte lines), ROI only",
             f"  references {r['references']}  candidate misses {r['candidate_misses']} ({100 * (r['candidate_miss_ratio'] or 0):.1f}%)"
             f"  MIN misses {r['min_misses']} ({100 * (r['min_miss_ratio'] or 0):.1f}%), {r['min_bypasses']} by bypass;"
             f" without bypass {r['min_misses_no_bypass']}",
             f"  headroom: {100 * r['headroom']:.1f}% of the candidate's misses are avoidable"
             f" ({100 * r['headroom_no_bypass']:.1f}% without bypass)",
             f"  evictions judged {d['compared']}: optimal {d['optimal']}, evicted a line reused sooner {d['evicted_sooner']},"
             f" kept a dead line {d['kept_dead']}, should have bypassed {d['should_bypass']}, wrong bypass {d['wrong_bypass']}"]
    if r["inconsistent_fills"]:
        lines.append(f"  WARNING: {r['inconsistent_fills']} fills disagree with the replayed contents")
    v = r.get("vs_parent")
    if v:
        p, dl = v["parent"], v["delta"]
        if v["comparable"]:
            lines.append(f"vs parent, same stream (references {v['parent_references']} vs {r['references']},"
                         f" MIN misses {v['parent_min_misses']} vs {r['min_misses']}); parent -> child")
        else:
            lines.append(f"vs parent: WARNING, {v['reason']}; the changes below mean nothing")
        rel = f", {100 * dl['candidate_misses_rel']:+.1f}%" if dl["candidate_misses_rel"] is not None else ""
        pct = lambda x: f"{100 * x:.1f}%"  # noqa: E731
        lines += [f"  candidate misses  {p['candidate_misses']:>8} -> {r['candidate_misses']:<8} ({dl['candidate_misses']:+d}{rel})",
                  f"  headroom          {pct(p['headroom']):>8} -> {pct(r['headroom']):<8}"
                  f" ({pct(p['headroom_no_bypass'])} -> {pct(r['headroom_no_bypass'])} without bypass)",
                  f"  evictions judged  {p['decisions']['compared']:>8} -> {d['compared']:<8}",
                  f"  mistakes          {p['mistakes']:>8} -> {d['compared'] - d['optimal']:<8} ({dl['mistakes']:+d})"]
        for cls, label in (("evicted_sooner", "evicted sooner"), ("kept_dead", "kept dead"),
                           ("should_bypass", "should bypass"), ("wrong_bypass", "wrong bypass")):
            lines.append(f"    {label:<16}{p['decisions'][cls]:>8} -> {d[cls]:<8} ({dl['decisions'][cls]:+d})")
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("log", help="the --opt-log file of a run")
    ap.add_argument("--parent", default=None, help="the parent design's JSON report or --opt-log file: add the change from it")
    ap.add_argument("--out", type=Path, default=None, help="write the JSON here as well")
    ap.add_argument("--report", action="store_true", help="print a summary instead of JSON")
    args = ap.parse_args()
    result = analyse(parse_log(args.log))
    if args.parent:
        result["vs_parent"] = compare(result, load_result(args.parent))
    if args.out:
        args.out.write_text(json.dumps(result, indent=1) + "\n")
    print(report(result) if args.report else json.dumps(result, indent=1))
