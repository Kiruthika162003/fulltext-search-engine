"""Tiered storage: old segments move to cheap seats, and say so.

Most corpora age: this week's documents take most of the queries,
last year's take almost none, and paying hot-tier prices for cold
data is a bill nobody audits. The tier ledger assigns each segment
a tier with a declared cost and latency multiplier, demotion
follows the policy's age and coldness rules, and the searcher's
report says which tiers a query touched so a slow answer can be
traced to the cold seats it visited instead of blamed on the
engine at large. Promotion back to hot requires recent heat, not
an operator mood, and the invariant the tests pin is the honest
one: moving tiers never changes what a query returns, only what
it costs, because a tier that loses documents is not a tier, it
is an outage with a pricing model.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid, Missing

TIERS = {
    "hot": {"cost": 10, "latency_multiplier": 1},
    "warm": {"cost": 4, "latency_multiplier": 3},
    "cold": {"cost": 1, "latency_multiplier": 10},
}
DEMOTE_TO_WARM_AFTER = 30
DEMOTE_TO_COLD_AFTER = 90
PROMOTE_HEAT = 10


@dataclass
class SegmentTier:
    segment_name: str
    tier: str = "hot"
    sealed_at: int = 0
    recent_queries: int = 0


@dataclass
class TierLedger:
    rows: dict[str, SegmentTier] = field(default_factory=dict)
    moves: list[str] = field(default_factory=list)

    def admit(self, segment_name: str, sealed_at: int) -> None:
        if segment_name in self.rows:
            raise Invalid(f"{segment_name} is already tiered")
        self.rows[segment_name] = SegmentTier(
            segment_name=segment_name, sealed_at=sealed_at
        )

    def retire(self, segment_name: str) -> None:
        if segment_name not in self.rows:
            raise Missing(f"{segment_name} was never tiered")
        del self.rows[segment_name]

    def touched(self, segment_name: str) -> None:
        row = self.rows.get(segment_name)
        if row is None:
            raise Missing(f"{segment_name} was never tiered")
        row.recent_queries += 1

    def settle(self, now: int) -> list[str]:
        """Run the policy: demote the old and cold, promote the hot."""
        acted = []
        for row in sorted(self.rows.values(), key=lambda r: r.segment_name):
            age = now - row.sealed_at
            target = row.tier
            if (
                row.recent_queries >= PROMOTE_HEAT
                and row.tier != "hot"
            ):
                target = "hot"
            elif row.tier == "hot" and age >= DEMOTE_TO_WARM_AFTER and (
                row.recent_queries < PROMOTE_HEAT
            ):
                target = "warm"
            elif row.tier == "warm" and age >= DEMOTE_TO_COLD_AFTER and (
                row.recent_queries < PROMOTE_HEAT
            ):
                target = "cold"
            if target != row.tier:
                line = (
                    f"[{now}] {row.segment_name}: {row.tier} -> "
                    f"{target} (age {age}, heat {row.recent_queries})"
                )
                row.tier = target
                self.moves.append(line)
                acted.append(line)
            row.recent_queries = 0
        return acted

    def tier_of(self, segment_name: str) -> str:
        row = self.rows.get(segment_name)
        if row is None:
            raise Missing(f"{segment_name} was never tiered")
        return row.tier

    def monthly_bill(self) -> int:
        return sum(
            TIERS[row.tier]["cost"] for row in self.rows.values()
        )

    def query_cost_report(self, touched: list[str]) -> str:
        """Which tiers a query visited, and the latency it bought."""
        if not touched:
            return "the query touched nothing"
        worst = 1
        by_tier: dict[str, int] = {}
        for segment_name in touched:
            tier = self.tier_of(segment_name)
            by_tier[tier] = by_tier.get(tier, 0) + 1
            worst = max(
                worst, TIERS[tier]["latency_multiplier"]
            )
        parts = ", ".join(
            f"{count} {tier}" for tier, count in sorted(by_tier.items())
        )
        return (
            f"touched {parts}; slowest seat multiplies latency by "
            f"{worst}"
        )
