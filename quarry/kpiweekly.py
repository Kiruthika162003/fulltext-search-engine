"""The weekly search digest: five numbers, their deltas, no adjectives.

Search health reaches non-engineers as a weekly page, and the
page earns trust by being the same five numbers every week:
queries served, zero-result share, click-through share, p95
latency, and index freshness lag. Each number arrives with its
delta against last week and a plain marker for direction,
better, worse, or steady against declared indifference bands,
because a two-percent wiggle in click-through is weather, not
news. The digest refuses adjectives by construction, there is
no field for great week, and it refuses to render with any
metric missing, since a dashboard that quietly drops its worst
number the week it breaks is the oldest trick in reporting.
Weeks chain by label so a stack of digests reads as a story,
and the summary line picks only movements outside the bands,
which some weeks means the honest sentence is nothing moved.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

from quarry.errors import Invalid, Missing

METRICS = (
    "queries_served",
    "zero_result_share",
    "click_through_share",
    "p95_latency_ms",
    "freshness_lag_min",
)

LOWER_IS_BETTER = frozenset(
    {"zero_result_share", "p95_latency_ms", "freshness_lag_min"}
)

INDIFFERENCE = {
    "queries_served": 0.05,
    "zero_result_share": 0.02,
    "click_through_share": 0.02,
    "p95_latency_ms": 0.10,
    "freshness_lag_min": 0.15,
}


@dataclass(frozen=True)
class WeekNumbers:
    label: str
    values: dict[str, float]

    def __post_init__(self) -> None:
        missing = sorted(set(METRICS) - set(self.values))
        if missing:
            raise Missing(
                f"{self.label}: metric(s) {', '.join(missing)} "
                f"absent; a digest that drops its worst number is "
                f"the oldest trick in reporting"
            )
        strays = sorted(set(self.values) - set(METRICS))
        if strays:
            raise Invalid(
                f"{self.label}: unknown metric(s) "
                f"{', '.join(strays)}; the digest is five numbers "
                f"on purpose"
            )


def _direction(metric: str, before: float, now: float) -> str:
    if before == 0:
        return "steady" if now == 0 else "worse" if metric in LOWER_IS_BETTER else "better"
    moved = (now - before) / abs(before)
    if abs(moved) <= INDIFFERENCE[metric]:
        return "steady"
    improved = (moved < 0) == (metric in LOWER_IS_BETTER)
    return "better" if improved else "worse"


def digest(last: WeekNumbers, this: WeekNumbers) -> str:
    if last.label == this.label:
        raise Invalid(
            "both weeks carry the same label; a week compared to "
            "itself always reads steady"
        )
    lines = [f"week {this.label} (vs {last.label}):"]
    movements = []
    for metric in METRICS:
        before = last.values[metric]
        now = this.values[metric]
        mark = _direction(metric, before, now)
        lines.append(
            f"  {metric}: {now} (was {before}, {mark})"
        )
        if mark != "steady":
            movements.append(f"{metric} {mark}")
    if movements:
        lines.append("movements: " + "; ".join(movements))
    else:
        lines.append("movements: nothing moved outside the bands")
    return "\n".join(lines)


def story(weeks: list[WeekNumbers]) -> str:
    if len(weeks) < 2:
        raise Invalid(
            "a story needs at least two weeks; one week is a "
            "snapshot"
        )
    pages = []
    for last, this in itertools.pairwise(weeks):
        pages.append(digest(last, this))
    return "\n\n".join(pages)
