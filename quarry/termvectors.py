"""Term vectors: one document's index entries, read back out.

The inverted index answers which documents hold this term; the
term vector answers the transpose, which terms this document
holds, with frequencies and positions, and the honest way to
build it is to read the same postings the searcher reads rather
than re-analyzing the stored text, because a vector built by
re-analysis can disagree with the index it claims to describe
whenever the analyzer changed between then and now. Vectors
power the workhorses: more-like-this seeds, keyword extraction
by frequency against corpus rarity, and document similarity by
cosine over shared terms, all of which are honest exactly as
far as the vector is, which is why it comes from the postings.
Tombstoned documents refuse a vector, since describing a
deleted document's content is how deleted content leaks.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from quarry.errors import Invalid
from quarry.segment import Segment


@dataclass(frozen=True)
class VectorEntry:
    field_name: str
    term: str
    frequency: int
    positions: tuple[int, ...]


def term_vector(
    segment: Segment, doc: int
) -> list[VectorEntry]:
    if doc in segment.tombstones:
        raise Invalid(
            f"doc {doc} is deleted; describing its content is how "
            f"deleted content leaks"
        )
    if doc >= segment.doc_count():
        raise Invalid(
            f"doc {doc} does not exist; the segment holds "
            f"{segment.doc_count()}"
        )
    entries = []
    for (field_name, term), postings in sorted(
        segment.postings.items()
    ):
        for row in postings.rows:
            if row.doc == doc:
                entries.append(
                    VectorEntry(
                        field_name=field_name,
                        term=term,
                        frequency=row.frequency,
                        positions=row.positions,
                    )
                )
                break
    return entries


def keywords(
    segment: Segment, doc: int, top_n: int = 5
) -> list[str]:
    """Frequent here, rare everywhere else: the classic ratio."""
    if top_n <= 0:
        raise Invalid("zero keywords describe nothing")
    scored = []
    for entry in term_vector(segment, doc):
        postings = segment.postings[(entry.field_name, entry.term)]
        spread = postings.document_frequency()
        score = entry.frequency / spread
        scored.append((score, entry.term))
    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    seen: set[str] = set()
    out = []
    for _, term in scored:
        if term not in seen:
            seen.add(term)
            out.append(term)
        if len(out) == top_n:
            break
    return out


def cosine_similarity(
    segment: Segment, left: int, right: int
) -> float:
    left_vector = {
        (entry.field_name, entry.term): entry.frequency
        for entry in term_vector(segment, left)
    }
    right_vector = {
        (entry.field_name, entry.term): entry.frequency
        for entry in term_vector(segment, right)
    }
    if not left_vector or not right_vector:
        raise Invalid(
            "cosine over an empty vector divides by zero; one of "
            "these documents indexed no terms"
        )
    shared = set(left_vector) & set(right_vector)
    top = sum(
        left_vector[key] * right_vector[key] for key in shared
    )
    left_norm = math.sqrt(
        sum(value**2 for value in left_vector.values())
    )
    right_norm = math.sqrt(
        sum(value**2 for value in right_vector.values())
    )
    return round(top / (left_norm * right_norm), 4)


def vector_page(segment: Segment, doc: int) -> str:
    entries = term_vector(segment, doc)
    if not entries:
        return f"doc {doc}: indexed no searchable terms"
    lines = [f"doc {doc}:"]
    for entry in entries:
        listed = ", ".join(str(p) for p in entry.positions)
        lines.append(
            f"  {entry.field_name}:{entry.term} x"
            f"{entry.frequency} at [{listed}]"
        )
    return "\n".join(lines)
