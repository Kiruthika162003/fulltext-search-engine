"""Multi-segment search: one question, every segment, one honest ranking.

A query against a segmented index must behave as if the index were
one piece, and the trap is statistics: each segment's idf sees only
its own documents, so the same term scores differently in different
segments and the merged ranking silently favours whichever segment
is smallest. The fix is global statistics: document frequencies and
lengths are summed across segments first, every per-segment scorer
is handed the same corpus-wide numbers, and only then do the hits
merge. Results carry external ids, not addresses, so callers never
learn which segment answered, and the pagination contract is
offset-free: page tokens name the last score and id seen, which
stays correct even if a flush lands between pages.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid
from quarry.query import Query
from quarry.scoring import TermStats, bm25_term
from quarry.searcher import match_group
from quarry.writer import Index


@dataclass(frozen=True)
class RankedHit:
    external: int
    score: float


@dataclass(frozen=True)
class Page:
    hits: tuple[RankedHit, ...]
    token: tuple[float, int] | None


@dataclass(frozen=True)
class CorpusStats:
    total_docs: int
    document_frequency: dict[str, int]
    total_length: dict[str, int]

    def average_length(self, field_name: str) -> float:
        if self.total_docs == 0:
            return 0.0
        return self.total_length.get(field_name, 0) / self.total_docs


def gather_stats(index: Index, terms: list[tuple[str, str]]) -> CorpusStats:
    total_docs = 0
    frequencies: dict[str, int] = {}
    lengths: dict[str, int] = {}
    for segment in index.segments:
        total_docs += segment.doc_count()
        for field_name, lengths_held in segment.lengths.items():
            lengths[field_name] = lengths.get(field_name, 0) + sum(
                lengths_held
            )
        for field_name, term in terms:
            held = segment.postings_for(field_name, term)
            if held is not None:
                key = f"{field_name}\x00{term}"
                frequencies[key] = (
                    frequencies.get(key, 0) + held.document_frequency()
                )
    return CorpusStats(
        total_docs=total_docs,
        document_frequency=frequencies,
        total_length=lengths,
    )


def search_index(
    index: Index,
    query: Query,
    limit: int = 10,
    after: tuple[float, int] | None = None,
) -> Page:
    if limit <= 0:
        raise Invalid("a search that wants no results should not run")
    terms: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for group in query.groups:
        for clause in group:
            if clause.prohibited:
                continue
            declared = index.schema.get(clause.field)
            if declared.kind != "text":
                continue
            for term in declared.analyzer.terms(clause.text):
                row = (clause.field, term)
                if row not in seen:
                    seen.add(row)
                    terms.append(row)
    stats = gather_stats(index, terms)
    ranked: list[RankedHit] = []
    for segment in index.segments:
        matched: list[int] = []
        for group in query.groups:
            for doc in match_group(segment, group):
                if doc not in matched:
                    matched.append(doc)
        for doc in matched:
            if not segment.is_live(doc):
                continue
            score = 0.0
            for field_name, term in terms:
                held = segment.postings_for(field_name, term)
                if held is None:
                    continue
                posting = held.find(doc)
                if posting is None:
                    continue
                key = f"{field_name}\x00{term}"
                score += bm25_term(
                    TermStats(
                        term=term,
                        document_frequency=stats.document_frequency[key],
                        corpus_docs=stats.total_docs,
                    ),
                    posting.frequency,
                    length=segment.field_length(field_name, doc),
                    average_length=stats.average_length(field_name),
                )
            ranked.append(
                RankedHit(
                    external=index.external_id(segment.name, doc),
                    score=round(score, 6),
                )
            )
    ranked.sort(key=lambda hit: (-hit.score, hit.external))
    if after is not None:
        boundary_score, boundary_id = after
        ranked = [
            hit
            for hit in ranked
            if (-hit.score, hit.external) > (-boundary_score, boundary_id)
        ]
    page = ranked[:limit]
    token = (
        (page[-1].score, page[-1].external)
        if len(ranked) > limit
        else None
    )
    return Page(hits=tuple(page), token=token)
