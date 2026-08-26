"""Facets: the sidebar counts are a second query answered honestly.

A facet answers "of the documents that matched, how many carry each
value of this field", and the honesty rules are all about what the
counts include. Counts run over every matching document, not the
returned page, because a sidebar that only counts page one lies
harder the deeper the corpus goes. Tombstoned documents never
count. Ties in the top-N break alphabetically so the sidebar is
stable across identical queries. And the tail is never silently
dropped: the report says how many distinct values exist beyond the
N shown, since "and 40 more" is the difference between a summary
and a keyhole. Numeric facets bucket by declared edges, and a value
outside every bucket lands in a named overflow rather than
vanishing.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

from quarry.errors import Invalid
from quarry.query import Query
from quarry.searcher import match_group
from quarry.writer import Index


@dataclass(frozen=True)
class FacetCount:
    value: str
    count: int


@dataclass(frozen=True)
class FacetResult:
    field: str
    top: tuple[FacetCount, ...]
    distinct_beyond: int
    matched_docs: int

    def line(self) -> str:
        shown = ", ".join(
            f"{held.value} ({held.count})" for held in self.top
        )
        tail = (
            f" and {self.distinct_beyond} more"
            if self.distinct_beyond
            else ""
        )
        return f"{self.field}: {shown}{tail}"


def _matching_pairs(index: Index, query: Query) -> list[tuple[str, int]]:
    pairs = []
    for segment in index.segments:
        matched: set[int] = set()
        for group in query.groups:
            matched.update(match_group(segment, group))
        for doc in matched:
            if segment.is_live(doc):
                pairs.append((segment.name, doc))
    return pairs


def facet(
    index: Index, query: Query, field_name: str, top_n: int = 5
) -> FacetResult:
    if top_n <= 0:
        raise Invalid("a facet with no rows is a blank sidebar")
    declared = index.schema.get(field_name)
    if declared.kind not in ("keyword", "numeric"):
        raise Invalid(
            f"{field_name} is {declared.kind}; facets count keywords "
            f"and numerics, not free text"
        )
    counts: dict[str, int] = {}
    pairs = _matching_pairs(index, query)
    for segment_name, doc in pairs:
        segment = next(
            held for held in index.segments if held.name == segment_name
        )
        value = segment.stored[doc].get(field_name)
        if value is None:
            continue
        shown = str(value)
        counts[shown] = counts.get(shown, 0) + 1
    ranked = sorted(counts.items(), key=lambda row: (-row[1], row[0]))
    top = tuple(
        FacetCount(value=value, count=count)
        for value, count in ranked[:top_n]
    )
    return FacetResult(
        field=field_name,
        top=top,
        distinct_beyond=max(0, len(ranked) - top_n),
        matched_docs=len(pairs),
    )


@dataclass(frozen=True)
class Bucket:
    label: str
    low: int
    high: int


def numeric_facet(
    index: Index,
    query: Query,
    field_name: str,
    edges: tuple[int, ...],
) -> list[FacetCount]:
    """Bucket counts over [edge, next_edge) with a named overflow."""
    if len(edges) < 2:
        raise Invalid("bucketing needs at least two edges")
    if list(edges) != sorted(set(edges)):
        raise Invalid("edges must be strictly increasing")
    declared = index.schema.get(field_name)
    if declared.kind != "numeric":
        raise Invalid(f"{field_name} is {declared.kind}; buckets need numbers")
    buckets = [
        Bucket(label=f"[{low}, {high})", low=low, high=high)
        for low, high in itertools.pairwise(edges)
    ]
    counts = {bucket.label: 0 for bucket in buckets}
    overflow = 0
    for segment_name, doc in _matching_pairs(index, query):
        segment = next(
            held for held in index.segments if held.name == segment_name
        )
        value = segment.stored[doc].get(field_name)
        if value is None:
            continue
        landed = False
        for bucket in buckets:
            if bucket.low <= int(value) < bucket.high:
                counts[bucket.label] += 1
                landed = True
                break
        if not landed:
            overflow += 1
    rows = [
        FacetCount(value=bucket.label, count=counts[bucket.label])
        for bucket in buckets
    ]
    rows.append(FacetCount(value="outside all buckets", count=overflow))
    return rows
