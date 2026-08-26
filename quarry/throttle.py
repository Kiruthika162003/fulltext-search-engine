"""Indexing admission: the write path yields to the read path.

Search is the product; indexing is maintenance, and maintenance
that saturates the box turns every query slow at once. The
throttle admits indexing work against a budget measured as a share
of recent capacity: each tick the caller reports how busy queries
kept the engine, the throttle grants indexing tokens from what
remains, and a burst of documents queues rather than shoves. The
backlog is bounded and overflow rejects loudly at the front door,
because a bounded queue that silently drops from the middle is a
data-loss bug with a flow-control costume. Starvation runs the
other way too: a trickle of guaranteed tokens flows even under
full query load, since an indexer starved to death during a busy
week surfaces as stale search results and nobody connects the
two.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid

CAPACITY_PER_TICK = 100
GUARANTEED = 5
BACKLOG_LIMIT = 500


@dataclass
class IndexThrottle:
    capacity: int = CAPACITY_PER_TICK
    guaranteed: int = GUARANTEED
    backlog_limit: int = BACKLOG_LIMIT
    backlog: list[str] = field(default_factory=list)
    admitted: int = 0
    rejected_at_the_door: int = 0
    granted_by_tick: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.capacity <= 0:
            raise Invalid("a throttle needs capacity to share")
        if not 0 < self.guaranteed <= self.capacity:
            raise Invalid(
                "the guarantee must exist and fit inside capacity, or "
                "the indexer starves during every busy week"
            )
        if self.backlog_limit <= 0:
            raise Invalid("a backlog of zero is a rejection machine")

    def offer(self, document_id: str) -> bool:
        """Queue a document; a full backlog rejects at the front door."""
        if len(self.backlog) >= self.backlog_limit:
            self.rejected_at_the_door += 1
            return False
        self.backlog.append(document_id)
        return True

    def tick(self, query_busy_share: float) -> list[str]:
        """Grant this tick's tokens from what queries left over."""
        if not 0.0 <= query_busy_share <= 1.0:
            raise Invalid("busyness is a fraction of capacity")
        spare = round(self.capacity * (1.0 - query_busy_share))
        tokens = max(self.guaranteed, spare)
        granted = self.backlog[:tokens]
        del self.backlog[:tokens]
        self.admitted += len(granted)
        self.granted_by_tick.append(len(granted))
        return granted

    def depth(self) -> int:
        return len(self.backlog)

    def drain_estimate(self, query_busy_share: float) -> int:
        """Ticks to empty the backlog at the current pressure."""
        if not 0.0 <= query_busy_share <= 1.0:
            raise Invalid("busyness is a fraction of capacity")
        spare = round(self.capacity * (1.0 - query_busy_share))
        rate = max(self.guaranteed, spare)
        return -(-len(self.backlog) // rate) if self.backlog else 0

    def pressure_report(self) -> str:
        return (
            f"backlog {self.depth()}/{self.backlog_limit}, "
            f"{self.admitted} admitted, "
            f"{self.rejected_at_the_door} rejected at the door"
        )
