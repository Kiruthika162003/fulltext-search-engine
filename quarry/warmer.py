"""Cache warming: yesterday's top queries pay for tomorrow's first hits.

A cold cache after a deploy makes the busiest hour of the day the
slowest, so the warmer replays the head of the query log into the
fresh cache before traffic arrives. The head is the right list
because cache value concentrates exactly where volume does, and
the warm budget is a count, not a vague ambition: the warmer takes
the top N by volume, replays them, and reports coverage as the
share of yesterday's total volume those N queries carried, which
is the number that predicts tomorrow's hit rate. Replaying a
query that fails is reported and skipped, never retried in a
loop, because a query that broke during warming will break again
at 9am and the report is where somebody finds that out at 7."""

from __future__ import annotations

from dataclasses import dataclass

from quarry.engine import Engine
from quarry.errors import Invalid, QuarryError


@dataclass(frozen=True)
class WarmingReport:
    replayed: tuple[str, ...]
    failed: tuple[tuple[str, str], ...]
    volume_covered: int
    total_volume: int

    def coverage(self) -> float:
        if self.total_volume == 0:
            raise Invalid("coverage over an empty log is a shrug")
        return round(self.volume_covered / self.total_volume, 4)

    def morning_note(self) -> str:
        note = (
            f"warmed {len(self.replayed)} queries covering "
            f"{self.coverage():.0%} of yesterday's volume"
        )
        if self.failed:
            broken = ", ".join(text for text, _ in self.failed)
            note += f"; BROKEN during warming: {broken}"
        return note


@dataclass
class CacheWarmer:
    engine: Engine
    budget: int = 20
    runs: int = 0

    def __post_init__(self) -> None:
        if self.budget <= 0:
            raise Invalid("a warm budget of zero is a cold cache with a plan")

    def warm(self, query_volumes: dict[str, int]) -> WarmingReport:
        if not query_volumes:
            raise Invalid("an empty log warms nothing; run cold honestly")
        self.runs += 1
        ranked = sorted(
            query_volumes.items(), key=lambda row: (-row[1], row[0])
        )
        chosen = ranked[: self.budget]
        replayed = []
        failed = []
        covered = 0
        for text, volume in chosen:
            try:
                self.engine.search(text)
                replayed.append(text)
                covered += volume
            except QuarryError as refused:
                failed.append((text, str(refused)))
        return WarmingReport(
            replayed=tuple(replayed),
            failed=tuple(failed),
            volume_covered=covered,
            total_volume=sum(query_volumes.values()),
        )
