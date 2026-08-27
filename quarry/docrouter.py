"""Document routing: a document's shard is a pure function of its key.

Sharded indexing dies two deaths without discipline: the same
document landing on two shards because two indexers disagreed
about where it goes, and a resharding that strands every
existing document on the wrong shard. Routing here is a pure
function, hash of the routing key modulo the shard count, so
any indexer anywhere computes the same home; the routing key is
declared per corpus, defaulting to the external id but
overridable to a tenant key so one tenant's documents cohabit,
which is what makes tenant-scoped queries single-shard. The
resharding answer is the routing epoch: the router carries
numbered epochs with their shard counts, documents remember the
epoch that placed them, and lookups route by the document's
epoch, not the current one, so growth never strands anyone and
migration is an explicit per-document move to the newest epoch,
trackable, resumable, and boring.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from quarry.errors import Invalid, Missing


def _bucket(key: str, shards: int) -> int:
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % shards


@dataclass
class DocRouter:
    epochs: dict[int, int] = field(default_factory=dict)
    placements: dict[str, int] = field(default_factory=dict)

    def declare_epoch(self, epoch: int, shards: int) -> str:
        if shards <= 0:
            raise Invalid("an epoch of zero shards routes nowhere")
        if epoch in self.epochs:
            raise Invalid(
                f"epoch {epoch} exists with {self.epochs[epoch]} "
                f"shard(s); epochs are immutable, declare the next"
            )
        if self.epochs and epoch <= max(self.epochs):
            raise Invalid(
                f"epoch {epoch} does not advance past "
                f"{max(self.epochs)}; history only grows"
            )
        self.epochs[epoch] = shards
        return f"epoch {epoch}: {shards} shard(s)"

    def newest_epoch(self) -> int:
        if not self.epochs:
            raise Missing("no epochs declared; the router is blank")
        return max(self.epochs)

    def place(self, routing_key: str) -> tuple[int, int]:
        if not routing_key.strip():
            raise Invalid("an empty routing key routes by accident")
        epoch = self.newest_epoch()
        shard = _bucket(routing_key, self.epochs[epoch])
        self.placements[routing_key] = epoch
        return epoch, shard

    def locate(self, routing_key: str) -> tuple[int, int]:
        epoch = self.placements.get(routing_key)
        if epoch is None:
            raise Missing(
                f"{routing_key!r} was never placed; locate answers "
                f"for residents, not visitors"
            )
        return epoch, _bucket(routing_key, self.epochs[epoch])

    def migrate(self, routing_key: str) -> str:
        old_epoch, old_shard = self.locate(routing_key)
        newest = self.newest_epoch()
        if old_epoch == newest:
            return (
                f"{routing_key!r} already lives in epoch {newest}; "
                f"nothing to move"
            )
        self.placements[routing_key] = newest
        new_shard = _bucket(routing_key, self.epochs[newest])
        return (
            f"{routing_key!r} moved epoch {old_epoch} shard "
            f"{old_shard} -> epoch {newest} shard {new_shard}"
        )

    def stragglers(self) -> list[str]:
        newest = self.newest_epoch()
        return sorted(
            key
            for key, epoch in self.placements.items()
            if epoch != newest
        )

    def census(self) -> str:
        if not self.placements:
            return "no documents placed"
        newest = self.newest_epoch()
        behind = len(self.stragglers())
        current = len(self.placements) - behind
        return (
            f"{len(self.placements)} document(s): {current} in "
            f"epoch {newest}, {behind} straggling in older epochs"
        )
