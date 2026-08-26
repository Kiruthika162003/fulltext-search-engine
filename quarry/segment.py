"""Segments: the index grows by sealing, never by editing.

A segment is an immutable slice of the index: documents go into a
mutable builder, the builder seals into a segment, and from that
moment the segment answers queries without a lock because nothing
will ever change it. Deletes are tombstones kept beside the
segment rather than surgery inside it, so a deleted document costs
one bit until a merge rewrites the neighbourhood, and every reader
holds a consistent view for free. The builder assigns local doc
ids densely from zero, keeps field lengths because ranking needs
them, and refuses documents that do not fit the sealed schema,
since the alternative is an index that lies about its own shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Frozen, Invalid, Missing
from quarry.postings import PostingList
from quarry.schema import Schema


@dataclass
class SegmentBuilder:
    schema: Schema
    postings: dict[tuple[str, str], PostingList] = field(default_factory=dict)
    stored: list[dict[str, object]] = field(default_factory=list)
    lengths: dict[str, list[int]] = field(default_factory=dict)
    sealed: bool = False

    def __post_init__(self) -> None:
        if not self.schema.sealed:
            raise Invalid("seal the schema before building a segment")

    def add(self, document: dict[str, object]) -> int:
        if self.sealed:
            raise Frozen("this builder already sealed; open a new one")
        for name in document:
            self.schema.get(name)
        doc = len(self.stored)
        kept: dict[str, object] = {}
        for name, declared in self.schema.fields.items():
            if name not in document:
                continue
            value = document[name]
            kept[name] = value
            if declared.kind == "text":
                terms = declared.analyzer.terms(str(value))
                self.lengths.setdefault(name, [])
                while len(self.lengths[name]) < doc:
                    self.lengths[name].append(0)
                self.lengths[name].append(len(terms))
                positions: dict[str, list[int]] = {}
                for index, term in enumerate(terms):
                    positions.setdefault(term, []).append(index)
                for term, where in positions.items():
                    self._list(name, term).add(doc, tuple(where))
            elif declared.kind == "keyword":
                self._list(name, str(value)).add(doc, (0,))
            elif declared.kind == "numeric":
                if not isinstance(value, int):
                    raise Invalid(
                        f"{name} is numeric and {value!r} is not an integer"
                    )
                self._list(name, f"{value:020d}").add(doc, (0,))
        self.stored.append(kept)
        return doc

    def _list(self, field_name: str, term: str) -> PostingList:
        key = (field_name, term)
        if key not in self.postings:
            self.postings[key] = PostingList(term=term)
        return self.postings[key]

    def seal(self, name: str) -> Segment:
        if self.sealed:
            raise Frozen("this builder already sealed")
        if not self.stored:
            raise Invalid("sealing an empty segment indexes nothing")
        self.sealed = True
        for held in self.lengths.values():
            while len(held) < len(self.stored):
                held.append(0)
        return Segment(
            name=name,
            schema=self.schema,
            postings=dict(self.postings),
            stored=list(self.stored),
            lengths={k: list(v) for k, v in self.lengths.items()},
        )


@dataclass
class Segment:
    name: str
    schema: Schema
    postings: dict[tuple[str, str], PostingList]
    stored: list[dict[str, object]]
    lengths: dict[str, list[int]]
    tombstones: set[int] = field(default_factory=set)

    def doc_count(self) -> int:
        return len(self.stored)

    def live_count(self) -> int:
        return len(self.stored) - len(self.tombstones)

    def postings_for(self, field_name: str, term: str) -> PostingList | None:
        self.schema.get(field_name)
        return self.postings.get((field_name, term))

    def document(self, doc: int) -> dict[str, object]:
        if not 0 <= doc < len(self.stored):
            raise Missing(f"no doc {doc} in segment {self.name}")
        if doc in self.tombstones:
            raise Missing(
                f"doc {doc} in segment {self.name} was deleted; the "
                f"tombstone stands until a merge sweeps it"
            )
        return self.stored[doc]

    def delete(self, doc: int) -> None:
        if not 0 <= doc < len(self.stored):
            raise Missing(f"no doc {doc} in segment {self.name}")
        self.tombstones.add(doc)

    def is_live(self, doc: int) -> bool:
        return 0 <= doc < len(self.stored) and doc not in self.tombstones

    def field_length(self, field_name: str, doc: int) -> int:
        held = self.lengths.get(field_name)
        if held is None:
            return 0
        return held[doc]

    def average_field_length(self, field_name: str) -> float:
        held = self.lengths.get(field_name)
        if not held:
            return 0.0
        return sum(held) / len(held)

    def vocabulary(self, field_name: str) -> list[str]:
        return sorted(
            term
            for held_field, term in self.postings
            if held_field == field_name
        )

    def waste_share(self) -> float:
        if not self.stored:
            return 0.0
        return len(self.tombstones) / len(self.stored)
