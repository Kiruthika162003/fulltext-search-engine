"""Query-side load shedding: the cheap survive, the costly wait.

When the search tier saturates, refusing everything is lazy and
refusing nothing is fatal; the shedder refuses selectively using
the cost model's own estimate: under pressure the expensive
queries shed first, because one query that walks half the index
displaces fifty cheap ones, and the pressure level decides the
cost ceiling admitted. Shed responses are honest refusals with
the estimate, the ceiling, and a retry hint, never silent empty
results, because an empty page teaches the user their query has
no answers when the truth is the cluster was busy. Interactive
queries outrank batch at every level, a stated policy rather
than an emergent accident, and the shed ledger counts what was
refused at each level so the postmortem reads decisions, not
guesses.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Frozen, Invalid

LEVELS = ("calm", "busy", "strained", "critical")
CEILINGS = {
    "calm": None,
    "busy": 500,
    "strained": 100,
    "critical": 20,
}
BATCH_PENALTY = 4


@dataclass
class LoadShedder:
    level: str = "calm"
    shed_counts: dict[str, int] = field(
        default_factory=lambda: dict.fromkeys(LEVELS, 0)
    )
    admitted: int = 0

    def set_level(self, level: str) -> str:
        if level not in LEVELS:
            raise Invalid(
                f"{level!r} is not a pressure level; the scale is "
                f"{', '.join(LEVELS)}"
            )
        before = self.level
        self.level = level
        return f"pressure {before} -> {level}"

    def _ceiling(self, interactive: bool) -> int | None:
        ceiling = CEILINGS[self.level]
        if ceiling is None:
            return None
        return ceiling if interactive else ceiling // BATCH_PENALTY

    def admit(
        self, estimated_postings: int, interactive: bool = True
    ) -> str:
        if estimated_postings < 0:
            raise Invalid("a negative estimate is not an estimate")
        ceiling = self._ceiling(interactive)
        if ceiling is not None and estimated_postings > ceiling:
            self.shed_counts[self.level] += 1
            kind = "interactive" if interactive else "batch"
            raise Frozen(
                f"shed at {self.level}: this {kind} query estimates "
                f"{estimated_postings} postings against a ceiling "
                f"of {ceiling}; narrow it or retry when pressure "
                f"drops"
            )
        self.admitted += 1
        return (
            f"admitted at {self.level}: {estimated_postings} "
            f"postings"
        )

    def ledger(self) -> str:
        sheds = ", ".join(
            f"{level}: {self.shed_counts[level]}"
            for level in LEVELS
        )
        return (
            f"level {self.level}; admitted {self.admitted}; "
            f"shed per level {sheds}"
        )
