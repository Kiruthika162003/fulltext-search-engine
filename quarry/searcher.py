"""The searcher: clauses become candidate sets, candidates become ranks.

Search runs in two acts. Matching walks the query tree against one
segment: required clauses intersect, prohibited clauses subtract,
bare clauses union into the candidates and remember themselves for
scoring, phrases prove adjacency before admitting anyone. Ranking
then scores each surviving document with BM25 summed over the
scoring clauses, using the segment's own statistics, and returns
hits sorted by score with ties broken by doc id so the same index
always answers in the same order. Tombstoned documents are dropped
after matching and before ranking, which keeps the algebra clean
and makes the delete's cost visible exactly once. The searcher
analyzes query text with the field's own analyzer, closing the
loop the tokenizer's docstring opened: one pipeline, both sides.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid
from quarry.postings import difference, intersect, phrase_docs, union
from quarry.query import Clause, Query
from quarry.scoring import TermStats, bm25_term
from quarry.segment import Segment


@dataclass(frozen=True)
class Hit:
    doc: int
    score: float


def _clause_docs(segment: Segment, clause: Clause) -> list[int]:
    declared = segment.schema.get(clause.field)
    if clause.kind == "phrase":
        if declared.kind != "text":
            raise Invalid(
                f"{clause.field} is {declared.kind}; phrases need text"
            )
        terms = declared.analyzer.terms(clause.text)
        if not terms:
            return []
        lists = []
        for term in terms:
            held = segment.postings_for(clause.field, term)
            if held is None:
                return []
            lists.append(held)
        return phrase_docs(lists)
    if declared.kind == "text":
        terms = declared.analyzer.terms(clause.text)
        docs: list[int] = []
        for term in terms:
            held = segment.postings_for(clause.field, term)
            if held is not None:
                docs = union(docs, held.docs())
        return docs
    held = segment.postings_for(clause.field, clause.text)
    return held.docs() if held is not None else []


def _scoring_terms(segment: Segment, clause: Clause) -> list[tuple[str, str]]:
    declared = segment.schema.get(clause.field)
    if declared.kind != "text":
        return []
    return [
        (clause.field, term)
        for term in declared.analyzer.terms(clause.text)
    ]


def match_group(segment: Segment, group: tuple[Clause, ...]) -> list[int]:
    candidates: list[int] | None = None
    optional: list[int] = []
    saw_optional = False
    for clause in group:
        if clause.prohibited:
            continue
        docs = _clause_docs(segment, clause)
        if clause.required or clause.kind == "phrase":
            candidates = (
                docs if candidates is None else intersect(candidates, docs)
            )
        else:
            saw_optional = True
            optional = union(optional, docs)
    if candidates is None:
        candidates = optional
    elif saw_optional:
        candidates = intersect(candidates, union(optional, candidates))
    for clause in group:
        if clause.prohibited:
            candidates = difference(
                candidates, _clause_docs(segment, clause)
            )
    return candidates


def search(segment: Segment, query: Query, limit: int = 10) -> list[Hit]:
    if limit <= 0:
        raise Invalid("a search that wants no results should not run")
    matched: list[int] = []
    for group in query.groups:
        matched = union(matched, match_group(segment, group))
    matched = [doc for doc in matched if segment.is_live(doc)]
    scoring: list[tuple[str, str]] = []
    for group in query.groups:
        for clause in group:
            if not clause.prohibited:
                scoring.extend(_scoring_terms(segment, clause))
    seen: set[tuple[str, str]] = set()
    unique_terms = []
    for row in scoring:
        if row not in seen:
            seen.add(row)
            unique_terms.append(row)
    hits = []
    for doc in matched:
        score = 0.0
        for field_name, term in unique_terms:
            held = segment.postings_for(field_name, term)
            if held is None:
                continue
            posting = held.find(doc)
            if posting is None:
                continue
            stats = TermStats(
                term=term,
                document_frequency=held.document_frequency(),
                corpus_docs=segment.doc_count(),
            )
            score += bm25_term(
                stats,
                posting.frequency,
                length=segment.field_length(field_name, doc),
                average_length=segment.average_field_length(field_name),
            )
        hits.append(Hit(doc=doc, score=round(score, 6)))
    hits.sort(key=lambda hit: (-hit.score, hit.doc))
    return hits[:limit]
