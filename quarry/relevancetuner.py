"""Tuning k1 and b against judgments instead of against folklore.

The BM25 constants shipped as folklore, 1.2 and 0.75, are decent
defaults and wrong for somebody, and the only honest way to move
them is to measure: a grid of candidate pairs, each scored
against human judgments over real queries, winner chosen by mean
reciprocal rank with ties going to the folklore values so nobody
churns constants for a rounding error. The tuner scores with the
same bm25_term the engine uses, not a reimplementation, because
a tuner that models the scorer instead of calling it optimizes a
rumor. The report shows every cell, not just the winner, since
the shape of the grid says whether the optimum is a plateau to
stand on or a spike to distrust.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid
from quarry.scoring import K1, B, TermStats, bm25_term

K1_GRID = (0.8, 1.2, 1.6, 2.0)
B_GRID = (0.25, 0.5, 0.75, 1.0)


@dataclass(frozen=True)
class TinyCorpus:
    """Term frequencies and lengths, enough to score honestly."""

    frequencies: tuple[dict[str, int], ...]

    def __post_init__(self) -> None:
        if not self.frequencies:
            raise Invalid("a corpus of nothing cannot be tuned")

    def length(self, doc: int) -> int:
        return sum(self.frequencies[doc].values())

    def average_length(self) -> float:
        total = sum(
            self.length(doc) for doc in range(len(self.frequencies))
        )
        return total / len(self.frequencies)

    def stats(self, term: str) -> TermStats:
        containing = sum(
            1 for held in self.frequencies if term in held
        )
        return TermStats(
            term=term,
            document_frequency=containing,
            corpus_docs=len(self.frequencies),
        )

    def rank(
        self, terms: list[str], k1: float, b: float
    ) -> list[int]:
        average = self.average_length()
        scored = []
        for doc, held in enumerate(self.frequencies):
            score = 0.0
            for term in terms:
                frequency = held.get(term, 0)
                if frequency == 0:
                    continue
                score += bm25_term(
                    self.stats(term),
                    frequency,
                    self.length(doc),
                    average,
                    k1=k1,
                    b=b,
                )
            if score > 0.0:
                scored.append((doc, score))
        scored.sort(key=lambda pair: (-pair[1], pair[0]))
        return [doc for doc, _ in scored]


@dataclass(frozen=True)
class Judgment:
    terms: tuple[str, ...]
    relevant: frozenset[int]


@dataclass(frozen=True)
class Cell:
    k1: float
    b: float
    mrr: float

    def line(self) -> str:
        return f"k1={self.k1} b={self.b}: mrr={self.mrr}"


def _mrr(
    corpus: TinyCorpus,
    judgments: tuple[Judgment, ...],
    k1: float,
    b: float,
) -> float:
    total = 0.0
    for judgment in judgments:
        ranked = corpus.rank(list(judgment.terms), k1=k1, b=b)
        for position, doc in enumerate(ranked, start=1):
            if doc in judgment.relevant:
                total += 1.0 / position
                break
    return round(total / len(judgments), 4)


def tune(
    corpus: TinyCorpus, judgments: tuple[Judgment, ...]
) -> tuple[Cell, list[Cell]]:
    if not judgments:
        raise Invalid(
            "tuning without judgments optimizes toward nothing"
        )
    cells = [
        Cell(k1=k1, b=b, mrr=_mrr(corpus, judgments, k1, b))
        for k1 in K1_GRID
        for b in B_GRID
    ]
    best = max(
        cells,
        key=lambda cell: (
            cell.mrr,
            cell.k1 == K1 and cell.b == B,
            -abs(cell.k1 - K1) - abs(cell.b - B),
        ),
    )
    return best, cells


def tuning_report(best: Cell, cells: list[Cell]) -> str:
    lines = [cell.line() for cell in cells]
    plateau = sum(1 for cell in cells if cell.mrr == best.mrr)
    shape = (
        "a plateau to stand on"
        if plateau > 1
        else "a spike to distrust"
    )
    lines.append(
        f"winner: {best.line()} ({plateau} cell(s) tie: {shape})"
    )
    return "\n".join(lines)
