"""What a structure description may say, and one numeric definition per symbol."""

from __future__ import annotations

from enum import Enum
from typing import Union


class Scope(str, Enum):
    PER_LINE = "per_line"
    PER_SET = "per_set"
    PER_CPU = "per_cpu"
    GLOBAL = "global"


class FieldKind(str, Enum):
    COUNTER = "counter"  # unsigned, wraps
    SATURATING = "saturating"  # fwcounter, clamps
    FLAG = "flag"  # single bit
    SIGNED = "signed"  # two's complement, wraps; values are literals (or ZERO)


class InitValue(str, Enum):
    """Initial values only; concrete ints are also allowed."""

    ZERO = "ZERO"
    MAX = "MAX"  # 2^width - 1
    MAX_MINUS_1 = "MAX_MINUS_1"
    MID = "MID"  # 1 << (width-1): 512 at width 10


class Threshold(str, Enum):
    """Separate from InitValue so MID cannot be used as a threshold."""

    ZERO = "ZERO"
    MAX = "MAX"
    MAX_OVER_2 = "MAX_OVER_2"  # maximum / 2: 511 at width 10


class Extremum(str, Enum):
    MIN = "min"
    MAX = "max"
    MAX_MAGNITUDE = "max_magnitude"  # largest |value|; signed keys only


class TieBreak(str, Enum):
    FIRST = "first"  # std::min_element / max_element
    LAST = "last"
    PREFER_NEGATIVE = "prefer_negative"  # a negative beats a positive (paper); among several, the last negative or the first positive (mockingjay.cc)


class SearchSideEffect(str, Enum):
    NONE = "none"
    AGE_TO_MAX = "age_to_max"  # add (MAX - found) to every way in the set


class Comparison(str, Enum):
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    EQ = "eq"
    IS_MAX = "is_max"
    ABSENT = "absent"  # a table has no entry at the index; takes no threshold


class AccessType(str, Enum):
    LOAD = "LOAD"
    RFO = "RFO"
    PREFETCH = "PREFETCH"
    WRITE = "WRITE"
    TRANSLATION = "TRANSLATION"


class Event(str, Enum):
    ON_ACCESS = "on_access"  # every lookup; way is invalid on a miss
    ON_HIT = "on_hit"
    ON_FILL = "on_fill"  # also a bypassed fill (way == NUM_WAY), where per_line writes are skipped


class SignatureSource(str, Enum):
    IP = "ip"


class FoldBit(str, Enum):
    """x = (x << 1) | bit, in list order, before the hash."""

    HIT = "hit"  # 1 in on_hit, else 0
    PREFETCH = "prefetch"  # type == PREFETCH


class SignatureHash(str, Enum):
    NONE = "none"
    CRC3 = "crc3"  # crc3() below


class TrainOp(str, Enum):
    INCREMENT = "increment"  # by one, clamped at the table's max; an absent entry takes the max
    DECREMENT = "decrement"  # by one, clamped at 0; an absent entry takes 0
    TOWARD = "toward"  # s = min(sample * scale, max); absent takes s; else one step toward s when at least min_diff away


class SampledSets(str, Enum):
    CATEGORY_ZERO = "category_zero"  # get_set_sample_category(set) == 0; sampler set = set / rate


TICK_WIDTH = 64  # lru.h uses uint64_t; a narrower clock wraps and misorders lines
CATEGORY_BOUND = 32  # largest set sample rate (src/modules.cc)
CRC_POLYNOMIAL = 0xEDB88320  # 3988292384, mockingjay.cc CRC_HASH


def set_sample_rate(sets: int) -> int:
    """get_set_sample_rate in src/modules.cc, branch for branch."""
    if 256 <= sets < 1024:
        return 16
    if sets >= 64:
        return 8
    if sets >= 8:
        return 4
    raise ValueError(f"{sets} sets is too few to sample")


def mirror_sampled(set_index: int, sets: int, count: int) -> bool:
    """mockingjay.cc is_sampled_set: the low (log2 sets - log2 count) bits of the set equal the bits above them."""
    if count < 1 or count & (count - 1) or sets & (sets - 1) or count > sets:
        raise ValueError(f"mirror sampling needs powers of two with count <= sets, got {count} of {sets}")
    shift = count.bit_length() - 1
    mask = (1 << (sets.bit_length() - 1 - shift)) - 1
    return (set_index & mask) == ((set_index >> shift) & mask)


def crc3(x: int) -> int:
    """Three rounds of the reflected CRC-32 step, as mockingjay.cc CRC_HASH."""
    x &= (1 << 64) - 1
    for _ in range(3):
        x = (x >> 1) ^ CRC_POLYNOMIAL if x & 1 else x >> 1
    return x


def reject_bool(value) -> None:
    """bool subclasses int, so YAML `true` would silently become 1."""
    if isinstance(value, bool):
        raise ValueError(f"boolean literal {value!r} is not a value; integers and symbols only")


def max_value(width: int) -> int:
    if not isinstance(width, int) or isinstance(width, bool) or not 1 <= width <= 64:
        raise ValueError(f"width must be an integer in 1..64, got {width!r}")
    return (1 << width) - 1


def signed_range(width: int) -> tuple[int, int]:
    max_value(width)
    return -(1 << (width - 1)), (1 << (width - 1)) - 1


def resolve_init(value: Union[InitValue, str, int], width: int) -> int:
    reject_bool(value)
    if isinstance(value, int):
        return value
    sym = InitValue(value)
    if sym is InitValue.ZERO:
        return 0
    if sym is InitValue.MAX:
        return max_value(width)
    if sym is InitValue.MAX_MINUS_1:
        return max_value(width) - 1
    if sym is InitValue.MID:
        return 1 << (width - 1)
    raise AssertionError(f"unhandled InitValue {sym!r}")


def resolve_threshold(value: Union[Threshold, str, int], width: int) -> int:
    reject_bool(value)
    if isinstance(value, int):
        return value
    sym = Threshold(value)
    if sym is Threshold.ZERO:
        return 0
    if sym is Threshold.MAX:
        return max_value(width)
    if sym is Threshold.MAX_OVER_2:
        return max_value(width) // 2
    raise AssertionError(f"unhandled Threshold {sym!r}")


if __name__ == "__main__":
    widths = (1, 2, 6, 10, 64)
    print("resolve_init")
    print("  width  " + "".join(f"{s.value:>14}" for s in InitValue))
    for w in widths:
        print(f"  {w:>5}  " + "".join(f"{resolve_init(s, w):>14}" for s in InitValue))
    print()
    print("resolve_threshold")
    print("  width  " + "".join(f"{s.value:>14}" for s in Threshold))
    for w in widths:
        print(f"  {w:>5}  " + "".join(f"{resolve_threshold(s, w):>14}" for s in Threshold))
    print()
    print("  the pair that matters, at DRRIP's PSEL width of 10:")
    print(f"    MID        (init)      = {resolve_init(InitValue.MID, 10)}")
    print(f"    MAX_OVER_2 (threshold) = {resolve_threshold(Threshold.MAX_OVER_2, 10)}")
    print(f"    drrip.cc:57 tests 512 > 511 -> {512 > 511}, so followers start on BRRIP")
