"""BM25: three intuitions with the arithmetic attached.

Rarer terms matter more: the idf climbs as the document frequency
falls, floored above zero so a term in every document scores tiny
instead of negative. Repetition saturates: the second mention adds
less than the first and the curve flattens toward k1 plus one, so
a keyword-stuffed page cannot buy rank linearly. Long documents
prove less per mention: the length normalisation divides the term
frequency by how much longer than average the document runs,
tempered by b, because one mention in a tweet outweighs one
mention in a novel. Every constant is a knob with a default the
literature earned, and the explain method shows each factor per
term because a ranking nobody can audit is a mood, not a metric.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from quarry.errors import Invalid

K1 = 1.2
B = 0.75


@dataclass(frozen=True)
class TermStats:
    term: str
    document_frequency: int
    corpus_docs: int

    def __post_init__(self) -> None:
        if self.document_frequency > self.corpus_docs:
            raise Invalid(
                f"{self.term} appears in more documents than exist"
            )
        if self.document_frequency <= 0:
            raise Invalid(f"{self.term} appears nowhere; nothing to score")

    def idf(self) -> float:
        top = self.corpus_docs - self.document_frequency + 0.5
        bottom = self.document_frequency + 0.5
        return math.log(1.0 + top / bottom)


def saturation(frequency: int, length: int, average_length: float,
               k1: float = K1, b: float = B) -> float:
    if frequency <= 0:
        return 0.0
    if average_length <= 0:
        raise Invalid("an average length of zero means an empty corpus")
    length_share = length / average_length
    normaliser = k1 * (1.0 - b + b * length_share)
    return frequency * (k1 + 1.0) / (frequency + normaliser)


def bm25_term(stats: TermStats, frequency: int, length: int,
              average_length: float, k1: float = K1, b: float = B) -> float:
    return stats.idf() * saturation(
        frequency, length, average_length, k1=k1, b=b
    )


@dataclass(frozen=True)
class Factor:
    term: str
    idf: float
    tf_part: float
    contribution: float

    def line(self) -> str:
        return (
            f"{self.term}: idf {self.idf:.3f} x saturation "
            f"{self.tf_part:.3f} = {self.contribution:.3f}"
        )


def explain(
    per_term: list[tuple[TermStats, int]],
    length: int,
    average_length: float,
    k1: float = K1,
    b: float = B,
) -> tuple[float, list[Factor]]:
    factors = []
    total = 0.0
    for stats, frequency in per_term:
        idf = stats.idf()
        tf_part = saturation(
            frequency, length, average_length, k1=k1, b=b
        )
        contribution = idf * tf_part
        total += contribution
        factors.append(
            Factor(
                term=stats.term,
                idf=round(idf, 6),
                tf_part=round(tf_part, 6),
                contribution=round(contribution, 6),
            )
        )
    return round(total, 6), factors
