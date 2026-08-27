"""Search feature flags: rollout by cohort, retreat by one switch.

Ranking changes ship behind flags because relevance regressions
are discovered by users, not compilers, and the flag system
carries three lessons learned the expensive way. Cohort
assignment hashes the user so an individual's experience is
stable across queries, flapping between rankers mid-session
being how users learn to distrust search. Every flag declares
its owner and its kill condition at creation, because a flag
without an owner outlives its author and a flag without a kill
condition outlives its usefulness; the ledger can always
answer which flags are past their review date. And retreat is
one switch: disabling a flag routes everyone to control
immediately with the disable recorded, no partial rollbacks,
since a half-disabled flag is two experiments wearing one
name.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from quarry.errors import Invalid, Missing


@dataclass
class Flag:
    name: str
    owner: str
    kill_condition: str
    review_day: int
    rollout_share: float = 0.0
    disabled_reason: str = ""

    def __post_init__(self) -> None:
        if not self.owner.strip():
            raise Invalid(
                f"{self.name}: a flag without an owner outlives "
                f"its author; name one"
            )
        if not self.kill_condition.strip():
            raise Invalid(
                f"{self.name}: a flag without a kill condition "
                f"outlives its usefulness; state when it dies"
            )
        if not 0.0 <= self.rollout_share <= 1.0:
            raise Invalid(
                f"{self.name}: rollout share lives in [0, 1]"
            )

    def live(self) -> bool:
        return not self.disabled_reason


@dataclass
class FlagBoard:
    flags: dict[str, Flag] = field(default_factory=dict)
    journal: list[str] = field(default_factory=list)

    def declare(self, flag: Flag) -> None:
        if flag.name in self.flags:
            raise Invalid(
                f"{flag.name} already exists; widen its rollout "
                f"instead of redeclaring it"
            )
        self.flags[flag.name] = flag
        self.journal.append(
            f"{flag.name} declared by {flag.owner}, dies when "
            f"{flag.kill_condition}"
        )

    def _flag(self, name: str) -> Flag:
        held = self.flags.get(name)
        if held is None:
            raise Missing(f"no flag named {name}")
        return held

    def widen(self, name: str, share: float, who: str) -> str:
        flag = self._flag(name)
        if not flag.live():
            raise Invalid(
                f"{name} is disabled ({flag.disabled_reason}); "
                f"a disabled flag widens to nobody"
            )
        if share <= flag.rollout_share:
            raise Invalid(
                f"{name}: {share} does not widen "
                f"{flag.rollout_share}; retreat is the disable "
                f"switch, not a narrower share"
            )
        if share > 1.0:
            raise Invalid(f"{name}: rollout share lives in [0, 1]")
        before = flag.rollout_share
        flag.rollout_share = share
        self.journal.append(
            f"{name} widened {before} -> {share} by {who}"
        )
        return f"{name} now at {share:.0%}"

    def disable(self, name: str, reason: str, who: str) -> str:
        flag = self._flag(name)
        if not reason.strip():
            raise Invalid(
                f"{name}: disabling without a reason leaves the "
                f"next reader guessing"
            )
        flag.disabled_reason = reason
        self.journal.append(
            f"{name} DISABLED by {who}: {reason}"
        )
        return f"{name} off; everyone routes to control"

    def serves(self, name: str, user: str) -> bool:
        flag = self._flag(name)
        if not flag.live():
            return False
        digest = hashlib.sha256(
            f"{name}|{user}".encode()
        ).digest()
        bucket = int.from_bytes(digest[:4], "big") / 2**32
        return bucket < flag.rollout_share

    def past_review(self, today: int) -> list[str]:
        return sorted(
            f"{flag.name}: review was day {flag.review_day}, "
            f"owner {flag.owner}"
            for flag in self.flags.values()
            if flag.live() and today > flag.review_day
        )
