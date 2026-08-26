"""Sharding: the corpus splits by key, the answer admits what it missed.

One index stops scaling when the corpus outgrows one machine's
patience, so documents route to shards by a stable hash of their
routing key and every search becomes scatter-gather: ask every
shard, merge by score, keep the top of the union. The two honesty
rules live in the gather step. Scores merge without renormalising
because every shard scored with the same global statistics
discipline, and a merge that rescales per shard quietly invents a
ranking no shard computed. And when a shard fails to answer, the
response says so in a way callers cannot miss: partial results
carry the names of the missing shards and the fraction of the
corpus they hold, because "here is what we found" and "here is
what we found in the 60 percent we could reach" are different
sentences that deserve different retry buttons.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from quarry.errors import Invalid, Missing
from quarry.multisearch import search_index
from quarry.query import Query
from quarry.schema import Schema
from quarry.writer import Index


def route(key: str, shard_count: int) -> int:
    if shard_count <= 0:
        raise Invalid("routing needs at least one shard")
    if not key:
        raise Invalid("an empty routing key routes everywhere and nowhere")
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % shard_count


@dataclass(frozen=True)
class ShardedHit:
    shard: int
    external: int
    score: float


@dataclass(frozen=True)
class GatheredPage:
    hits: tuple[ShardedHit, ...]
    complete: bool
    missing_shards: tuple[int, ...]
    corpus_share_reached: float


@dataclass
class ShardedIndex:
    schema: Schema
    shard_count: int = 3
    shards: list[Index] = field(default_factory=list)
    down: set[int] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.shard_count <= 0:
            raise Invalid("a sharded index needs shards")
        if not self.shards:
            self.shards = [
                Index(schema=self.schema) for _ in range(self.shard_count)
            ]

    def add(self, routing_key: str, document: dict[str, object]) -> tuple[int, int]:
        shard = route(routing_key, self.shard_count)
        external = self.shards[shard].add(document)
        return shard, external

    def flush(self) -> None:
        for shard in self.shards:
            shard.flush()

    def mark_down(self, shard: int) -> None:
        if not 0 <= shard < self.shard_count:
            raise Missing(f"no shard {shard}")
        self.down.add(shard)

    def mark_up(self, shard: int) -> None:
        self.down.discard(shard)

    def doc_counts(self) -> list[int]:
        return [shard.searchable_count() for shard in self.shards]

    def search(self, query: Query, limit: int = 10) -> GatheredPage:
        if limit <= 0:
            raise Invalid("a search that wants no results should not run")
        gathered: list[ShardedHit] = []
        missing: list[int] = []
        for number, shard in enumerate(self.shards):
            if number in self.down:
                missing.append(number)
                continue
            page = search_index(shard, query, limit=limit)
            gathered.extend(
                ShardedHit(
                    shard=number,
                    external=hit.external,
                    score=hit.score,
                )
                for hit in page.hits
            )
        gathered.sort(
            key=lambda hit: (-hit.score, hit.shard, hit.external)
        )
        total_docs = sum(self.doc_counts())
        reached_docs = sum(
            count
            for number, count in enumerate(self.doc_counts())
            if number not in self.down
        )
        share = (
            round(reached_docs / total_docs, 4) if total_docs else 1.0
        )
        return GatheredPage(
            hits=tuple(gathered[:limit]),
            complete=not missing,
            missing_shards=tuple(missing),
            corpus_share_reached=share,
        )

    def imbalance(self) -> float:
        """Largest shard over the fair share; 1.0 is perfect."""
        counts = self.doc_counts()
        total = sum(counts)
        if total == 0:
            raise Invalid("an empty index balances trivially; not a number")
        fair = total / self.shard_count
        return round(max(counts) / fair, 3)
