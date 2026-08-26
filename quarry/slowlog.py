"""The slow log: the queries that hurt, kept with their anatomy.

Averages hide the query that took two seconds behind the thousand
that took two milliseconds, so the slow log keeps individual
offenders past a threshold with the anatomy that explains them:
how many terms, how many candidates matched, how many segments
were consulted. Percentiles come from every query, not just the
slow ones, because a slow log without the population underneath
cannot say whether the p99 moved or one whale swam past. The
repeat-offender report groups slow entries by canonical query,
which is the difference between "searches are slow" and "this one
query with eleven terms is slow every time marketing runs its
Monday report", and only one of those sentences is actionable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid

SLOW_LINE = 100


@dataclass(frozen=True)
class SlowEntry:
    canonical: str
    took: int
    terms: int
    candidates: int
    segments: int


@dataclass
class SlowLog:
    slow_line: int = SLOW_LINE
    entries: list[SlowEntry] = field(default_factory=list)
    all_timings: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.slow_line <= 0:
            raise Invalid("a slow line at zero calls everything slow")

    def observe(
        self,
        canonical: str,
        took: int,
        terms: int = 0,
        candidates: int = 0,
        segments: int = 0,
    ) -> bool:
        if took < 0:
            raise Invalid("negative timings are clock skew, not speed")
        self.all_timings.append(took)
        if took >= self.slow_line:
            self.entries.append(
                SlowEntry(
                    canonical=canonical,
                    took=took,
                    terms=terms,
                    candidates=candidates,
                    segments=segments,
                )
            )
            return True
        return False

    def percentile(self, fraction: float) -> int:
        if not self.all_timings:
            raise Invalid("no queries observed; percentiles of nothing")
        if not 0.0 <= fraction <= 1.0:
            raise Invalid("a percentile is a fraction")
        ordered = sorted(self.all_timings)
        index = int(fraction * (len(ordered) - 1) + 0.5)
        return ordered[index]

    def slow_share(self) -> float:
        if not self.all_timings:
            raise Invalid("no queries observed")
        return round(len(self.entries) / len(self.all_timings), 4)

    def repeat_offenders(self, floor: int = 2) -> list[tuple[str, int, int]]:
        """Canonical queries slow more than once: name, count, worst."""
        if floor < 2:
            raise Invalid("an offender of one is an incident, not a habit")
        by_query: dict[str, list[int]] = {}
        for entry in self.entries:
            by_query.setdefault(entry.canonical, []).append(entry.took)
        rows = [
            (canonical, len(timings), max(timings))
            for canonical, timings in by_query.items()
            if len(timings) >= floor
        ]
        rows.sort(key=lambda held: (-held[1], -held[2], held[0]))
        return rows

    def anatomy_of_the_worst(self) -> str:
        if not self.entries:
            return "nothing slow yet; the line holds"
        worst = max(self.entries, key=lambda held: held.took)
        return (
            f"{worst.canonical}: {worst.took} ticks, {worst.terms} "
            f"terms, {worst.candidates} candidates across "
            f"{worst.segments} segment(s)"
        )

    def report(self) -> str:
        if not self.all_timings:
            return "no queries observed"
        lines = [
            f"{len(self.all_timings)} queries, p50 "
            f"{self.percentile(0.5)}, p99 {self.percentile(0.99)}, "
            f"{self.slow_share():.1%} past the line"
        ]
        offenders = self.repeat_offenders()
        for canonical, count, worst in offenders:
            lines.append(
                f"  habitual: {canonical} slow {count} times, "
                f"worst {worst}"
            )
        lines.append(f"  worst anatomy: {self.anatomy_of_the_worst()}")
        return "\n".join(lines)
