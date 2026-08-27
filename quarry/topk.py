"""Top-k accumulation: the best k survive, ties break the same way twice.

Ranking keeps the best k of millions, and the accumulator that
does it cheaply has three duties beyond a sorted list. Bounded
memory: the heap holds k candidates and every arrival past
capacity evicts the current floor or bounces off it, so a
million-document scan carries k entries, not a million. Total
order: score ties break by ascending id, declared once and
applied in the heap and the final sort both, because an
accumulator whose eviction order disagrees with its output
order drops a tied document nondeterministically, the bug that
haunts result diffs. And shard merging: accumulators from
parallel scans merge by feeding survivors through the same
admission gate, never by concatenation, so the merged top k
equals the top k a single scan would have found, a property
pinned by test rather than assumed from symmetry.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field

from quarry.errors import Invalid


def _heap_key(score: float, doc: int) -> tuple[float, int]:
    """Min-heap key: worst first; ties evict the LARGER id first."""
    return (score, -doc)


@dataclass
class TopK:
    k: int
    heap: list[tuple[tuple[float, int], int, float]] = field(
        default_factory=list
    )
    offered: int = 0

    def __post_init__(self) -> None:
        if self.k <= 0:
            raise Invalid("keeping the best zero keeps nothing")

    def offer(self, doc: int, score: float) -> bool:
        self.offered += 1
        entry = (_heap_key(score, doc), doc, score)
        if len(self.heap) < self.k:
            heapq.heappush(self.heap, entry)
            return True
        if entry[0] <= self.heap[0][0]:
            return False
        heapq.heapreplace(self.heap, entry)
        return True

    def floor(self) -> tuple[int, float] | None:
        if len(self.heap) < self.k:
            return None
        _, doc, score = self.heap[0]
        return doc, score

    def ranked(self) -> list[tuple[int, float]]:
        ordered = sorted(
            self.heap,
            key=lambda entry: (-entry[2], entry[1]),
        )
        return [(doc, score) for _, doc, score in ordered]

    def line(self) -> str:
        kept = len(self.heap)
        return (
            f"kept {kept} of {self.offered} offered; the floor "
            f"is {self.floor()}"
        )


def merge(accumulators: list[TopK]) -> TopK:
    if not accumulators:
        raise Invalid("merging no accumulators keeps nothing")
    widths = {held.k for held in accumulators}
    if len(widths) != 1:
        raise Invalid(
            f"accumulators of widths {sorted(widths)} do not "
            f"merge; they were answering different questions"
        )
    out = TopK(k=accumulators[0].k)
    for held in accumulators:
        for doc, score in held.ranked():
            out.offer(doc, score)
    out.offered = sum(held.offered for held in accumulators)
    return out
