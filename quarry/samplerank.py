"""Sampled ranking review: a defensible verdict from a slice of traffic.

Judging every query is unaffordable and judging none is blind,
so the review samples deterministically: a query joins the
sample when the hash of its canonical form lands under the
sampling share, which keeps the same queries in the sample
across days so trends are trends and not resampling noise. Each
sampled query gets a verdict from its judged results, good,
mixed, or bad by the share of relevant documents in the top
three, and the period report aggregates with the sample size
and the confession that it is a sample, stating the margin as
plus or minus one over root n rather than pretending census
precision. The floor rule refuses verdicts from under thirty
sampled queries, because below that the margin swallows the
signal and the report would be a horoscope with a denominator.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from quarry.errors import Invalid

SAMPLE_FLOOR = 30
TOP_WINDOW = 3


def in_sample(canonical: str, share: float) -> bool:
    if not 0.0 < share <= 1.0:
        raise Invalid(
            f"a sampling share of {share} samples nothing or "
            f"everything twice"
        )
    digest = hashlib.sha256(canonical.encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:4], "big") / 2**32
    return bucket < share


@dataclass(frozen=True)
class QueryVerdict:
    canonical: str
    relevant_in_top: int

    def __post_init__(self) -> None:
        if not 0 <= self.relevant_in_top <= TOP_WINDOW:
            raise Invalid(
                f"{self.canonical!r}: {self.relevant_in_top} "
                f"relevant of a top {TOP_WINDOW} is arithmetic "
                f"that cannot happen"
            )

    def grade(self) -> str:
        if self.relevant_in_top == TOP_WINDOW:
            return "good"
        if self.relevant_in_top == 0:
            return "bad"
        return "mixed"


@dataclass
class SampledReview:
    share: float
    verdicts: list[QueryVerdict] = field(default_factory=list)
    skipped: int = 0

    def offer(
        self, canonical: str, relevant_in_top: int
    ) -> bool:
        if in_sample(canonical, self.share):
            self.verdicts.append(
                QueryVerdict(
                    canonical=canonical,
                    relevant_in_top=relevant_in_top,
                )
            )
            return True
        self.skipped += 1
        return False

    def report(self) -> str:
        n = len(self.verdicts)
        if n < SAMPLE_FLOOR:
            return (
                f"{n} of {SAMPLE_FLOOR} sampled queries needed; "
                f"below the floor the margin swallows the signal"
            )
        good = sum(
            1 for held in self.verdicts if held.grade() == "good"
        )
        bad = sum(
            1 for held in self.verdicts if held.grade() == "bad"
        )
        mixed = n - good - bad
        margin = round(1.0 / (n**0.5), 3)
        good_share = round(good / n, 3)
        return (
            f"sampled {n} queries (skipped {self.skipped}): "
            f"{good} good, {mixed} mixed, {bad} bad; good share "
            f"{good_share} +/- {margin}. This is a sample, not a "
            f"census"
        )

    def worst(self, top_n: int = 5) -> list[str]:
        ranked = sorted(
            self.verdicts,
            key=lambda held: (held.relevant_in_top, held.canonical),
        )
        return [
            f"{held.canonical}: {held.relevant_in_top} of "
            f"{TOP_WINDOW} relevant"
            for held in ranked[:top_n]
        ]
