"""Cascade search: strict first, looser only when strictness starves.

A good result page tries the honest interpretation before the
generous one: exact terms with AND semantics first, because
when it works it is precisely what was asked; stemmed OR next,
trading precision for a page that is not empty; fuzzy last,
because corrected words are guesses wearing results' clothes.
The cascade descends only on starvation, fewer hits than the
floor, never mixes tiers in one page since a page that
interleaves exact hits with guesses teaches users to distrust
the exact ones, and every response names the tier that
produced it so the UI can say showing close matches in exactly
the case where it should. The starvation floor is declared per
call because a lookup wants one great answer while a browse
page wants twelve decent ones, and those are different
starvations.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from quarry.errors import Invalid

TIERS = ("exact", "loosened", "fuzzy")


@dataclass(frozen=True)
class CascadePage:
    tier: str
    externals: tuple[int, ...]
    starved_tiers: tuple[str, ...]

    def banner(self) -> str:
        if self.tier == "exact":
            return ""
        if self.tier == "loosened":
            return "showing broader matches; exact search found too few"
        return "showing close matches; did you mean one of these?"

    def line(self) -> str:
        starved = (
            ", ".join(self.starved_tiers)
            if self.starved_tiers
            else "none"
        )
        return (
            f"tier {self.tier}: {len(self.externals)} hit(s) "
            f"(starved: {starved})"
        )


def cascade(
    tiers: dict[str, Callable[[], list[int]]],
    floor: int,
) -> CascadePage:
    if floor <= 0:
        raise Invalid(
            "a starvation floor of zero never starves; the "
            "cascade would be a plain search"
        )
    missing = [name for name in TIERS if name not in tiers]
    if missing:
        raise Invalid(
            f"the cascade needs every tier; missing "
            f"{', '.join(missing)}"
        )
    starved: list[str] = []
    for name in TIERS:
        found = tiers[name]()
        deduped = tuple(dict.fromkeys(found))
        if len(deduped) >= floor:
            return CascadePage(
                tier=name,
                externals=deduped,
                starved_tiers=tuple(starved),
            )
        starved.append(name)
        last = deduped
    return CascadePage(
        tier=TIERS[-1],
        externals=last,
        starved_tiers=tuple(starved[:-1]),
    )


def cascade_trace(
    tiers: dict[str, Callable[[], list[int]]], floor: int
) -> str:
    """The whole descent narrated, for the relevance engineer."""
    lines = [f"floor {floor}:"]
    for name in TIERS:
        found = tuple(dict.fromkeys(tiers[name]()))
        state = (
            "SERVES"
            if len(found) >= floor
            else f"starves ({len(found)} under {floor})"
        )
        lines.append(f"  {name}: {len(found)} hit(s), {state}")
        if len(found) >= floor:
            break
    return "\n".join(lines)
