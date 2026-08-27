"""The regression gate: a build ships when the evals say nothing broke.

Continuous relevance work needs a mechanical answer to did this
change make search worse, and the gate gives one: it runs the
whole eval registry before and after, pairs the grades by name,
and blocks the ship when any eval that held goes broken, listing
the casualties by name with their numbers on both sides. The
direction matters: an eval that was broken and stays broken is
standing debt and blocks nothing new, one that heals is
celebrated in the report, and only held-to-broken is a
regression, because gating on preexisting failures teaches teams
to delete evals instead of fixing them. The gate has no
override parameter on purpose; shipping over a regression is a
human decision that belongs in a conversation, not in a
keyword argument that will end up hardcoded to True in a
pipeline nobody rereads.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid
from quarry.evals.grade import Grade


@dataclass(frozen=True)
class GradePair:
    eval_name: str
    before_held: bool
    after_held: bool

    def state(self) -> str:
        if self.before_held and not self.after_held:
            return "REGRESSED"
        if not self.before_held and self.after_held:
            return "healed"
        if self.before_held:
            return "held"
        return "standing debt"


def pair_grades(
    before: list[Grade], after: list[Grade]
) -> list[GradePair]:
    before_map = {grade.eval_name: grade for grade in before}
    after_map = {grade.eval_name: grade for grade in after}
    missing = sorted(set(before_map) - set(after_map))
    if missing:
        raise Invalid(
            f"eval(s) {', '.join(missing)} vanished between runs; "
            f"deleting an eval is not the same as passing it"
        )
    pairs = []
    for name in sorted(after_map):
        held_after = after_map[name].holds
        held_before = (
            before_map[name].holds if name in before_map else True
        )
        pairs.append(
            GradePair(
                eval_name=name,
                before_held=held_before,
                after_held=held_after,
            )
        )
    return pairs


@dataclass(frozen=True)
class GateVerdict:
    ships: bool
    regressions: tuple[str, ...]
    healed: tuple[str, ...]
    debt: tuple[str, ...]

    def report(self) -> str:
        if self.ships:
            lines = ["SHIP: no eval that held went broken"]
        else:
            listed = ", ".join(self.regressions)
            lines = [f"BLOCKED: regressed eval(s): {listed}"]
        if self.healed:
            lines.append(
                f"healed this build: {', '.join(self.healed)}"
            )
        if self.debt:
            lines.append(
                f"standing debt (broken before and after): "
                f"{', '.join(self.debt)}"
            )
        return "\n".join(lines)


def gate(before: list[Grade], after: list[Grade]) -> GateVerdict:
    if not after:
        raise Invalid(
            "gating on zero evals approves anything; run the "
            "registry first"
        )
    pairs = pair_grades(before, after)
    regressions = tuple(
        held.eval_name
        for held in pairs
        if held.state() == "REGRESSED"
    )
    healed = tuple(
        held.eval_name for held in pairs if held.state() == "healed"
    )
    debt = tuple(
        held.eval_name
        for held in pairs
        if held.state() == "standing debt"
    )
    return GateVerdict(
        ships=not regressions,
        regressions=regressions,
        healed=healed,
        debt=debt,
    )
