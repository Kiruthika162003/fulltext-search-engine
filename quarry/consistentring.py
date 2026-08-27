"""A consistent hash ring: nodes come and go, keys barely move.

Modulo routing reshuffles nearly every key when the node count
changes; the ring fixes that by hashing nodes and keys into the
same circular space, each key belonging to the first node
clockwise from it, so adding a node steals only the keys
between it and its predecessor and removing one spills only
its own keys to its successor. Virtual nodes are the load
balancer: each physical node appears many times on the ring so
its share evens out, and the spread report measures the actual
share per node because a ring trusted without measuring is a
ring with one node owning half the space by bad luck. The
movement guarantee is pinned by test, growing the ring moves
only the mathematically necessary share of keys, which is the
entire reason to accept the ring's extra machinery over
modulo's one line.
"""

from __future__ import annotations

import bisect
import hashlib
from dataclasses import dataclass, field

from quarry.errors import Invalid, Missing

VIRTUAL_NODES = 64


def _point(label: str) -> int:
    digest = hashlib.sha256(label.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


@dataclass
class HashRing:
    points: list[int] = field(default_factory=list)
    owner_at: dict[int, str] = field(default_factory=dict)
    nodes: set[str] = field(default_factory=set)

    def add_node(self, node: str) -> str:
        if not node.strip():
            raise Invalid("a nameless node cannot own keys")
        if node in self.nodes:
            raise Invalid(
                f"{node} is already on the ring; doubling a node "
                f"doubles its share invisibly"
            )
        self.nodes.add(node)
        for replica in range(VIRTUAL_NODES):
            point = _point(f"{node}#{replica}")
            bisect.insort(self.points, point)
            self.owner_at[point] = node
        return f"{node} on the ring with {VIRTUAL_NODES} points"

    def remove_node(self, node: str) -> str:
        if node not in self.nodes:
            raise Missing(f"{node} is not on the ring")
        if len(self.nodes) == 1:
            raise Invalid(
                "removing the last node strands every key; add "
                "its successor first"
            )
        self.nodes.discard(node)
        for replica in range(VIRTUAL_NODES):
            point = _point(f"{node}#{replica}")
            index = bisect.bisect_left(self.points, point)
            del self.points[index]
            del self.owner_at[point]
        return f"{node} off the ring; its keys spill clockwise"

    def owner(self, key: str) -> str:
        if not self.points:
            raise Missing("the ring is empty; nothing owns anything")
        point = _point(key)
        index = bisect.bisect_right(self.points, point)
        if index == len(self.points):
            index = 0
        return self.owner_at[self.points[index]]

    def spread(self, sample_keys: list[str]) -> dict[str, float]:
        if not sample_keys:
            raise Invalid("spread over no keys measures nothing")
        counts: dict[str, int] = dict.fromkeys(self.nodes, 0)
        for key in sample_keys:
            counts[self.owner(key)] += 1
        return {
            node: round(count / len(sample_keys), 4)
            for node, count in sorted(counts.items())
        }

    def spread_report(self, sample_keys: list[str]) -> str:
        shares = self.spread(sample_keys)
        fair = 1.0 / len(self.nodes)
        lines = []
        for node, share in shares.items():
            skew = share / fair
            lines.append(
                f"{node}: {share:.1%} of keys ({skew:.2f}x fair)"
            )
        worst = max(shares.values()) / fair
        lines.append(
            f"worst skew {worst:.2f}x over {len(sample_keys)} keys"
        )
        return "\n".join(lines)


def moved_keys(
    before: HashRing, after: HashRing, keys: list[str]
) -> float:
    if not keys:
        raise Invalid("movement over no keys measures nothing")
    moved = sum(
        1 for key in keys if before.owner(key) != after.owner(key)
    )
    return round(moved / len(keys), 4)
