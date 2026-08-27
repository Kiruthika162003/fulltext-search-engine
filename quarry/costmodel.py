"""A cost model for queries: the estimate comes from the postings.

Some queries are cheap and some walk half the index, and telling
them apart before running is what lets a scheduler be fair. The
unit here is postings touched, the honest currency of an
inverted index: a term clause costs its document frequency, an
intersection costs the smallest list involved because that is
the list a competent intersect walks, a union costs the sum of
its branches, and a phrase costs its rarest word plus a
position-check surcharge per candidate. The model is checked
against the real engine in its own eval, not trusted, and every
estimate returns a breakdown rather than a bare number, because
a total nobody can decompose is a total nobody will believe
when it is wrong.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid
from quarry.query import Query
from quarry.segment import Segment
from quarry.tokenize import Analyzer

PHRASE_SURCHARGE = 2


@dataclass(frozen=True)
class CostLine:
    label: str
    postings: int

    def line(self) -> str:
        return f"{self.label}: {self.postings}"


@dataclass(frozen=True)
class Estimate:
    lines: tuple[CostLine, ...]

    def total(self) -> int:
        return sum(held.postings for held in self.lines)

    def breakdown(self) -> str:
        rows = [held.line() for held in self.lines]
        rows.append(f"total: {self.total()} postings touched")
        return "\n".join(rows)


def _term_frequency(
    segment: Segment, analyzer: Analyzer, field_name: str, text: str
) -> int:
    terms = analyzer.terms(text)
    if not terms:
        return 0
    postings = segment.postings.get((field_name, terms[0]))
    return postings.document_frequency() if postings else 0


def _phrase_cost(
    segment: Segment, analyzer: Analyzer, field_name: str, text: str
) -> int:
    words = analyzer.terms(text)
    if not words:
        return 0
    frequencies = [
        _term_frequency(segment, analyzer, field_name, word)
        for word in words
    ]
    rarest = min(frequencies)
    if rarest == 0:
        return 0
    return rarest + rarest * PHRASE_SURCHARGE


def estimate(
    segment: Segment, analyzer: Analyzer, query: Query
) -> Estimate:
    lines: list[CostLine] = []
    for group_index, group in enumerate(query.groups):
        required: list[int] = []
        for clause in group:
            if not analyzer.terms(clause.text):
                continue
            if clause.prohibited:
                cost = _term_frequency(
                    segment, analyzer, clause.field, clause.text
                )
                lines.append(
                    CostLine(
                        label=f"-{clause.field}:{clause.text}",
                        postings=cost,
                    )
                )
                continue
            if clause.kind == "phrase":
                cost = _phrase_cost(
                    segment, analyzer, clause.field, clause.text
                )
                label = f'{clause.field}:"{clause.text}"'
            else:
                cost = _term_frequency(
                    segment, analyzer, clause.field, clause.text
                )
                label = f"{clause.field}:{clause.text}"
            if clause.required:
                required.append(cost)
                label = f"+{label}"
                lines.append(
                    CostLine(label=label, postings=cost)
                )
            else:
                lines.append(
                    CostLine(label=label, postings=cost)
                )
        if len(required) >= 2:
            smallest = min(required)
            saved = sum(required) - smallest
            lines.append(
                CostLine(
                    label=(
                        f"group {group_index}: intersection walks "
                        f"the smallest list, credit"
                    ),
                    postings=-saved,
                )
            )
    if not lines:
        raise Invalid("an empty query costs nothing and runs never")
    return Estimate(lines=tuple(lines))


def classify(held: Estimate, segment: Segment) -> str:
    live = max(segment.live_count(), 1)
    ratio = held.total() / live
    if ratio <= 1.0:
        return f"cheap: {held.total()} postings, under one per document"
    if ratio <= 3.0:
        return (
            f"moderate: {held.total()} postings, {ratio:.1f} per "
            f"live document"
        )
    return (
        f"expensive: {held.total()} postings, {ratio:.1f} per live "
        f"document; consider tightening the query"
    )
