"""Percolation: the queries sit still and the documents walk past.

An alert subscription is search inverted: hundreds of stored
queries, one new document, and the question of which subscriptions
fire. Testing every stored query against every arriving document is
the quadratic road, so stored queries are indexed by their required
terms: a query cannot match a document that lacks one of its
positive terms, and the term-to-query map shrinks the candidate set
to queries sharing at least one term with the document before any
full evaluation runs. The full check then runs the real matcher on
a one-document throwaway segment, because an approximation that
fires false alerts trains people to delete their subscriptions.
The skipped count rides along on every percolation, keeping the
shortcut auditable the way every shortcut here has to be.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid, Missing
from quarry.query import Query, parse
from quarry.schema import Schema
from quarry.searcher import match_group
from quarry.segment import SegmentBuilder


@dataclass(frozen=True)
class Subscription:
    name: str
    text: str
    query: Query


@dataclass(frozen=True)
class Percolation:
    fired: tuple[str, ...]
    candidates_checked: int
    skipped_by_the_map: int


@dataclass
class Percolator:
    schema: Schema
    subscriptions: dict[str, Subscription] = field(default_factory=dict)
    by_term: dict[str, set[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.schema.sealed:
            raise Invalid("seal the schema before percolating against it")

    def subscribe(self, name: str, text: str) -> Subscription:
        if name in self.subscriptions:
            raise Invalid(f"{name} is already subscribed")
        query = parse(text)
        held = Subscription(name=name, text=text, query=query)
        anchors = self._anchor_terms(query)
        if not anchors:
            raise Invalid(
                f"{name} has no positive text term to index under; a "
                f"subscription must be findable before it can fire"
            )
        for term in anchors:
            self.by_term.setdefault(term, set()).add(name)
        self.subscriptions[name] = held
        return held

    def unsubscribe(self, name: str) -> None:
        if name not in self.subscriptions:
            raise Missing(f"no subscription named {name}")
        held = self.subscriptions.pop(name)
        for term in self._anchor_terms(held.query):
            names = self.by_term.get(term)
            if names is not None:
                names.discard(name)
                if not names:
                    del self.by_term[term]

    def _anchor_terms(self, query: Query) -> set[str]:
        anchors: set[str] = set()
        for group in query.groups:
            for clause in group:
                if clause.prohibited:
                    continue
                declared = self.schema.get(clause.field)
                if declared.kind == "text":
                    anchors.update(declared.analyzer.terms(clause.text))
                elif declared.kind == "keyword":
                    anchors.add(f"\x00{clause.field}:{clause.text}")
        return anchors

    def _document_terms(self, document: dict[str, object]) -> set[str]:
        terms: set[str] = set()
        for name, value in document.items():
            declared = self.schema.get(name)
            if declared.kind == "text":
                terms.update(declared.analyzer.terms(str(value)))
            elif declared.kind == "keyword":
                terms.add(f"\x00{name}:{value}")
        return terms

    def percolate(self, document: dict[str, object]) -> Percolation:
        present = self._document_terms(document)
        candidates: set[str] = set()
        for term in present:
            candidates.update(self.by_term.get(term, set()))
        skipped = len(self.subscriptions) - len(candidates)
        if not candidates:
            return Percolation(
                fired=(), candidates_checked=0, skipped_by_the_map=skipped
            )
        builder = SegmentBuilder(schema=self.schema)
        builder.add(document)
        segment = builder.seal("percolation")
        fired = []
        for name in sorted(candidates):
            held = self.subscriptions[name]
            if any(
                match_group(segment, group) for group in held.query.groups
            ):
                fired.append(name)
        return Percolation(
            fired=tuple(fired),
            candidates_checked=len(candidates),
            skipped_by_the_map=skipped,
        )
