"""Canary rollout for ranking changes: a slice sees it, numbers decide.

A relevance change confident enough to ship is still a
hypothesis, and the canary is the experiment: a deterministic
slice of sessions gets the candidate ranker while everyone else
keeps the incumbent, assignment by hash of the session so a user
never flaps between arms mid-session and no coin flip needs
storing. The verdict is mechanical and pre-declared: the canary
must not lose on abandonment, the share of searches with no
click, by more than the tolerance, and must win or tie on
clicks per search. A canary that TIES ships, because the change
was wanted for other reasons and the experiment only had to
prove no harm; a canary that loses rolls back with the numbers
in the decision record, and a canary read before enough traffic
refuses to conclude at all rather than concluding early.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from quarry.errors import Invalid

CANARY_SHARE = 0.1
MIN_SEARCHES = 50
ABANDON_TOLERANCE = 0.02


def assigned_arm(session: str, share: float = CANARY_SHARE) -> str:
    if not session.strip():
        raise Invalid("a session with no name cannot be assigned")
    digest = hashlib.sha256(session.encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:4], "big") / 2**32
    return "canary" if bucket < share else "incumbent"


@dataclass
class ArmLedger:
    searches: int = 0
    clicks: int = 0
    abandoned: int = 0

    def observe(self, clicks: int) -> None:
        self.searches += 1
        if clicks == 0:
            self.abandoned += 1
        self.clicks += clicks

    def abandonment(self) -> float:
        if self.searches == 0:
            raise Invalid("no searches yet; the rate is not a number")
        return round(self.abandoned / self.searches, 4)

    def clicks_per_search(self) -> float:
        if self.searches == 0:
            raise Invalid("no searches yet; the rate is not a number")
        return round(self.clicks / self.searches, 4)


@dataclass
class Canary:
    ledgers: dict[str, ArmLedger] = field(
        default_factory=lambda: {
            "canary": ArmLedger(),
            "incumbent": ArmLedger(),
        }
    )

    def observe(self, session: str, clicks: int) -> str:
        arm = assigned_arm(session)
        self.ledgers[arm].observe(clicks)
        return arm

    def ready(self) -> bool:
        return all(
            ledger.searches >= MIN_SEARCHES
            for ledger in self.ledgers.values()
        )

    def verdict(self) -> str:
        if not self.ready():
            counts = ", ".join(
                f"{arm}: {ledger.searches}/{MIN_SEARCHES}"
                for arm, ledger in sorted(self.ledgers.items())
            )
            raise Invalid(
                f"the canary refuses to conclude early ({counts})"
            )
        canary = self.ledgers["canary"]
        incumbent = self.ledgers["incumbent"]
        abandon_gap = round(
            canary.abandonment() - incumbent.abandonment(), 4
        )
        click_gap = round(
            canary.clicks_per_search()
            - incumbent.clicks_per_search(),
            4,
        )
        numbers = (
            f"abandonment {canary.abandonment()} vs "
            f"{incumbent.abandonment()} (gap {abandon_gap}), clicks "
            f"per search {canary.clicks_per_search()} vs "
            f"{incumbent.clicks_per_search()} (gap {click_gap})"
        )
        if abandon_gap > ABANDON_TOLERANCE:
            return f"ROLL BACK: {numbers}"
        if click_gap < 0 and abandon_gap > 0:
            return f"ROLL BACK: {numbers}"
        return f"SHIP: {numbers}"
