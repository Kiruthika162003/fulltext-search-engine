"""Scripted scoring: business rules join the ranking, declared and capped.

Sooner or later somebody needs freshness, stock status, or a
margin tier to influence order, and the two failure modes are both
famous: hardcoding business rules into the scorer, or exposing a
scripting language that lets a template outrank relevance forever.
The middle path here is a small set of declared factor types,
recency decay, numeric scaling, and flag bonuses, each with a cap,
composed by addition onto the relevance score. The composition
rule that keeps search being search: the sum of every factor cap
must stay under the configured share of a typical relevance score,
so business signals tilt close calls and can never bury a plainly
better match. Every factor evaluates to an auditable line, and
the explain output shows relevance and factors side by side,
because the merchandiser and the engineer argue better over the
same table.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid

TILT_SHARE = 0.5
TYPICAL_RELEVANCE = 1.0


@dataclass(frozen=True)
class FactorValue:
    name: str
    value: float
    detail: str


@dataclass(frozen=True)
class RecencyFactor:
    name: str
    field: str
    half_life: int
    cap: float

    def __post_init__(self) -> None:
        if self.half_life <= 0:
            raise Invalid(f"{self.name}: a half life must be positive")
        if self.cap <= 0:
            raise Invalid(f"{self.name}: a cap of zero contributes nothing")

    def evaluate(self, document: dict, now: int) -> FactorValue:
        raw = document.get(self.field)
        if raw is None:
            return FactorValue(
                name=self.name, value=0.0, detail=f"no {self.field}"
            )
        age = max(0, now - int(raw))
        halvings = age / self.half_life
        value = round(self.cap * (0.5**halvings), 6)
        return FactorValue(
            name=self.name,
            value=value,
            detail=f"age {age}, {halvings:.1f} half-lives",
        )


@dataclass(frozen=True)
class FlagFactor:
    name: str
    field: str
    expected: object
    cap: float

    def __post_init__(self) -> None:
        if self.cap <= 0:
            raise Invalid(f"{self.name}: a cap of zero contributes nothing")

    def evaluate(self, document: dict, now: int) -> FactorValue:
        held = document.get(self.field)
        if held == self.expected:
            return FactorValue(
                name=self.name,
                value=self.cap,
                detail=f"{self.field}={held!r}",
            )
        return FactorValue(
            name=self.name,
            value=0.0,
            detail=f"{self.field}={held!r}, wanted {self.expected!r}",
        )


@dataclass
class ScorePlan:
    factors: list
    tilt_share: float = TILT_SHARE

    def __post_init__(self) -> None:
        if not self.factors:
            raise Invalid("a plan without factors is plain relevance; use that")
        names = [factor.name for factor in self.factors]
        if len(set(names)) != len(names):
            raise Invalid("two factors share a name; the table needs both")
        total_cap = sum(factor.cap for factor in self.factors)
        budget = TYPICAL_RELEVANCE * self.tilt_share
        if total_cap > budget:
            raise Invalid(
                f"factor caps sum to {total_cap}, past the tilt budget "
                f"of {budget}; business signals tilt close calls, they "
                f"do not bury better matches"
            )

    def score(
        self, relevance: float, document: dict, now: int
    ) -> tuple[float, list[FactorValue]]:
        values = [
            factor.evaluate(document, now) for factor in self.factors
        ]
        total = relevance + sum(value.value for value in values)
        return round(total, 6), values

    def explain(
        self, relevance: float, document: dict, now: int
    ) -> str:
        total, values = self.score(relevance, document, now)
        lines = [f"relevance {relevance}"]
        for value in values:
            lines.append(
                f"  + {value.name}: {value.value} ({value.detail})"
            )
        lines.append(f"= {total}")
        return "\n".join(lines)
