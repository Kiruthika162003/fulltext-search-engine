"""ASCII sparklines: a week of numbers in one terminal line.

Reports in this codebase end in terminals, and a trend needs a
shape more than it needs digits: the sparkline maps each value
onto a seven-step ASCII ramp, lowest to highest within the
series, so the eye reads rise and fall before the mind reads a
single number. The honesty rules are small but firm: the scale
is per series and the endpoints are printed beside the line,
because a sparkline without its bounds flattens a crisis and a
calm week into the same squiggle; a flat series says flat
instead of drawing false drama at some arbitrary height; and
missing points render as a gap character rather than as zero,
since a gauge that was down is not a gauge that read nothing.
"""

from __future__ import annotations

from quarry.errors import Invalid

RAMP = ".:-=+*#"
GAP = " "


def spark(values: list[float | None]) -> str:
    if not values:
        raise Invalid("a sparkline of nothing draws nothing")
    present = [held for held in values if held is not None]
    if not present:
        raise Invalid(
            "every point is missing; the gauge was down all week"
        )
    low = min(present)
    high = max(present)
    if low == high:
        line = "".join(
            GAP if held is None else RAMP[0] for held in values
        )
        return f"{line} (flat at {low})"
    span = high - low
    steps = len(RAMP) - 1
    marks = []
    for held in values:
        if held is None:
            marks.append(GAP)
            continue
        position = round((held - low) / span * steps)
        marks.append(RAMP[position])
    return f"{''.join(marks)} ({low} to {high})"


def labeled(name: str, values: list[float | None]) -> str:
    if not name.strip():
        raise Invalid("an unlabeled sparkline decorates nothing")
    return f"{name}: {spark(values)}"
