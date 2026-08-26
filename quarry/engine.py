"""The engine: one front door, everything behind it already tested.

The pieces compose here and nowhere else: the writer owns the
documents, the multi-searcher ranks with global statistics, the
highlighter builds snippets from stored text, the fuzzy index
learns the vocabulary at flush time, and maintenance merges on the
policy's schedule. The engine's job is to be boring: parse the
query once, fan out, assemble a response object whose fields are
what a caller actually renders, and keep the counters that answer
"what has this index been doing all day". The one decision made at
this level is when to suggest: a correction rides along only when
the query found fewer than the suggestion floor, because a page of
good results with a did-you-mean on top reads as doubt.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.fuzzy import FuzzyIndex, did_you_mean
from quarry.highlight import snippet
from quarry.merge import maintain
from quarry.multisearch import search_index
from quarry.query import parse
from quarry.schema import Schema
from quarry.writer import Index

SUGGESTION_FLOOR = 3


@dataclass(frozen=True)
class Rendered:
    external: int
    score: float
    snippets: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Response:
    query: str
    canonical: str
    hits: tuple[Rendered, ...]
    total_matched: int
    suggestion: str | None
    token: tuple[float, int] | None


@dataclass
class Engine:
    schema: Schema
    index: Index = None
    vocabulary: FuzzyIndex = field(default_factory=FuzzyIndex)
    queries_served: int = 0
    suggestions_offered: int = 0

    def __post_init__(self) -> None:
        if self.index is None:
            self.index = Index(schema=self.schema)

    def add(self, document: dict[str, object]) -> int:
        return self.index.add(document)

    def delete(self, external: int) -> str:
        return self.index.delete(external)

    def commit(self) -> list[str]:
        """Flush, learn the new vocabulary, and run maintenance."""
        segment = self.index.flush()
        if segment is not None:
            for (field_name, term), held in segment.postings.items():
                declared = self.schema.get(field_name)
                if declared.kind == "text":
                    self.vocabulary.admit(
                        term, weight=held.document_frequency()
                    )
        return maintain(self.index)

    def search(
        self,
        text: str,
        limit: int = 10,
        after: tuple[float, int] | None = None,
        snippet_fields: tuple[str, ...] = (),
    ) -> Response:
        self.queries_served += 1
        query = parse(text)
        page = search_index(self.index, query, limit=limit, after=after)
        terms: set[str] = set()
        for group in query.groups:
            for clause in group:
                if clause.prohibited:
                    continue
                declared = self.schema.get(clause.field)
                if declared.kind == "text":
                    terms |= set(declared.analyzer.terms(clause.text))
        rendered = []
        for hit in page.hits:
            document = self.index.document(hit.external)
            made = []
            for field_name in snippet_fields:
                declared = self.schema.get(field_name)
                if declared.kind != "text" or field_name not in document:
                    continue
                made.append(
                    (
                        field_name,
                        snippet(
                            str(document[field_name]),
                            declared.analyzer,
                            terms,
                        ),
                    )
                )
            rendered.append(
                Rendered(
                    external=hit.external,
                    score=hit.score,
                    snippets=tuple(made),
                )
            )
        suggestion = None
        if len(page.hits) < SUGGESTION_FLOOR:
            for group in query.groups:
                for clause in group:
                    if clause.kind != "term" or clause.prohibited:
                        continue
                    declared = self.schema.get(clause.field)
                    if declared.kind != "text":
                        continue
                    for term in declared.analyzer.terms(clause.text):
                        offered = did_you_mean(self.vocabulary, term)
                        if offered is not None:
                            suggestion = text.replace(clause.text, offered)
                            break
                    if suggestion:
                        break
                if suggestion:
                    break
        if suggestion is not None:
            self.suggestions_offered += 1
        return Response(
            query=text,
            canonical=query.canonical(),
            hits=tuple(rendered),
            total_matched=len(page.hits),
            suggestion=suggestion,
            token=page.token,
        )

    def daybook(self) -> str:
        return (
            f"{self.queries_served} queries served, "
            f"{self.suggestions_offered} corrections offered, "
            f"{self.index.searchable_count()} documents searchable "
            f"across {len(self.index.segments)} segment(s), "
            f"{self.vocabulary.vocabulary_size()} terms known"
        )
