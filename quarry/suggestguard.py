"""Suggestion guarding: the dropdown is the most public surface.

Autocomplete is the one place the engine speaks first, before
the user finishes asking, so its content is guarded harder than
results: a blocklist of terms that must never surface however
popular, matched after the same analysis the suggester uses so
casing tricks do not slip past; a minimum evidence floor so a
term seen once cannot ride a typo into everyone's dropdown; and
a freshness rule that a term must have been seen in the recent
window, because suggesting last year's product names is how a
dropdown becomes an archaeology exhibit. Every rejection is
counted by reason, and the guard can explain any term's status
on demand, because the first question after a bad suggestion
ships is always how did that get through and the answer must
be a lookup, not an investigation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid
from quarry.tokenize import Analyzer

EVIDENCE_FLOOR = 3
FRESH_WINDOW = 90


@dataclass
class SuggestGuard:
    analyzer: Analyzer = field(default_factory=Analyzer)
    blocked: set[str] = field(default_factory=set)
    rejections: dict[str, int] = field(default_factory=dict)

    def block(self, term: str, who: str) -> str:
        analyzed = self.analyzer.terms(term)
        if not analyzed:
            raise Invalid(
                f"{term!r} analyzes to nothing; blocking it blocks "
                f"nothing"
            )
        self.blocked.add(analyzed[0])
        return f"{analyzed[0]!r} blocked by {who}"

    def _reject(self, reason: str) -> None:
        self.rejections[reason] = self.rejections.get(reason, 0) + 1

    def admit(
        self,
        term: str,
        seen_count: int,
        last_seen_day: int,
        today: int,
    ) -> bool:
        analyzed = self.analyzer.terms(term)
        if not analyzed:
            self._reject("analyzed-to-nothing")
            return False
        shaped = analyzed[0]
        if shaped in self.blocked:
            self._reject("blocklist")
            return False
        if seen_count < EVIDENCE_FLOOR:
            self._reject("thin-evidence")
            return False
        age = today - last_seen_day
        if age < 0:
            raise Invalid(
                f"{term!r} was last seen {-age} day(s) in the "
                f"future; the clock or the log is wrong"
            )
        if age > FRESH_WINDOW:
            self._reject("stale")
            return False
        return True

    def explain(
        self,
        term: str,
        seen_count: int,
        last_seen_day: int,
        today: int,
    ) -> str:
        analyzed = self.analyzer.terms(term)
        if not analyzed:
            return f"{term!r}: analyzes to nothing, never surfaces"
        shaped = analyzed[0]
        if shaped in self.blocked:
            return f"{shaped!r}: on the blocklist, never surfaces"
        if seen_count < EVIDENCE_FLOOR:
            return (
                f"{shaped!r}: seen {seen_count}x, needs "
                f"{EVIDENCE_FLOOR}; one sighting rides typos"
            )
        age = today - last_seen_day
        if age > FRESH_WINDOW:
            return (
                f"{shaped!r}: last seen {age} days ago, window is "
                f"{FRESH_WINDOW}; the dropdown is not an "
                f"archaeology exhibit"
            )
        return f"{shaped!r}: admitted"

    def filter_candidates(
        self,
        candidates: list[tuple[str, int, int]],
        today: int,
    ) -> list[str]:
        out = []
        for term, seen_count, last_seen_day in candidates:
            if self.admit(term, seen_count, last_seen_day, today):
                out.append(self.analyzer.terms(term)[0])
        return out

    def rejection_ledger(self) -> str:
        if not self.rejections:
            return "nothing rejected yet"
        rows = ", ".join(
            f"{reason}: {count}"
            for reason, count in sorted(self.rejections.items())
        )
        return f"rejections by reason: {rows}"
