"""Hedged reads: the second request is insurance, priced and audited.

Tail latency comes from unlucky replicas, and hedging is the
standard purchase: send the read to one replica, and if no
answer arrives inside the hedge delay, send a second copy to a
different replica and take whichever answers first. The delay
is the whole design: hedge at zero and every read doubles the
cluster's work for nothing, hedge too late and the insurance
pays after the fire, so the delay is set from the observed p95
and the ledger reports what hedging actually bought, hedged
share, wins by the second request, and wasted duplicates,
because insurance that never pays should be cancelled with
numbers in hand. Hedges go to a different replica by
construction, a hedge to the same slow box is a retry wearing
insurance's clothes, and cancellation is recorded when the
first answer lands so the wasted work is counted, not
imagined.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid


@dataclass(frozen=True)
class ReadOutcome:
    query: str
    hedged: bool
    winner: str
    first_latency: int
    hedge_latency: int | None

    def hedge_won(self) -> bool:
        return self.hedged and self.winner == "hedge"


@dataclass
class HedgedReader:
    replicas: tuple[str, ...]
    hedge_delay_ms: int
    outcomes: list[ReadOutcome] = field(default_factory=list)

    def __post_init__(self) -> None:
        if len(self.replicas) < 2:
            raise Invalid(
                "hedging needs a second replica to hedge to; one "
                "box is a retry, not insurance"
            )
        if self.hedge_delay_ms <= 0:
            raise Invalid(
                "a hedge delay of zero doubles every read's cost "
                "for nothing; set it from the observed p95"
            )

    def pick_hedge_target(self, primary: str) -> str:
        if primary not in self.replicas:
            raise Invalid(
                f"{primary} is not a replica in this group"
            )
        for candidate in self.replicas:
            if candidate != primary:
                return candidate
        raise Invalid("unreachable: two replicas were checked")

    def observe(
        self,
        query: str,
        primary: str,
        primary_latency: int,
        hedge_latency: int | None = None,
    ) -> ReadOutcome:
        if primary_latency < 0:
            raise Invalid("negative latency is a clock bug")
        if primary not in self.replicas:
            raise Invalid(
                f"{primary} is not a replica in this group"
            )
        hedged = primary_latency > self.hedge_delay_ms
        if not hedged:
            outcome = ReadOutcome(
                query=query,
                hedged=False,
                winner="primary",
                first_latency=primary_latency,
                hedge_latency=None,
            )
        else:
            if hedge_latency is None:
                raise Invalid(
                    f"the primary took {primary_latency}ms, past "
                    f"the {self.hedge_delay_ms}ms hedge point; a "
                    f"hedge was sent and its latency must be "
                    f"reported"
                )
            hedge_total = self.hedge_delay_ms + hedge_latency
            winner = (
                "hedge"
                if hedge_total < primary_latency
                else "primary"
            )
            outcome = ReadOutcome(
                query=query,
                hedged=True,
                winner=winner,
                first_latency=min(primary_latency, hedge_total),
                hedge_latency=hedge_latency,
            )
        self.outcomes.append(outcome)
        return outcome

    def ledger(self) -> str:
        total = len(self.outcomes)
        if total == 0:
            return "no reads observed"
        hedged = [held for held in self.outcomes if held.hedged]
        wins = sum(1 for held in hedged if held.hedge_won())
        wasted = len(hedged) - wins
        share = len(hedged) / total
        if not hedged:
            return (
                f"{total} reads, none hedged; the delay of "
                f"{self.hedge_delay_ms}ms was never reached"
            )
        return (
            f"{total} reads, {len(hedged)} hedged ({share:.0%}); "
            f"the hedge won {wins} and wasted {wasted}; "
            f"insurance that never pays should be cancelled"
        )

    def worth_it(self) -> bool:
        hedged = [held for held in self.outcomes if held.hedged]
        if not hedged:
            return False
        wins = sum(1 for held in hedged if held.hedge_won())
        return wins * 2 >= len(hedged)
