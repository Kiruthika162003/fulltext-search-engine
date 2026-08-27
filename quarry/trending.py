"""Trending queries: rising is a ratio against yesterday, not a big number.

The most-searched list is boring by construction, the same head
queries every day, and what the desk actually wants is what moved.
A query trends when its current-window count beats its previous
window by the rise factor with a volume floor underneath, because
a query going from one to three searches tripled on noise, and a
floor-less trend list is a parade of flukes. Newborn queries, ones
with no history at all, get their own section rather than an
infinite ratio, since something-from-nothing is a different kind
of news than growth and dividing by zero to prove it is not
arithmetic. The falling list is computed with the same rules in
reverse, because a collapse in a head query is an outage signal
wearing an analytics hat, and nobody looks for outages in a
trending-up list.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid

RISE_FACTOR = 2.0
VOLUME_FLOOR = 5


@dataclass(frozen=True)
class Trend:
    query: str
    previous: int
    current: int

    def ratio(self) -> float:
        if self.previous == 0:
            raise Invalid(
                f"{self.query}: a ratio over zero history is not "
                f"arithmetic; newborns have their own section"
            )
        return round(self.current / self.previous, 2)


@dataclass
class TrendWatch:
    rise_factor: float = RISE_FACTOR
    volume_floor: int = VOLUME_FLOOR
    previous_window: dict[str, int] = field(default_factory=dict)
    current_window: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.rise_factor <= 1.0:
            raise Invalid(
                "a rise factor at or under one calls standing still a "
                "trend"
            )
        if self.volume_floor < 1:
            raise Invalid("a floor under one parades flukes")

    def observe(self, query: str) -> None:
        if not query.strip():
            raise Invalid("an empty query trends nowhere")
        self.current_window[query] = (
            self.current_window.get(query, 0) + 1
        )

    def roll_window(self) -> None:
        self.previous_window = self.current_window
        self.current_window = {}

    def rising(self) -> list[Trend]:
        found = []
        for query, count in self.current_window.items():
            previous = self.previous_window.get(query, 0)
            if previous == 0:
                continue
            if count < self.volume_floor:
                continue
            if count / previous >= self.rise_factor:
                found.append(
                    Trend(
                        query=query, previous=previous, current=count
                    )
                )
        found.sort(
            key=lambda trend: (-trend.ratio(), trend.query)
        )
        return found

    def newborn(self) -> list[Trend]:
        found = [
            Trend(query=query, previous=0, current=count)
            for query, count in self.current_window.items()
            if query not in self.previous_window
            and count >= self.volume_floor
        ]
        found.sort(key=lambda trend: (-trend.current, trend.query))
        return found

    def falling(self) -> list[Trend]:
        found = []
        for query, previous in self.previous_window.items():
            if previous < self.volume_floor:
                continue
            count = self.current_window.get(query, 0)
            if count == 0 or previous / count >= self.rise_factor:
                found.append(
                    Trend(
                        query=query, previous=previous, current=count
                    )
                )
        found.sort(key=lambda trend: (-trend.previous, trend.query))
        return found

    def deskpage(self) -> str:
        lines = []
        risers = self.rising()
        if risers:
            lines.append("rising:")
            lines.extend(
                f"  {trend.query}: {trend.previous} -> "
                f"{trend.current} ({trend.ratio()}x)"
                for trend in risers
            )
        newborns = self.newborn()
        if newborns:
            lines.append("new this window:")
            lines.extend(
                f"  {trend.query}: {trend.current} from nothing"
                for trend in newborns
            )
        fallers = self.falling()
        if fallers:
            lines.append("falling (check for outages):")
            lines.extend(
                f"  {trend.query}: {trend.previous} -> {trend.current}"
                for trend in fallers
            )
        return "\n".join(lines) if lines else "a quiet window; no news"
