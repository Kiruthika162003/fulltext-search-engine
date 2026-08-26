"""Replication: replicas serve yesterday's truth and say how old it is.

The primary indexes; replicas answer queries from shipped segment
snapshots. Shipping is segment-granular because segments are
immutable, so a replica pulls only what it lacks, and tombstone
sets travel separately since they are the one thing that mutates
under a sealed segment. The lag between primary and replica is
measured in operations, not seconds, because a replica three
operations behind during a quiet night is fresher than one three
seconds behind during a bulk load. Every replica answer carries
its lag so the caller chooses: read-your-writes goes to the
primary, the dashboard tolerates staleness it can see, and the
one unforgivable design is the replica that serves stale data
while claiming to be current.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid, Missing
from quarry.multisearch import search_index
from quarry.query import Query
from quarry.schema import Schema
from quarry.segment import Segment
from quarry.writer import Index


@dataclass
class Primary:
    index: Index
    operations: int = 0

    def add(self, document: dict[str, object]) -> int:
        self.operations += 1
        return self.index.add(document)

    def delete(self, external: int) -> None:
        self.operations += 1
        self.index.delete(external)

    def flush(self) -> None:
        self.index.flush()


@dataclass(frozen=True)
class ReplicaAnswer:
    externals: tuple[int, ...]
    lag_operations: int
    current: bool


@dataclass
class Replica:
    schema: Schema
    index: Index = None
    applied_operations: int = 0
    segments_pulled: int = 0
    tombstones_pulled: int = 0

    def __post_init__(self) -> None:
        if self.index is None:
            self.index = Index(schema=self.schema)

    def sync(self, primary: Primary) -> str:
        """Pull missing segments and refresh tombstones; report the haul."""
        primary.flush()
        have = {segment.name for segment in self.index.segments}
        pulled = 0
        for segment in primary.index.segments:
            if segment.name in have:
                continue
            self.index.segments.append(
                Segment(
                    name=segment.name,
                    schema=segment.schema,
                    postings=segment.postings,
                    stored=segment.stored,
                    lengths=segment.lengths,
                    tombstones=set(segment.tombstones),
                )
            )
            pulled += 1
        primary_names = {
            segment.name for segment in primary.index.segments
        }
        self.index.segments = [
            segment
            for segment in self.index.segments
            if segment.name in primary_names
        ]
        refreshed = 0
        for segment in self.index.segments:
            source = next(
                held
                for held in primary.index.segments
                if held.name == segment.name
            )
            if segment.tombstones != source.tombstones:
                segment.tombstones = set(source.tombstones)
                refreshed += 1
        self.index.locations = dict(primary.index.locations)
        self.index.next_id = primary.index.next_id
        self.index.next_segment = primary.index.next_segment
        self.applied_operations = primary.operations
        self.segments_pulled += pulled
        self.tombstones_pulled += refreshed
        return (
            f"pulled {pulled} segment(s), refreshed {refreshed} "
            f"tombstone set(s)"
        )

    def lag(self, primary: Primary) -> int:
        behind = primary.operations - self.applied_operations
        if behind < 0:
            raise Invalid(
                "the replica claims to be ahead of its primary; one of "
                "them is lying and neither should be trusted"
            )
        return behind

    def search(
        self, primary: Primary, query: Query, limit: int = 10
    ) -> ReplicaAnswer:
        behind = self.lag(primary)
        page = search_index(self.index, query, limit=limit)
        return ReplicaAnswer(
            externals=tuple(hit.external for hit in page.hits),
            lag_operations=behind,
            current=behind == 0,
        )


def route_read(
    primary: Primary,
    replicas: list[Replica],
    needs_own_writes: bool,
) -> str:
    """Read-your-writes goes home; everything else takes the freshest."""
    if needs_own_writes or not replicas:
        return "primary"
    lags = [replica.lag(primary) for replica in replicas]
    freshest = min(range(len(lags)), key=lambda i: (lags[i], i))
    return f"replica-{freshest}"


def replication_report(primary: Primary, replicas: list[Replica]) -> str:
    if not replicas:
        raise Missing("no replicas to report on")
    lines = [f"primary at operation {primary.operations}"]
    for number, replica in enumerate(replicas):
        behind = replica.lag(primary)
        state = "current" if behind == 0 else f"{behind} operation(s) behind"
        lines.append(f"  replica-{number}: {state}")
    return "\n".join(lines)
