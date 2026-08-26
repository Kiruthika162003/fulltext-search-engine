"""The result cache: stale answers are worse than slow ones.

Caching search results is safe exactly as long as the index does
not move, so the cache key includes the index generation: every
flush, merge, and delete bumps the generation, and entries from
older generations are dead on arrival rather than served with
yesterday's corpus. Within a generation the key is the canonical
query plus the page bounds, because two spellings of the same query
should share one slot, which is what the canonical form was built
for. Eviction is least-recently-used with a declared capacity, the
hit ratio is tracked from birth, and the invalidation counter says
how many entries each index change killed, since a cache that
cannot show its own funeral count will be blamed for staleness it
never caused.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid

CAPACITY = 128


@dataclass
class CachedPage:
    generation: int
    hits: tuple
    token: tuple | None


@dataclass
class ResultCache:
    capacity: int = CAPACITY
    generation: int = 0
    slots: dict[str, CachedPage] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    lookups: int = 0
    served: int = 0
    killed_by_invalidation: int = 0

    def __post_init__(self) -> None:
        if self.capacity <= 0:
            raise Invalid("a cache with no slots is a hash of regret")

    def _key(self, canonical: str, limit: int, after: tuple | None) -> str:
        return f"{canonical}\x00{limit}\x00{after}"

    def get(
        self, canonical: str, limit: int, after: tuple | None
    ) -> CachedPage | None:
        self.lookups += 1
        key = self._key(canonical, limit, after)
        held = self.slots.get(key)
        if held is None:
            return None
        if held.generation != self.generation:
            del self.slots[key]
            self.order.remove(key)
            self.killed_by_invalidation += 1
            return None
        self.order.remove(key)
        self.order.append(key)
        self.served += 1
        return held

    def put(
        self,
        canonical: str,
        limit: int,
        after: tuple | None,
        hits: tuple,
        token: tuple | None,
    ) -> None:
        key = self._key(canonical, limit, after)
        if key in self.slots:
            self.order.remove(key)
        self.slots[key] = CachedPage(
            generation=self.generation, hits=hits, token=token
        )
        self.order.append(key)
        while len(self.order) > self.capacity:
            oldest = self.order.pop(0)
            del self.slots[oldest]

    def index_changed(self) -> int:
        """Bump the generation; report how many live entries died."""
        doomed = sum(
            1
            for held in self.slots.values()
            if held.generation == self.generation
        )
        self.generation += 1
        self.killed_by_invalidation += doomed
        return doomed

    def hit_ratio(self) -> float:
        if self.lookups == 0:
            raise Invalid("no lookups yet; a ratio over zero is a shrug")
        return round(self.served / self.lookups, 4)

    def obituary(self) -> str:
        return (
            f"{len(self.slots)} entries held, "
            f"{self.killed_by_invalidation} killed by index changes, "
            f"hit ratio "
            f"{self.hit_ratio() if self.lookups else 0.0}"
        )
