"""More like this: the document is the query, after a diet.

Finding similar documents means turning one document into a query,
and the diet is the whole design: common terms say nothing about
similarity, the document's rarest terms say almost everything, so
the seed document's terms rank by idf and only the top few carry
into the query. The floor exists on the other side too, terms
appearing in just one document are the seed's fingerprints, serial
numbers and typos that match nothing else by construction and
waste query breath. The seed itself is excluded from results
because a similarity engine whose best answer is "this document
resembles itself" is technically correct in the way that gets a
feature turned off. The selected terms ride along in the response
so when the similars look wrong, the first debugging question,
what query did it actually run, is already answered.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid, Missing
from quarry.multisearch import search_index
from quarry.query import Clause, Query
from quarry.scoring import TermStats
from quarry.writer import Index

TOP_TERMS = 5
FINGERPRINT_FLOOR = 2


@dataclass(frozen=True)
class SimilarHit:
    external: int
    score: float


@dataclass(frozen=True)
class Likeness:
    seed: int
    query_terms: tuple[str, ...]
    similars: tuple[SimilarHit, ...]
    fingerprints_dropped: tuple[str, ...]


def _seed_terms(
    index: Index, external: int, field_name: str
) -> dict[str, int]:
    if external not in index.locations:
        raise Missing(f"no document with id {external}")
    segment_name, local = index.locations[external]
    segment = next(
        held for held in index.segments if held.name == segment_name
    )
    counts: dict[str, int] = {}
    for (held_field, term), postings in segment.postings.items():
        if held_field != field_name:
            continue
        posting = postings.find(local)
        if posting is not None:
            counts[term] = posting.frequency
    return counts


def more_like_this(
    index: Index,
    external: int,
    field_name: str,
    top_terms: int = TOP_TERMS,
    limit: int = 5,
) -> Likeness:
    if top_terms <= 0 or limit <= 0:
        raise Invalid("a likeness needs terms to ask and room to answer")
    index.flush()
    seed_counts = _seed_terms(index, external, field_name)
    if not seed_counts:
        raise Invalid(
            f"doc {external} holds no terms in {field_name}; nothing "
            f"to be like"
        )
    total_docs = sum(
        segment.doc_count() for segment in index.segments
    )
    scored = []
    fingerprints = []
    for term in seed_counts:
        document_frequency = sum(
            held.document_frequency()
            for segment in index.segments
            if (held := segment.postings_for(field_name, term))
            is not None
        )
        if document_frequency < FINGERPRINT_FLOOR:
            fingerprints.append(term)
            continue
        stats = TermStats(
            term=term,
            document_frequency=document_frequency,
            corpus_docs=total_docs,
        )
        scored.append((stats.idf(), term))
    scored.sort(key=lambda row: (-row[0], row[1]))
    chosen = tuple(term for _, term in scored[:top_terms])
    if not chosen:
        raise Invalid(
            f"every term in doc {external} is a fingerprint; the "
            f"document is only like itself"
        )
    query = Query(
        groups=(
            tuple(
                Clause(kind="term", field=field_name, text=term)
                for term in chosen
            ),
        )
    )
    page = search_index(index, query, limit=limit + 1)
    similars = tuple(
        SimilarHit(external=hit.external, score=hit.score)
        for hit in page.hits
        if hit.external != external
    )[:limit]
    return Likeness(
        seed=external,
        query_terms=chosen,
        similars=similars,
        fingerprints_dropped=tuple(sorted(fingerprints)),
    )
