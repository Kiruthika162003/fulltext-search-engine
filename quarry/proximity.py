"""Proximity: words that appear near each other are talking about it.

Between the exact phrase and the anywhere-in-the-document bag sits
the query most people mean: these words, close together, in any
order. The span machinery finds, per document, the tightest window
containing every term at least once, using the classic pointer
walk over the sorted position lists: advance the pointer at the
minimum position, track the best window seen, stop when any list
runs out. The proximity boost then converts tightness into score,
scaled so that adjacency earns the full bonus and windows wider
than the horizon earn exactly nothing, with the decay linear
because a ranking factor whose shape nobody can sketch on a napkin
is a ranking factor nobody can debug. Single-term queries have no
proximity and score no bonus, stated plainly rather than
special-cased into a surprise.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid
from quarry.segment import Segment

HORIZON = 8
FULL_BONUS = 1.0


@dataclass(frozen=True)
class SpanWindow:
    doc: int
    start: int
    end: int

    def width(self) -> int:
        return self.end - self.start


def tightest_window(
    position_lists: list[tuple[int, ...]],
) -> tuple[int, int] | None:
    """The smallest position range touching every list, or None."""
    if not position_lists:
        raise Invalid("a window over no terms is not a window")
    if any(not held for held in position_lists):
        return None
    if len(position_lists) == 1:
        only = position_lists[0][0]
        return (only, only)
    pointers = [0] * len(position_lists)
    best: tuple[int, int] | None = None
    while True:
        current = [
            held[pointer]
            for held, pointer in zip(position_lists, pointers, strict=True)
        ]
        low = min(current)
        high = max(current)
        if best is None or high - low < best[1] - best[0]:
            best = (low, high)
        mover = current.index(low)
        pointers[mover] += 1
        if pointers[mover] >= len(position_lists[mover]):
            return best


def span_windows(
    segment: Segment, field_name: str, terms: list[str]
) -> list[SpanWindow]:
    """Per document holding every term, its tightest window."""
    if not terms:
        raise Invalid("spans need terms")
    lists = []
    for term in terms:
        held = segment.postings_for(field_name, term)
        if held is None:
            return []
        lists.append(held)
    candidates = lists[0].docs()
    for held in lists[1:]:
        candidates = [doc for doc in candidates if held.find(doc)]
    windows = []
    for doc in candidates:
        found = tightest_window(
            [held.find(doc).positions for held in lists]
        )
        if found is not None:
            windows.append(
                SpanWindow(doc=doc, start=found[0], end=found[1])
            )
    return windows


def proximity_bonus(
    window_width: int,
    term_count: int,
    horizon: int = HORIZON,
    full_bonus: float = FULL_BONUS,
) -> float:
    """Linear decay from adjacency to the horizon.

    Adjacent means width equals term_count minus one; anything at or
    past the horizon earns zero. Single terms earn zero by
    definition, not by accident.
    """
    if horizon <= 0:
        raise Invalid("the horizon must be positive")
    if term_count < 1:
        raise Invalid("a bonus needs at least one term")
    if term_count == 1:
        return 0.0
    slack = window_width - (term_count - 1)
    if slack < 0:
        raise Invalid(
            f"width {window_width} cannot hold {term_count} distinct "
            f"positions"
        )
    if slack >= horizon:
        return 0.0
    return round(full_bonus * (1.0 - slack / horizon), 6)


def near(
    segment: Segment,
    field_name: str,
    terms: list[str],
    within: int,
) -> list[int]:
    """Documents whose tightest window slack is inside the limit."""
    if within < 0:
        raise Invalid("a negative nearness asks words to overlap")
    return [
        window.doc
        for window in span_windows(segment, field_name, terms)
        if window.width() - (len(terms) - 1) <= within
    ]
