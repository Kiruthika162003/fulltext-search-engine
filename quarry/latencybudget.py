"""Per-stage latency budgets: the deadline is divided before it is spent.

A 100 millisecond search deadline dies by a thousand cuts when
every stage assumes it can take fifty, so the budget divides the
deadline across the pipeline up front: parse, retrieve, score,
rerank, and render each own a declared slice, and a stage that
overruns its slice is named at the point of overrun rather than
discovered in the total. The remainder rule is what makes this
practical: a stage that finishes early donates its leftover to
the stages after it, because punishing early finishers with a
use-it-or-lose-it rule teaches stages to pad, while a stage that
overruns eats into the donation pool before it eats into anyone
else's slice. The report shows each stage's slice, spend, and
balance, and the total only breaches when the pool itself runs
dry, which is the arithmetic actually matching how deadlines
die.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid

STAGES = ("parse", "retrieve", "score", "rerank", "render")


@dataclass(frozen=True)
class StageSpend:
    stage: str
    slice_ms: int
    spent_ms: int

    def balance(self) -> int:
        return self.slice_ms - self.spent_ms

    def line(self) -> str:
        state = (
            "on time"
            if self.balance() >= 0
            else f"over by {-self.balance()}ms"
        )
        return (
            f"{self.stage}: {self.spent_ms}ms of {self.slice_ms}ms "
            f"({state})"
        )


@dataclass
class LatencyBudget:
    slices: dict[str, int]
    spends: list[StageSpend] = field(default_factory=list)
    pool_ms: int = 0

    def __post_init__(self) -> None:
        unknown = sorted(set(self.slices) - set(STAGES))
        if unknown:
            raise Invalid(
                f"unknown stage(s) {', '.join(unknown)}; the "
                f"pipeline is {', '.join(STAGES)}"
            )
        missing = sorted(set(STAGES) - set(self.slices))
        if missing:
            raise Invalid(
                f"stage(s) {', '.join(missing)} have no slice; an "
                f"unbudgeted stage spends everyone else's time"
            )
        if any(ms <= 0 for ms in self.slices.values()):
            raise Invalid("every stage needs a positive slice")

    def total_budget(self) -> int:
        return sum(self.slices.values())

    def charge(self, stage: str, spent_ms: int) -> str:
        if stage not in self.slices:
            raise Invalid(f"{stage} is not a pipeline stage")
        expected = STAGES[len(self.spends)] if len(
            self.spends
        ) < len(STAGES) else None
        if stage != expected:
            raise Invalid(
                f"stages spend in pipeline order; expected "
                f"{expected}, got {stage}"
            )
        if spent_ms < 0:
            raise Invalid("negative time is a clock bug")
        held = StageSpend(
            stage=stage,
            slice_ms=self.slices[stage],
            spent_ms=spent_ms,
        )
        self.spends.append(held)
        self.pool_ms += held.balance()
        if held.balance() >= 0:
            return f"{stage} finished with {held.balance()}ms spare"
        if self.pool_ms >= 0:
            return (
                f"{stage} overran by {-held.balance()}ms, covered "
                f"by the donation pool ({self.pool_ms}ms left)"
            )
        return (
            f"{stage} overran and the pool is dry "
            f"({-self.pool_ms}ms into the deadline)"
        )

    def breached(self) -> bool:
        return self.pool_ms < 0

    def report(self) -> str:
        if not self.spends:
            return "no stages have run"
        lines = [held.line() for held in self.spends]
        total_spent = sum(held.spent_ms for held in self.spends)
        state = (
            "DEADLINE BREACHED"
            if self.breached()
            else "inside the deadline"
        )
        lines.append(
            f"total {total_spent}ms of {self.total_budget()}ms: "
            f"{state}"
        )
        return "\n".join(lines)


def even_budget(deadline_ms: int) -> LatencyBudget:
    if deadline_ms < len(STAGES):
        raise Invalid(
            f"{deadline_ms}ms cannot cover {len(STAGES)} stages"
        )
    share = deadline_ms // len(STAGES)
    slices = dict.fromkeys(STAGES, share)
    slices["render"] += deadline_ms - share * len(STAGES)
    return LatencyBudget(slices=slices)
