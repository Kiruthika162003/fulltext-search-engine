"""A micro-benchmark harness that refuses to flatter itself.

Timing search code lies three ways: the first run pays import
and cache-warming costs the steady state never sees, the mean
is dragged by one GC pause into slander, and a single number
hides whether the thing is stable at all. The harness answers
each lie by construction: declared warmup runs execute and are
discarded, the reported center is the median because medians
shrug at outliers, and the spread ships beside it as the ratio
of the slowest kept run to the fastest, with a stability
verdict at the declared tolerance. Comparisons between two
subjects require the same run counts, refuse to declare a
winner inside the noise band, and report the margin as a
ratio, never a percentage of a percentage, because benchmark
prose is where arithmetic goes to be misquoted.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from quarry.errors import Invalid

NOISE_BAND = 1.1


@dataclass(frozen=True)
class BenchResult:
    label: str
    runs: int
    median_us: float
    spread: float

    def stable(self) -> bool:
        return self.spread <= 3.0

    def line(self) -> str:
        verdict = (
            "stable" if self.stable() else "NOISY, distrust this"
        )
        return (
            f"{self.label}: median {self.median_us}us over "
            f"{self.runs} runs, spread {self.spread}x ({verdict})"
        )


def measure(
    label: str,
    subject: Callable[[], object],
    runs: int = 30,
    warmup: int = 5,
) -> BenchResult:
    if runs < 5:
        raise Invalid(
            f"{runs} run(s) cannot produce a median worth quoting; "
            f"five is the floor"
        )
    if warmup < 1:
        raise Invalid(
            "at least one warmup run; the first run pays costs "
            "the steady state never sees"
        )
    for _ in range(warmup):
        subject()
    kept: list[float] = []
    for _ in range(runs):
        start = time.perf_counter()
        subject()
        kept.append(time.perf_counter() - start)
    kept.sort()
    middle = len(kept) // 2
    if len(kept) % 2 == 1:
        median = kept[middle]
    else:
        median = (kept[middle - 1] + kept[middle]) / 2
    fastest = max(kept[0], 1e-9)
    spread = round(kept[-1] / fastest, 2)
    return BenchResult(
        label=label,
        runs=runs,
        median_us=round(median * 1_000_000, 2),
        spread=spread,
    )


def compare(left: BenchResult, right: BenchResult) -> str:
    if left.runs != right.runs:
        raise Invalid(
            f"{left.runs} vs {right.runs} runs; comparing unequal "
            f"efforts flatters whoever ran less"
        )
    slower, faster = (
        (left, right)
        if left.median_us > right.median_us
        else (right, left)
    )
    if faster.median_us <= 0:
        raise Invalid("a zero median means the clock blinked")
    ratio = round(slower.median_us / faster.median_us, 2)
    if ratio <= NOISE_BAND:
        return (
            f"no winner: {left.label} and {right.label} sit inside "
            f"the {NOISE_BAND}x noise band ({ratio}x apart)"
        )
    if not (left.stable() and right.stable()):
        return (
            f"{faster.label} looks {ratio}x faster but at least "
            f"one side is noisy; rerun before quoting this"
        )
    return (
        f"{faster.label} is {ratio}x faster than {slower.label} "
        f"({faster.median_us}us vs {slower.median_us}us)"
    )
