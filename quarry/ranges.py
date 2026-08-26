"""Range queries: numbers were indexed sorted, so ranges are walks.

Numeric fields index each value as a zero-padded string precisely
so the term dictionary's lexicographic order is the numeric order,
and a range query becomes a walk over the sorted vocabulary between
two fenceposts. Bounds are inclusive or exclusive by declaration,
an inverted range is refused instead of silently matching nothing,
and open ends are spelled None rather than magic sentinels. The
result is a sorted doc list ready for the same algebra every other
clause speaks, which is the point: a range is not a special query,
it is a big OR the vocabulary already sorted for us.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid
from quarry.postings import union
from quarry.segment import Segment

PAD = 20


def sortable(value: int) -> str:
    if value < 0:
        raise Invalid(
            "negative values need an offset encoding this index does "
            "not promise; store them shifted"
        )
    return f"{value:0{PAD}d}"


@dataclass(frozen=True)
class NumericRange:
    field: str
    low: int | None = None
    high: int | None = None
    low_inclusive: bool = True
    high_inclusive: bool = True

    def __post_init__(self) -> None:
        if self.low is None and self.high is None:
            raise Invalid(
                f"{self.field}: a range open on both ends is not a "
                f"question"
            )
        if (
            self.low is not None
            and self.high is not None
            and self.low > self.high
        ):
            raise Invalid(
                f"{self.field}: the range runs backwards, "
                f"{self.low} to {self.high}"
            )

    def admits(self, value: int) -> bool:
        if self.low is not None:
            if self.low_inclusive and value < self.low:
                return False
            if not self.low_inclusive and value <= self.low:
                return False
        if self.high is not None:
            if self.high_inclusive and value > self.high:
                return False
            if not self.high_inclusive and value >= self.high:
                return False
        return True


def range_docs(segment: Segment, asked: NumericRange) -> list[int]:
    declared = segment.schema.get(asked.field)
    if declared.kind != "numeric":
        raise Invalid(
            f"{asked.field} is {declared.kind}; ranges walk numerics"
        )
    docs: list[int] = []
    for term in segment.vocabulary(asked.field):
        value = int(term)
        if not asked.admits(value):
            continue
        held = segment.postings_for(asked.field, term)
        docs = union(docs, held.docs())
    return docs


def range_report(segment: Segment, asked: NumericRange) -> str:
    low_mark = "[" if asked.low_inclusive else "("
    high_mark = "]" if asked.high_inclusive else ")"
    low_text = "open" if asked.low is None else str(asked.low)
    high_text = "open" if asked.high is None else str(asked.high)
    count = len(range_docs(segment, asked))
    return (
        f"{asked.field} {low_mark}{low_text}, {high_text}{high_mark}: "
        f"{count} document(s)"
    )
