"""Span queries: order and distance as first-class constraints.

A phrase is the strictest span, adjacent and ordered, but the
useful middle ground is wider: near(error, timeout, 3) should
match a timeout three words from its error in either order,
and before(cause, effect, 5) should insist on the order while
allowing the gap. Spans are resolved per document from the
positions the postings already store, walking both position
lists in one pass per pair, and every match reports the exact
window that satisfied it, because a span match that cannot show
its window is indistinguishable from a bug. Distance is
measured between word positions with adjacency at one, the same
arithmetic the phrase machinery uses, so tightening a near to
distance one and demanding order gives back exactly the phrase
semantics rather than a near-copy with different off-by-ones.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid
from quarry.segment import Segment
from quarry.tokenize import Analyzer


@dataclass(frozen=True)
class SpanMatch:
    doc: int
    left_position: int
    right_position: int

    def window(self) -> int:
        return abs(self.right_position - self.left_position)

    def line(self) -> str:
        return (
            f"doc {self.doc}: positions {self.left_position} and "
            f"{self.right_position}, {self.window()} apart"
        )


def _positions(
    segment: Segment,
    analyzer: Analyzer,
    field_name: str,
    word: str,
) -> dict[int, tuple[int, ...]]:
    terms = analyzer.terms(word)
    if not terms:
        raise Invalid(
            f"{word!r} analyzed to nothing; a span over a stopword "
            f"constrains nothing"
        )
    postings = segment.postings.get((field_name, terms[0]))
    if postings is None:
        return {}
    return {row.doc: row.positions for row in postings.rows}


def _closest_pair(
    lefts: tuple[int, ...],
    rights: tuple[int, ...],
    ordered: bool,
) -> tuple[int, int] | None:
    best: tuple[int, int] | None = None
    best_gap: int | None = None
    for left in lefts:
        for right in rights:
            if ordered and right <= left:
                continue
            gap = abs(right - left)
            if gap == 0:
                continue
            if best_gap is None or gap < best_gap:
                best_gap = gap
                best = (left, right)
    return best


def _span(
    segment: Segment,
    analyzer: Analyzer,
    field_name: str,
    first: str,
    second: str,
    distance: int,
    ordered: bool,
) -> list[SpanMatch]:
    if distance < 1:
        raise Invalid(
            "a distance under one means the same word twice; spans "
            "start at adjacency"
        )
    left_map = _positions(segment, analyzer, field_name, first)
    right_map = _positions(segment, analyzer, field_name, second)
    matches = []
    for doc in sorted(set(left_map) & set(right_map)):
        if doc in segment.tombstones:
            continue
        pair = _closest_pair(
            left_map[doc], right_map[doc], ordered=ordered
        )
        if pair is None:
            continue
        left, right = pair
        if abs(right - left) <= distance:
            matches.append(
                SpanMatch(
                    doc=doc,
                    left_position=left,
                    right_position=right,
                )
            )
    return matches


def near(
    segment: Segment,
    analyzer: Analyzer,
    field_name: str,
    first: str,
    second: str,
    distance: int,
) -> list[SpanMatch]:
    """Either order, at most distance apart."""
    return _span(
        segment,
        analyzer,
        field_name,
        first,
        second,
        distance,
        ordered=False,
    )


def before(
    segment: Segment,
    analyzer: Analyzer,
    field_name: str,
    first: str,
    second: str,
    distance: int,
) -> list[SpanMatch]:
    """First strictly before second, at most distance apart."""
    return _span(
        segment,
        analyzer,
        field_name,
        first,
        second,
        distance,
        ordered=True,
    )


def phrase_via_spans(
    segment: Segment,
    analyzer: Analyzer,
    field_name: str,
    first: str,
    second: str,
) -> list[int]:
    """before() at distance one is the two-word phrase, by design."""
    return [
        match.doc
        for match in before(
            segment, analyzer, field_name, first, second, distance=1
        )
    ]
