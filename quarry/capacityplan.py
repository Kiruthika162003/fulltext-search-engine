"""Capacity planning: when this index outgrows its box, with working.

The question arrives as are we fine and deserves a number: given
the document count over recent periods, the planner fits growth
honestly, linear because index growth in documents usually is,
using least squares over the observed points rather than the
last two, since the last two periods are where the noise lives.
The answer states the fitted rate, the current headroom, and the
period in which the line crosses capacity, with the deliberate
refusals stated: two points make a line but not a trend, so
fewer than three periods refuse to forecast; a negative fitted
slope reports shrinking and declines to predict a crossing; and
a forecast further out than the observed history is labeled
extrapolation, because a quarter of data does not honestly
predict a year.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid

MIN_PERIODS = 3


@dataclass(frozen=True)
class GrowthFit:
    slope: float
    intercept: float
    points: int

    def level_at(self, period: int) -> float:
        return self.intercept + self.slope * period


def fit_growth(counts: list[int]) -> GrowthFit:
    if len(counts) < MIN_PERIODS:
        raise Invalid(
            f"{len(counts)} period(s) make a line but not a trend; "
            f"{MIN_PERIODS} are the floor"
        )
    if any(count < 0 for count in counts):
        raise Invalid("a negative document count is a counting bug")
    n = len(counts)
    mean_x = (n - 1) / 2
    mean_y = sum(counts) / n
    top = sum(
        (x - mean_x) * (y - mean_y) for x, y in enumerate(counts)
    )
    bottom = sum((x - mean_x) ** 2 for x in range(n))
    slope = top / bottom
    intercept = mean_y - slope * mean_x
    return GrowthFit(
        slope=round(slope, 4),
        intercept=round(intercept, 4),
        points=n,
    )


@dataclass(frozen=True)
class Forecast:
    verdict: str
    crossing_period: int | None
    extrapolated: bool

    def line(self) -> str:
        tail = " [extrapolation]" if self.extrapolated else ""
        return f"{self.verdict}{tail}"


def forecast_crossing(
    counts: list[int], capacity: int
) -> Forecast:
    if capacity <= 0:
        raise Invalid("a capacity of zero is already crossed")
    fit = fit_growth(counts)
    current = counts[-1]
    if current >= capacity:
        return Forecast(
            verdict=(
                f"already over: {current} of {capacity} documents"
            ),
            crossing_period=len(counts) - 1,
            extrapolated=False,
        )
    if fit.slope <= 0:
        manner = (
            "flat"
            if fit.slope == 0
            else f"shrinking at {abs(fit.slope)} per period"
        )
        return Forecast(
            verdict=f"{manner}; no crossing to predict",
            crossing_period=None,
            extrapolated=False,
        )
    period = len(counts) - 1
    while fit.level_at(period) < capacity:
        period += 1
        if period > len(counts) * 100:
            return Forecast(
                verdict=(
                    "the crossing is beyond a hundred histories "
                    "away; capacity is not the problem"
                ),
                crossing_period=None,
                extrapolated=True,
            )
    ahead = period - (len(counts) - 1)
    extrapolated = ahead > len(counts)
    headroom = capacity - current
    return Forecast(
        verdict=(
            f"headroom {headroom} documents; at "
            f"{fit.slope}/period the line crosses {capacity} in "
            f"period {period}, {ahead} period(s) from now"
        ),
        crossing_period=period,
        extrapolated=extrapolated,
    )
