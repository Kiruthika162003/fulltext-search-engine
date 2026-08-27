"""Query planning: intersect from the rarest end, and show the work.

ANDing five terms costs least when the walk starts from the
shortest posting list, because every intersection after the first
is bounded by the smallest set seen so far, and starting from the
longest list is the same answer at many times the price. The
planner orders required terms by document frequency ascending,
estimates the cost of both the chosen order and the naive
left-to-right order, and the explain output shows each step with
its running candidate bound, so a slow query's plan can be read
instead of imagined. The estimates are honest about being
estimates: they price comparisons in the worst case, the report
labels them as ceilings, and the one guarantee made is the one
that matters, that the chosen order's ceiling never exceeds the
written order's, which the planner earns by sorting rather than
by promising.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid
from quarry.segment import Segment


@dataclass(frozen=True)
class PlanStep:
    term: str
    list_length: int
    candidate_bound: int


@dataclass(frozen=True)
class Plan:
    steps: tuple[PlanStep, ...]
    cost_ceiling: int
    naive_ceiling: int

    def saved(self) -> int:
        return self.naive_ceiling - self.cost_ceiling


def plan_intersection(
    segment: Segment, field_name: str, terms: list[str]
) -> Plan:
    if not terms:
        raise Invalid("planning nothing costs nothing and means less")
    lengths: list[tuple[str, int]] = []
    for term in terms:
        held = segment.postings_for(field_name, term)
        lengths.append(
            (term, held.document_frequency() if held else 0)
        )
    ordered = sorted(lengths, key=lambda row: (row[1], row[0]))
    steps: list[PlanStep] = []
    bound: int | None = None
    cost = 0
    for term, length in ordered:
        if bound is None:
            bound = length
        else:
            cost += bound + length
            bound = min(bound, length)
        steps.append(
            PlanStep(
                term=term, list_length=length, candidate_bound=bound
            )
        )
    naive_cost = 0
    naive_bound: int | None = None
    for _term, length in lengths:
        if naive_bound is None:
            naive_bound = length
        else:
            naive_cost += naive_bound + length
            naive_bound = min(naive_bound, length)
    return Plan(
        steps=tuple(steps),
        cost_ceiling=cost,
        naive_ceiling=naive_cost,
    )


def explain(plan: Plan) -> str:
    lines = ["intersection plan, rarest first:"]
    for number, step in enumerate(plan.steps, start=1):
        lines.append(
            f"  {number}. {step.term} (list {step.list_length}, "
            f"candidates bounded at {step.candidate_bound})"
        )
    lines.append(
        f"cost ceiling {plan.cost_ceiling} comparisons against "
        f"{plan.naive_ceiling} for the written order; ceilings, not "
        f"invoices"
    )
    if plan.steps and plan.steps[0].list_length == 0:
        lines.append(
            "the rarest term matches nothing; the whole intersection "
            "is already empty and everything after step 1 is theatre"
        )
    return "\n".join(lines)
