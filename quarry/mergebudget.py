"""A merge budget: maintenance pays for itself or waits its turn.

Merging segments buys faster searches with indexing downtime,
and the budget makes that trade explicit instead of ambient:
each proposed merge is priced in documents rewritten, benefit
is scored as the reduction in segment count plus the tombstones
it would finally drop, and the scheduler admits merges by best
benefit per cost until the period's rewrite budget is spent.
A merge that rewrites more than the budget alone never runs in
busy periods but is queued for the quiet window with that
stated, not dropped, because postponed maintenance that
silently disappears is how an index ends up with ninety
segments on a Friday. The plan prints price and reasoning per
decision, and refuses entirely when the budget is zero, since
zero maintenance is a decision someone should have to type.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid


@dataclass(frozen=True)
class MergeCandidate:
    name: str
    live_docs: int
    tombstones: int
    segments_in: int

    def __post_init__(self) -> None:
        if self.segments_in < 2:
            raise Invalid(
                f"{self.name}: merging {self.segments_in} segment(s) "
                f"merges nothing"
            )

    def cost(self) -> int:
        return self.live_docs

    def benefit(self) -> int:
        return (self.segments_in - 1) * 10 + self.tombstones

    def value(self) -> float:
        return round(self.benefit() / max(self.cost(), 1), 4)


@dataclass(frozen=True)
class MergeDecision:
    candidate: MergeCandidate
    admitted: bool
    reason: str

    def line(self) -> str:
        mark = "RUN" if self.admitted else "WAIT"
        return (
            f"{mark} {self.candidate.name}: cost "
            f"{self.candidate.cost()}, benefit "
            f"{self.candidate.benefit()}, {self.reason}"
        )


def plan_merges(
    candidates: list[MergeCandidate], budget_docs: int
) -> list[MergeDecision]:
    if budget_docs <= 0:
        raise Invalid(
            "a merge budget of zero is a decision to skip "
            "maintenance; type it as such where it can be seen"
        )
    if not candidates:
        return []
    ranked = sorted(
        candidates,
        key=lambda held: (-held.value(), held.name),
    )
    remaining = budget_docs
    decisions = []
    for candidate in ranked:
        if candidate.cost() > budget_docs:
            decisions.append(
                MergeDecision(
                    candidate=candidate,
                    admitted=False,
                    reason=(
                        f"larger than the whole budget "
                        f"{budget_docs}; queued for the quiet "
                        f"window"
                    ),
                )
            )
        elif candidate.cost() <= remaining:
            remaining -= candidate.cost()
            decisions.append(
                MergeDecision(
                    candidate=candidate,
                    admitted=True,
                    reason=(
                        f"best value {candidate.value()} while "
                        f"{remaining + candidate.cost()} remained"
                    ),
                )
            )
        else:
            decisions.append(
                MergeDecision(
                    candidate=candidate,
                    admitted=False,
                    reason=(
                        f"needs {candidate.cost()}, only "
                        f"{remaining} left this period"
                    ),
                )
            )
    return decisions


def plan_report(decisions: list[MergeDecision]) -> str:
    if not decisions:
        return "no merges proposed; the index is tidy or nobody looked"
    lines = [decision.line() for decision in decisions]
    run = sum(1 for decision in decisions if decision.admitted)
    spent = sum(
        decision.candidate.cost()
        for decision in decisions
        if decision.admitted
    )
    lines.append(
        f"{run} of {len(decisions)} admitted, {spent} documents "
        f"to rewrite"
    )
    return "\n".join(lines)
