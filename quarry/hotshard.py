"""Hot shard detection and the move plan that cools it.

Hash routing spreads documents evenly and traffic unevenly: one
viral tenant turns its shard into the hot one, and the cluster
is only as fast as its hottest member. The detector compares
each shard's query load against the fleet median, not the mean,
because the hot shard itself drags a mean upward until it hides
inside it, and flags shards past the declared multiple. The
cooling plan moves the busiest tenants off the hot shard onto
the coolest ones, largest first, until the projection drops
under the threshold, and the plan is a proposal with projected
numbers, never an action, because tenant moves invalidate
caches and warm indexes, and a balancer that moves things on
its own schedule is a source of outages wearing a badge. The
projection arithmetic ships in the plan so the operator can
check it before agreeing.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid

HOT_MULTIPLE = 2.0


def median(values: list[int]) -> float:
    if not values:
        raise Invalid("a median of nothing is nothing")
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2


@dataclass(frozen=True)
class ShardLoad:
    name: str
    tenant_loads: dict[str, int]

    def total(self) -> int:
        return sum(self.tenant_loads.values())


@dataclass(frozen=True)
class Move:
    tenant: str
    load: int
    source: str
    target: str

    def line(self) -> str:
        return (
            f"move {self.tenant} ({self.load} qps) from "
            f"{self.source} to {self.target}"
        )


def find_hot(shards: list[ShardLoad]) -> tuple[list[str], float]:
    if len(shards) < 3:
        raise Invalid(
            "hot detection needs at least three shards; with two, "
            "one is always hotter and the label means nothing"
        )
    fleet_median = median([shard.total() for shard in shards])
    if fleet_median == 0:
        return [], 0.0
    hot = [
        shard.name
        for shard in shards
        if shard.total() > fleet_median * HOT_MULTIPLE
    ]
    return sorted(hot), fleet_median


def cooling_plan(
    shards: list[ShardLoad],
) -> tuple[list[Move], str]:
    hot_names, fleet_median = find_hot(shards)
    if not hot_names:
        return [], "no shard runs hot; the fleet is balanced"
    threshold = fleet_median * HOT_MULTIPLE
    by_name = {shard.name: shard for shard in shards}
    moves: list[Move] = []
    projected = {
        shard.name: shard.total() for shard in shards
    }
    for hot_name in hot_names:
        hot_shard = by_name[hot_name]
        tenants = sorted(
            hot_shard.tenant_loads.items(),
            key=lambda pair: (-pair[1], pair[0]),
        )
        for tenant, load in tenants:
            if projected[hot_name] <= threshold:
                break
            coolest = min(
                (
                    name
                    for name in projected
                    if name not in hot_names
                ),
                key=lambda name: (projected[name], name),
            )
            projected[hot_name] -= load
            projected[coolest] += load
            moves.append(
                Move(
                    tenant=tenant,
                    load=load,
                    source=hot_name,
                    target=coolest,
                )
            )
    lines = [move.line() for move in moves]
    after = ", ".join(
        f"{name}: {projected[name]}"
        for name in sorted(projected)
    )
    lines.append(
        f"projected loads after: {after} (threshold "
        f"{threshold:.0f}, median {fleet_median:.0f})"
    )
    return moves, "\n".join(lines)
