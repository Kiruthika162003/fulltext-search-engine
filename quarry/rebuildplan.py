"""Rebuild planning: recovery is a sequence, not a scramble.

The disk came back wrong, some segments verify and some do
not, the journal holds a tail nobody flushed, and the plan for
that morning should be computed, not improvised. The planner
takes the manifest verdicts and the journal state and emits an
ordered sequence with a reason per step: verified segments
mount as they are because rebuilding the healthy wastes the
outage; corrupt segments rebuild from their manifest sources
in size order, smallest first, because early wins restore
partial service while the big one grinds; the journal replays
strictly after the rebuilds it feeds, since replaying into a
segment about to be rebuilt does the work twice; and the plan
ends with a full verify because a recovery that ends without
one is a rumor of a recovery. Every plan carries its projected
service level per phase, so whoever is on the bridge can say
how much search is back before the phone is asked.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid


@dataclass(frozen=True)
class SegmentStatus:
    name: str
    verified: bool
    live_docs: int


@dataclass(frozen=True)
class PlanStep:
    action: str
    target: str
    reason: str

    def line(self) -> str:
        return f"{self.action} {self.target}: {self.reason}"


def plan_rebuild(
    segments: list[SegmentStatus], journal_pending: int
) -> list[PlanStep]:
    if not segments:
        raise Invalid(
            "a rebuild plan over no segments plans a different "
            "outage"
        )
    healthy = [held for held in segments if held.verified]
    broken = sorted(
        (held for held in segments if not held.verified),
        key=lambda held: (held.live_docs, held.name),
    )
    total_docs = sum(held.live_docs for held in segments)
    steps: list[PlanStep] = []
    restored = 0
    for held in sorted(healthy, key=lambda one: one.name):
        restored += held.live_docs
        share = restored / total_docs if total_docs else 0.0
        steps.append(
            PlanStep(
                action="mount",
                target=held.name,
                reason=(
                    f"verified; rebuilding the healthy wastes "
                    f"the outage ({share:.0%} of corpus serving)"
                ),
            )
        )
    for held in broken:
        restored += held.live_docs
        share = restored / total_docs if total_docs else 0.0
        steps.append(
            PlanStep(
                action="rebuild",
                target=held.name,
                reason=(
                    f"failed verification; smallest first for "
                    f"early wins ({share:.0%} serving after)"
                ),
            )
        )
    if journal_pending > 0:
        steps.append(
            PlanStep(
                action="replay",
                target="journal",
                reason=(
                    f"{journal_pending} pending entrie(s), strictly "
                    f"after rebuilds so nothing is done twice"
                ),
            )
        )
    steps.append(
        PlanStep(
            action="verify",
            target="everything",
            reason=(
                "a recovery that ends without a verify is a "
                "rumor of a recovery"
            ),
        )
    )
    return steps


def bridge_page(steps: list[PlanStep]) -> str:
    if not steps:
        raise Invalid("an empty plan briefs nobody")
    lines = [
        f"{index}. {step.line()}"
        for index, step in enumerate(steps, start=1)
    ]
    rebuilds = sum(1 for step in steps if step.action == "rebuild")
    lines.append(
        f"{len(steps)} step(s), {rebuilds} rebuild(s); the plan "
        f"is the briefing"
    )
    return "\n".join(lines)
