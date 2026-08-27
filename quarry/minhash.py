"""MinHash sketches: set similarity at sketch price, error included.

Comparing every document pair by full term sets is quadratic in
a currency nobody has, and MinHash is the classic discount: a
sketch keeps, for each of k seeded hash functions, the minimum
hash any member produced, and the share of positions where two
sketches agree estimates the Jaccard similarity of the full
sets. The module states the machinery's terms: sketches must
share their width to compare, because agreement across
different widths is numerology; the estimate carries its
standard error, one over the square root of the width, so a
16-hash sketch confessing plus-or-minus a quarter cannot be
mistaken for a measurement; and the self-test measures the
estimate against true Jaccard on known sets, since a sketch
trusted without calibration is a rumor with a decimal point.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from quarry.errors import Invalid

DEFAULT_WIDTH = 64


def _hash_member(seed: int, member: str) -> int:
    digest = hashlib.sha256(
        f"{seed}|{member}".encode()
    ).digest()
    return int.from_bytes(digest[:8], "big")


@dataclass(frozen=True)
class MinHashSketch:
    width: int
    minima: tuple[int, ...]

    def agreement(self, other: MinHashSketch) -> float:
        if self.width != other.width:
            raise Invalid(
                f"widths {self.width} and {other.width} do not "
                f"compare; agreement across widths is numerology"
            )
        matched = sum(
            1
            for left, right in zip(
                self.minima, other.minima, strict=True
            )
            if left == right
        )
        return round(matched / self.width, 4)

    def standard_error(self) -> float:
        return round(1.0 / (self.width**0.5), 4)

    def estimate_line(self, other: MinHashSketch) -> str:
        estimate = self.agreement(other)
        error = self.standard_error()
        return (
            f"similarity ~{estimate} +/- {error} "
            f"({self.width} hashes); an estimate, not a "
            f"measurement"
        )


def sketch(
    members: set[str], width: int = DEFAULT_WIDTH
) -> MinHashSketch:
    if not members:
        raise Invalid(
            "an empty set sketches nothing and would claim "
            "similarity to everything"
        )
    if width < 16:
        raise Invalid(
            f"a width of {width} confesses an error past a "
            f"quarter; sixteen is the floor"
        )
    minima = tuple(
        min(_hash_member(seed, member) for member in members)
        for seed in range(width)
    )
    return MinHashSketch(width=width, minima=minima)


def true_jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    if not union:
        raise Invalid("Jaccard of two empty sets is undefined")
    return round(len(left & right) / len(union), 4)


def calibration_report(
    left: set[str], right: set[str], width: int = DEFAULT_WIDTH
) -> str:
    truth = true_jaccard(left, right)
    estimate = sketch(left, width).agreement(sketch(right, width))
    error = abs(estimate - truth)
    bound = 2.0 / (width**0.5)
    verdict = (
        "inside two standard errors"
        if error <= bound
        else "OUTSIDE two standard errors; check the hashing"
    )
    return (
        f"true {truth}, estimated {estimate}, off by "
        f"{round(error, 4)} against a bound of {round(bound, 4)}: "
        f"{verdict}"
    )
