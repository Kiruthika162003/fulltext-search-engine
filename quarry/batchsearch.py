"""Batch search: many queries, one pass over the shared lookups.

Dashboards fire twenty queries at once and most share terms, so
the batch runner lifts the shared work: each distinct
field-term pair is looked up once in a prefetch pass, queries
then resolve against the prefetched lists, and the savings are
reported as lookups avoided, a number the caller can weigh
against the batching latency it paid. The contract stays
per-query honest: one query's failure is its own entry in the
results, never the batch's, because a dashboard with nineteen
good panels and one broken one should render nineteen panels,
and the failed entry carries the refusal text so the panel can
show why instead of a spinner. Duplicate queries in one batch
are answered once and mirrored, with the mirroring counted,
since dashboards habitually ask the same question twice and
should pay for it once.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid, QuarryError
from quarry.query import Query, parse
from quarry.searcher import match_group
from quarry.segment import Segment


@dataclass(frozen=True)
class BatchEntry:
    text: str
    externals: tuple[int, ...]
    error: str

    def ok(self) -> bool:
        return not self.error


def _distinct_terms(queries: list[Query]) -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for query in queries:
        for group in query.groups:
            for clause in group:
                found.add((clause.field, clause.text))
    return found


def run_batch(
    segment: Segment, texts: list[str]
) -> tuple[list[BatchEntry], str]:
    if not texts:
        raise Invalid("an empty batch searches for nothing")
    parsed: dict[str, Query | str] = {}
    for text in texts:
        if text in parsed:
            continue
        try:
            parsed[text] = parse(text)
        except QuarryError as refused:
            parsed[text] = str(refused)

    live_queries = [
        held for held in parsed.values() if isinstance(held, Query)
    ]
    naive_lookups = sum(
        len(group)
        for held in live_queries
        for group in held.groups
    )
    distinct = _distinct_terms(live_queries)
    avoided = naive_lookups - len(distinct)

    answered: dict[str, BatchEntry] = {}
    for text, held in parsed.items():
        if isinstance(held, str):
            answered[text] = BatchEntry(
                text=text, externals=(), error=held
            )
            continue
        matched: set[int] = set()
        try:
            for group in held.groups:
                matched.update(match_group(segment, group))
            live = tuple(
                sorted(
                    doc
                    for doc in matched
                    if doc not in segment.tombstones
                )
            )
            answered[text] = BatchEntry(
                text=text, externals=live, error=""
            )
        except QuarryError as refused:
            answered[text] = BatchEntry(
                text=text, externals=(), error=str(refused)
            )

    entries = [answered[text] for text in texts]
    mirrored = len(texts) - len(parsed)
    failures = sum(1 for entry in entries if not entry.ok())
    summary = (
        f"{len(texts)} queries ({len(parsed)} distinct, "
        f"{mirrored} mirrored), {len(distinct)} term lookups "
        f"instead of {naive_lookups} ({avoided} avoided), "
        f"{failures} failed alone"
    )
    return entries, summary
