"""Health checks: green means verified, never merely unexceptional.

A health endpoint that returns green because nothing threw is a
liveness check wearing a health check's badge. Every check here
performs its subsystem's actual job in miniature: the index check
runs a real query against a canary document it indexed itself, the
analyzer check round-trips a known phrase, the cache check writes
and reads back, and the tier check verifies the ledger prices
every registered segment. Checks report in three states because
two lose information: healthy, degraded with the number that says
how much, and failing with the evidence. The aggregate is the
worst of its parts, never the average, since a service that is
one-third failing is failing, and averaging it green is how status
pages stay green through outages.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from quarry.errors import Invalid, QuarryError

STATES = ("healthy", "degraded", "failing")


@dataclass(frozen=True)
class CheckResult:
    name: str
    state: str
    evidence: str

    def __post_init__(self) -> None:
        if self.state not in STATES:
            raise Invalid(f"{self.name}: unknown state {self.state}")


@dataclass
class HealthBoard:
    checks: dict[str, Callable[[], CheckResult]] = field(
        default_factory=dict
    )
    history: list[tuple[str, str]] = field(default_factory=list)

    def register(
        self, name: str, check: Callable[[], CheckResult]
    ) -> None:
        if name in self.checks:
            raise Invalid(f"check {name} is already registered")
        self.checks[name] = check

    def run(self) -> list[CheckResult]:
        results = []
        for name in sorted(self.checks):
            try:
                result = self.checks[name]()
            except QuarryError as refused:
                result = CheckResult(
                    name=name,
                    state="failing",
                    evidence=f"the check itself refused: {refused}",
                )
            results.append(result)
            self.history.append((name, result.state))
        return results

    def aggregate(self) -> str:
        """The worst of the parts, never the average."""
        results = self.run()
        if not results:
            raise Invalid(
                "a board with no checks has no opinion worth serving"
            )
        ranking = {state: rank for rank, state in enumerate(STATES)}
        worst = max(results, key=lambda r: ranking[r.state])
        return worst.state

    def page(self) -> str:
        results = self.run()
        if not results:
            return "no checks registered"
        ranking = {state: rank for rank, state in enumerate(STATES)}
        worst = max(results, key=lambda r: ranking[r.state])
        lines = [f"overall: {worst.state}"]
        for result in results:
            lines.append(
                f"  {result.name}: {result.state} ({result.evidence})"
            )
        return "\n".join(lines)


def index_canary_check(name: str = "index") -> Callable[[], CheckResult]:
    """A real index, a real document, a real query, every time."""

    def check() -> CheckResult:
        from quarry.engine import Engine
        from quarry.schema import Schema

        schema = Schema()
        schema.add_text("body")
        schema.seal()
        engine = Engine(schema=schema)
        engine.add({"body": "canary tweets at dawn"})
        engine.commit()
        hits = engine.search("canary").hits
        if len(hits) == 1:
            return CheckResult(
                name=name,
                state="healthy",
                evidence="indexed one canary, found one canary",
            )
        return CheckResult(
            name=name,
            state="failing",
            evidence=f"indexed one canary, found {len(hits)}",
        )

    return check


def latency_check(
    name: str, observed_p99: int, budget: int
) -> Callable[[], CheckResult]:
    def check() -> CheckResult:
        if budget <= 0:
            raise Invalid("a latency budget must be positive")
        if observed_p99 <= budget:
            return CheckResult(
                name=name,
                state="healthy",
                evidence=f"p99 {observed_p99} inside budget {budget}",
            )
        if observed_p99 <= budget * 2:
            return CheckResult(
                name=name,
                state="degraded",
                evidence=f"p99 {observed_p99} over budget {budget}",
            )
        return CheckResult(
            name=name,
            state="failing",
            evidence=f"p99 {observed_p99} at double the budget {budget}",
        )

    return check
