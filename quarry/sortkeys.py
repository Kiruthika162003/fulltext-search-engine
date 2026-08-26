"""Sorting by field: sometimes the user wants newest, not best.

Relevance is one order among several, and the sort contract has
sharp edges the API refuses to sand off. Sorting runs over every
matching document before the page cut, because sorting the top ten
by score and calling it newest-first is a lie with pagination.
Documents missing the sort field go last regardless of direction,
under the principle that absence is not a value and should never
outrank presence. Score remains the tiebreaker inside equal keys
so the order stays total and reproducible. And sorting on a text
field is refused outright: alphabetising analyzed prose sorts by
whatever token survived the pipeline, which is a surprise wearing
an ORDER BY.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid
from quarry.multisearch import RankedHit, search_index
from quarry.query import Query
from quarry.writer import Index


@dataclass(frozen=True)
class SortedHit:
    external: int
    key: object | None
    score: float


def sorted_search(
    index: Index,
    query: Query,
    by: str,
    descending: bool = False,
    limit: int = 10,
) -> list[SortedHit]:
    if limit <= 0:
        raise Invalid("a search that wants no results should not run")
    declared = index.schema.get(by)
    if declared.kind == "text":
        raise Invalid(
            f"{by} is analyzed text; alphabetising surviving tokens is "
            f"a surprise wearing an ORDER BY. Sort on keyword or "
            f"numeric fields"
        )
    if declared.kind == "stored":
        raise Invalid(
            f"{by} is stored-only; it was never indexed for anything, "
            f"sorting included"
        )
    everything: list[RankedHit] = list(
        search_index(index, query, limit=10_000_000).hits
    )
    keyed = []
    for hit in everything:
        document = index.document(hit.external)
        keyed.append(
            SortedHit(
                external=hit.external,
                key=document.get(by),
                score=hit.score,
            )
        )
    present = [hit for hit in keyed if hit.key is not None]
    absent = [hit for hit in keyed if hit.key is None]
    present.sort(key=lambda hit: (-hit.score, hit.external))
    present.sort(key=lambda hit: hit.key, reverse=descending)
    absent.sort(key=lambda hit: (-hit.score, hit.external))
    return (present + absent)[:limit]


def sort_report(hits: list[SortedHit], by: str) -> str:
    lines = [f"sorted by {by}"]
    for hit in hits:
        shown = "(absent)" if hit.key is None else str(hit.key)
        lines.append(
            f"  doc {hit.external}: {shown} (score {hit.score})"
        )
    return "\n".join(lines)
