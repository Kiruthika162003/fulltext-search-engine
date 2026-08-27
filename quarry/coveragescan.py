"""Coverage scanning: the documents no query can ever find.

Every index accumulates orphans, documents that exist but are
unreachable: a body that analyzed to nothing because it was all
stopwords or punctuation, a document whose only terms are
unique typos nobody will ever type, a record whose text landed
in stored fields that answer no queries. The scan walks every
live document and grades its reachability: rich documents
carry several searchable terms, thin ones hang by one or two,
and orphans carry none, with the reason attached because the
fix differs, an all-stopword title needs a schema change while
an empty body needs an ingest fix. The scan reports counts and
the worst offenders by name, and the orphan share is the
number to alarm on, since orphans are storage that pays rent
in bytes and never once answers a query.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid
from quarry.segment import Segment

THIN_THRESHOLD = 2


@dataclass(frozen=True)
class Reachability:
    doc: int
    searchable_terms: int
    grade: str
    reason: str

    def line(self) -> str:
        return (
            f"doc {self.doc}: {self.grade} "
            f"({self.searchable_terms} searchable term(s); "
            f"{self.reason})"
        )


def scan_segment(segment: Segment) -> list[Reachability]:
    per_doc: dict[int, int] = {}
    for (_, _), postings in segment.postings.items():
        for row in postings.rows:
            per_doc[row.doc] = per_doc.get(row.doc, 0) + 1
    out = []
    for doc in range(segment.doc_count()):
        if doc in segment.tombstones:
            continue
        count = per_doc.get(doc, 0)
        if count == 0:
            grade, reason = (
                "ORPHAN",
                "no searchable terms; analyzed to nothing or all "
                "stored freight",
            )
        elif count <= THIN_THRESHOLD:
            grade, reason = (
                "thin",
                "hangs by a term or two; one edit away from orphan",
            )
        else:
            grade, reason = ("rich", "healthy")
        out.append(
            Reachability(
                doc=doc,
                searchable_terms=count,
                grade=grade,
                reason=reason,
            )
        )
    return out


def coverage_report(segment: Segment) -> str:
    graded = scan_segment(segment)
    if not graded:
        raise Invalid(
            f"{segment.name}: no live documents; coverage of "
            f"nothing is nothing"
        )
    orphans = [held for held in graded if held.grade == "ORPHAN"]
    thin = [held for held in graded if held.grade == "thin"]
    share = len(orphans) / len(graded)
    lines = [
        f"{segment.name}: {len(graded)} live, "
        f"{len(orphans)} orphan(s) ({share:.0%}), "
        f"{len(thin)} thin"
    ]
    for held in orphans:
        lines.append(f"  {held.line()}")
    for held in thin[:3]:
        lines.append(f"  {held.line()}")
    if orphans:
        lines.append(
            "orphans pay rent in bytes and never answer a query; "
            "fix ingest or schema, then reindex them"
        )
    return "\n".join(lines)


def orphan_share(segment: Segment) -> float:
    graded = scan_segment(segment)
    if not graded:
        raise Invalid(
            f"{segment.name}: no live documents; a share of "
            f"nothing is nothing"
        )
    orphans = sum(1 for held in graded if held.grade == "ORPHAN")
    return round(orphans / len(graded), 4)
