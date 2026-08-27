"""Read repair: replica divergence is fixed by the read that finds it.

Replicated indexes drift when an update reaches one copy and
not another, and the cheapest place to notice is the read path:
a repairing read queries every replica, compares document
versions, serves the newest, and queues repairs for the copies
that answered stale, so the system heals in proportion to how
much it is actually read. Version comparison is by explicit
version number, never by timestamp, because clocks across
replicas disagree by exactly enough to resurrect deleted
documents. A deletion is itself versioned as a tombstone so a
replica that missed the delete gets the tombstone pushed,
rather than the deleted document pushed back by a helpful
stale copy, which is the classic read-repair disaster. The
repair queue is explicit and drainable, and reads report
whether they were clean or repairing so a divergence spike is
visible the hour it starts.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid, Missing


@dataclass(frozen=True)
class Versioned:
    external: int
    version: int
    body: str | None

    def deleted(self) -> bool:
        return self.body is None


@dataclass
class Replica:
    name: str
    held: dict[int, Versioned] = field(default_factory=dict)

    def put(self, record: Versioned) -> None:
        standing = self.held.get(record.external)
        if standing is not None and standing.version >= record.version:
            raise Invalid(
                f"{self.name}: doc {record.external} v"
                f"{record.version} does not beat standing v"
                f"{standing.version}; versions only move forward"
            )
        self.held[record.external] = record

    def get(self, external: int) -> Versioned | None:
        return self.held.get(external)


@dataclass
class RepairingReader:
    replicas: list[Replica]
    repair_queue: list[tuple[str, Versioned]] = field(
        default_factory=list
    )
    clean_reads: int = 0
    repairing_reads: int = 0

    def __post_init__(self) -> None:
        if len(self.replicas) < 2:
            raise Invalid(
                "read repair over one replica repairs nothing; "
                "it is just a read"
            )

    def read(self, external: int) -> tuple[Versioned | None, str]:
        answers = [
            (replica, replica.get(external))
            for replica in self.replicas
        ]
        present = [
            (replica, record)
            for replica, record in answers
            if record is not None
        ]
        if not present:
            raise Missing(
                f"doc {external} is on no replica; nothing to "
                f"serve, nothing to repair"
            )
        newest = max(
            (record for _, record in present),
            key=lambda record: record.version,
        )
        stale = [
            replica
            for replica, record in answers
            if record is None or record.version < newest.version
        ]
        for replica in stale:
            self.repair_queue.append((replica.name, newest))
        if stale:
            self.repairing_reads += 1
            names = ", ".join(
                sorted(replica.name for replica in stale)
            )
            note = (
                f"served v{newest.version}, repairs queued for "
                f"{names}"
            )
        else:
            self.clean_reads += 1
            note = f"served v{newest.version}, all replicas agree"
        served = None if newest.deleted() else newest
        return served, note

    def drain_repairs(self) -> str:
        by_name = {
            replica.name: replica for replica in self.replicas
        }
        applied = 0
        for name, record in self.repair_queue:
            replica = by_name[name]
            standing = replica.get(record.external)
            if (
                standing is None
                or standing.version < record.version
            ):
                replica.held[record.external] = record
                applied += 1
        drained = len(self.repair_queue)
        self.repair_queue = []
        return (
            f"drained {drained} repair(s), applied {applied}; the "
            f"rest were already healed by later reads"
        )

    def health(self) -> str:
        total = self.clean_reads + self.repairing_reads
        if total == 0:
            return "no reads yet"
        share = self.repairing_reads / total
        return (
            f"{self.repairing_reads} of {total} reads repaired "
            f"({share:.0%}); queue holds {len(self.repair_queue)}"
        )
