"""Runbooks as data: the 3am fix is a checklist, not a memory.

Incident knowledge lives in the heads of whoever fixed it last
until it is written as steps a stranger can follow, and the
runbook here is deliberately strict about what a step is: an
instruction, a verification that says how to know it worked,
and an escalation that says who to wake when it did not.
Executions are journaled step by step with outcomes, because
the difference between we ran the runbook and it worked and we
ran the runbook and skipped step three is the difference the
next incident review needs. A runbook with an unverifiable
step is refused at declaration, the theory being that do the
thing and hope is not a step, it is a prayer, and prayers do
not belong in the escalation path.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid, Missing

OUTCOMES = ("worked", "failed", "skipped")


@dataclass(frozen=True)
class Step:
    instruction: str
    verify_by: str
    escalate_to: str

    def __post_init__(self) -> None:
        for label, value in (
            ("instruction", self.instruction),
            ("verify_by", self.verify_by),
            ("escalate_to", self.escalate_to),
        ):
            if not value.strip():
                raise Invalid(
                    f"a step with an empty {label} is a prayer, "
                    f"not a step"
                )


@dataclass(frozen=True)
class Runbook:
    name: str
    trigger: str
    steps: tuple[Step, ...]

    def __post_init__(self) -> None:
        if not self.steps:
            raise Invalid(
                f"{self.name}: a runbook with no steps is a "
                f"sympathy card"
            )
        if not self.trigger.strip():
            raise Invalid(
                f"{self.name}: without a trigger nobody knows "
                f"when to open it"
            )


@dataclass
class Execution:
    runbook: Runbook
    operator: str
    journal: list[str] = field(default_factory=list)
    cursor: int = 0
    closed: bool = False

    def current_step(self) -> Step:
        if self.closed:
            raise Invalid("this execution is closed; open another")
        if self.cursor >= len(self.runbook.steps):
            raise Missing("all steps are done; close the execution")
        return self.runbook.steps[self.cursor]

    def report_outcome(self, outcome: str, note: str = "") -> str:
        if outcome not in OUTCOMES:
            raise Invalid(
                f"{outcome!r} is not an outcome; the choices are "
                f"{', '.join(OUTCOMES)}"
            )
        step = self.current_step()
        suffix = f" ({note})" if note.strip() else ""
        self.journal.append(
            f"step {self.cursor + 1} {outcome}{suffix}"
        )
        if outcome == "failed":
            self.journal.append(
                f"escalate to {step.escalate_to}"
            )
            self.closed = True
            return (
                f"step {self.cursor + 1} failed; wake "
                f"{step.escalate_to}, the journal is written"
            )
        if outcome == "skipped" and not note.strip():
            raise Invalid(
                "skipping without a reason is the line the "
                "incident review always asks about; say why"
            )
        self.cursor += 1
        if self.cursor == len(self.runbook.steps):
            self.closed = True
            return "runbook complete; close the incident with the journal"
        return f"next: {self.runbook.steps[self.cursor].instruction}"

    def transcript(self) -> str:
        header = (
            f"{self.runbook.name} run by {self.operator} "
            f"(trigger: {self.runbook.trigger})"
        )
        if not self.journal:
            return f"{header}\nno steps reported yet"
        return "\n".join([header, *self.journal])
