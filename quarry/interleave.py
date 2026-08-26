"""Interleaving: two rankers, one result list, and the clicks decide.

Offline metrics answer whether a ranker matches the judgments;
interleaving answers whether users prefer it, and it does so
without splitting traffic into slow-moving cohorts. Team-draft
interleaving builds one list by alternating picks: a coin decides
who drafts first each round, each team picks its highest-ranked
document not yet taken, and every position remembers which team
supplied it. Clicks then score for the supplying team, the winner
is the team with more credited clicks, and the verdict requires a
margin because a one-click victory is noise wearing a medal. The
coin here is a deterministic sequence supplied by the caller, so
experiments replay exactly and the tests can force every draft
order the real world would ever produce.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid

MARGIN = 2


@dataclass(frozen=True)
class DraftedList:
    documents: tuple[int, ...]
    supplied_by: tuple[str, ...]


def team_draft(
    left: list[int],
    right: list[int],
    coin: list[bool],
    length: int = 10,
) -> DraftedList:
    """Alternate picks; True means left drafts first that round."""
    if length <= 0:
        raise Invalid("an interleaved list needs room")
    if not coin:
        raise Invalid("the draft needs its coin sequence")
    taken: set[int] = set()
    documents: list[int] = []
    supplied: list[str] = []
    round_number = 0

    def pick(source: list[int], team: str) -> None:
        for doc in source:
            if doc not in taken:
                taken.add(doc)
                documents.append(doc)
                supplied.append(team)
                return

    while len(documents) < length:
        before = len(documents)
        first_left = coin[round_number % len(coin)]
        round_number += 1
        if first_left:
            pick(left, "left")
            if len(documents) < length:
                pick(right, "right")
        else:
            pick(right, "right")
            if len(documents) < length:
                pick(left, "left")
        if len(documents) == before:
            break
    return DraftedList(
        documents=tuple(documents), supplied_by=tuple(supplied)
    )


@dataclass
class InterleaveExperiment:
    coin: list[bool]
    credits: dict[str, int] = field(default_factory=dict)
    impressions: int = 0

    def serve_and_observe(
        self,
        left: list[int],
        right: list[int],
        clicked: list[int],
        length: int = 10,
    ) -> None:
        drafted = team_draft(left, right, self.coin, length)
        self.impressions += 1
        position_of = {
            doc: index for index, doc in enumerate(drafted.documents)
        }
        for doc in clicked:
            if doc not in position_of:
                raise Invalid(
                    f"a click on doc {doc} which was never shown; check "
                    f"the instrumentation"
                )
            team = drafted.supplied_by[position_of[doc]]
            self.credits[team] = self.credits.get(team, 0) + 1

    def verdict(self, margin: int = MARGIN) -> str:
        if margin < 1:
            raise Invalid("a margin under one crowns every coin flip")
        left = self.credits.get("left", 0)
        right = self.credits.get("right", 0)
        if left - right >= margin:
            return f"left wins {left} to {right}"
        if right - left >= margin:
            return f"right wins {right} to {left}"
        return (
            f"no verdict at {left} to {right}; a difference under "
            f"{margin} is noise wearing a medal"
        )
