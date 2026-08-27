"""The writer: documents buffer, buffers flush, segments accumulate.

An index is a growing family of sealed segments plus one mutable
buffer. Adds land in the buffer and become searchable at flush,
which happens when the buffer reaches its size or the caller asks,
so freshness is a knob rather than a promise nobody costed. Every
document gets a stable external id at add time; the pair segment
name and local doc id is an address, not an identity, because
merges rewrite addresses and an id that moved is a broken bookmark.
Deletes resolve the external id to whichever segment holds it and
plant a tombstone there, including in the unflushed buffer, where
the delete simply removes the pending document before it ever
becomes real.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid, Missing
from quarry.schema import Schema
from quarry.segment import Segment, SegmentBuilder

FLUSH_AT = 128


@dataclass
class Index:
    schema: Schema
    flush_at: int = FLUSH_AT
    segments: list[Segment] = field(default_factory=list)
    pending: list[tuple[int, dict[str, object]]] = field(default_factory=list)
    locations: dict[int, tuple[str, int]] = field(default_factory=dict)
    next_id: int = 0
    next_segment: int = 0
    flushes: int = 0

    def __post_init__(self) -> None:
        if not self.schema.sealed:
            raise Invalid("seal the schema before opening an index")
        if self.flush_at <= 0:
            raise Invalid("flush_at must be positive")

    def add(self, document: dict[str, object]) -> int:
        for name, value in document.items():
            declared = self.schema.get(name)
            if declared.kind == "numeric" and not isinstance(value, int):
                raise Invalid(
                    f"{name} is numeric and {value!r} is not an "
                    f"integer; refused at the door rather than at "
                    f"flush, where it would sink innocent documents"
                )
        external = self.next_id
        self.next_id += 1
        self.pending.append((external, document))
        if len(self.pending) >= self.flush_at:
            self.flush()
        return external

    def delete(self, external: int) -> str:
        for index, (held_id, _) in enumerate(self.pending):
            if held_id == external:
                del self.pending[index]
                return "removed before it ever became real"
        if external not in self.locations:
            raise Missing(f"no document with id {external}")
        segment_name, local = self.locations[external]
        self._segment(segment_name).delete(local)
        return f"tombstoned in {segment_name}"

    def _segment(self, name: str) -> Segment:
        for held in self.segments:
            if held.name == name:
                return held
        raise Missing(f"no segment named {name}")

    def flush(self) -> Segment | None:
        if not self.pending:
            return None
        builder = SegmentBuilder(schema=self.schema)
        name = f"seg{self.next_segment}"
        self.next_segment += 1
        for external, document in self.pending:
            local = builder.add(document)
            self.locations[external] = (name, local)
        segment = builder.seal(name)
        self.segments.append(segment)
        self.pending.clear()
        self.flushes += 1
        return segment

    def external_id(self, segment_name: str, local: int) -> int:
        for external, (held_name, held_local) in self.locations.items():
            if held_name == segment_name and held_local == local:
                return external
        raise Missing(
            f"no external id maps to {segment_name}:{local}"
        )

    def document(self, external: int) -> dict[str, object]:
        for held_id, held_doc in self.pending:
            if held_id == external:
                return held_doc
        if external not in self.locations:
            raise Missing(f"no document with id {external}")
        segment_name, local = self.locations[external]
        return self._segment(segment_name).document(local)

    def doc_count(self) -> int:
        flushed = sum(segment.live_count() for segment in self.segments)
        return flushed + len(self.pending)

    def searchable_count(self) -> int:
        return sum(segment.live_count() for segment in self.segments)

    def shape(self) -> str:
        rows = [
            f"{segment.name}: {segment.live_count()}/{segment.doc_count()} "
            f"live"
            for segment in self.segments
        ]
        rows.append(f"buffer: {len(self.pending)} pending")
        return "\n".join(rows)
