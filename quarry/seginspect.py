"""The segment inspector: one segment, examined until it confesses.

When a query behaves strangely the suspect is usually one
segment, and the inspector is how it gets questioned: the shape
summary counts documents live and dead with byte-free honesty,
the hot terms list shows which postings dominate the segment's
weight, the field profile says how much of each field's text the
segment holds, and the posting histogram buckets list lengths so
a segment full of one-document terms announces its serial-number
problem on sight. Everything reads from the sealed structures
without touching them, and every number states its unit, because
an inspector whose output needs a decoder ring gets replaced by
guessing.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid
from quarry.segment import Segment


@dataclass(frozen=True)
class HotTerm:
    field: str
    term: str
    documents: int
    occurrences: int


def shape_summary(segment: Segment) -> str:
    dead = len(segment.tombstones)
    return (
        f"{segment.name}: {segment.live_count()} live + {dead} dead "
        f"= {segment.doc_count()} documents, "
        f"{len(segment.postings)} distinct field-terms"
    )


def hot_terms(segment: Segment, limit: int = 5) -> list[HotTerm]:
    if limit <= 0:
        raise Invalid("a hot list with no rows should not print")
    rows = []
    for (field_name, term), postings in segment.postings.items():
        occurrences = sum(
            posting.frequency for posting in postings.rows
        )
        rows.append(
            HotTerm(
                field=field_name,
                term=term,
                documents=postings.document_frequency(),
                occurrences=occurrences,
            )
        )
    rows.sort(
        key=lambda held: (-held.occurrences, held.field, held.term)
    )
    return rows[:limit]


def field_profile(segment: Segment) -> str:
    lines = []
    for field_name in sorted(segment.lengths):
        total = sum(segment.lengths[field_name])
        average = (
            total / segment.doc_count() if segment.doc_count() else 0
        )
        lines.append(
            f"{field_name}: {total} terms total, "
            f"{average:.1f} terms per document"
        )
    return "\n".join(lines) if lines else "no text fields indexed"


def posting_histogram(segment: Segment) -> dict[str, int]:
    """List lengths bucketed: the serial-number problem shows here."""
    buckets = {"1 doc": 0, "2-10 docs": 0, "11-100 docs": 0, "100+ docs": 0}
    for postings in segment.postings.values():
        count = postings.document_frequency()
        if count == 1:
            buckets["1 doc"] += 1
        elif count <= 10:
            buckets["2-10 docs"] += 1
        elif count <= 100:
            buckets["11-100 docs"] += 1
        else:
            buckets["100+ docs"] += 1
    return buckets


def interrogate(segment: Segment) -> str:
    lines = [shape_summary(segment)]
    lines.append("hot terms:")
    for held in hot_terms(segment):
        lines.append(
            f"  {held.field}:{held.term} in {held.documents} doc(s), "
            f"{held.occurrences} occurrence(s)"
        )
    lines.append("fields:")
    for row in field_profile(segment).splitlines():
        lines.append(f"  {row}")
    histogram = posting_histogram(segment)
    lines.append("posting list sizes:")
    for bucket, count in histogram.items():
        lines.append(f"  {bucket}: {count} term(s)")
    singles = histogram["1 doc"]
    total_terms = sum(histogram.values())
    if total_terms and singles / total_terms > 0.8:
        lines.append(
            f"NOTE: {singles} of {total_terms} terms appear in one "
            f"document; this segment smells of serial numbers"
        )
    return "\n".join(lines)
