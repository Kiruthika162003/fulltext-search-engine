"""Chaos drills: failures rehearsed on purpose, verdicts on the record.

The first segment loss should not happen in production, so the
drill harness injects declared failures into a scripted scenario
and checks the system's answer against the promise: drop a
replica and the search must still answer from the survivors,
corrupt a journal tail and replay must stop loudly rather than
import garbage, fill the buffer and admission must degrade in
stages rather than die. Each drill is a named scenario with an
inject step, an expectation, and a verdict, drills run in
isolation so one failure cannot cascade into the next drill's
baseline, and the outcome report distinguishes survived,
degraded as designed, and FAILED DRILL, because the whole point
is finding the third kind here instead of at four in the
morning.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from quarry.errors import Invalid, QuarryError

VERDICTS = ("survived", "degraded as designed", "FAILED DRILL")


@dataclass(frozen=True)
class DrillResult:
    name: str
    verdict: str
    evidence: str

    def line(self) -> str:
        return f"{self.name}: {self.verdict} ({self.evidence})"


@dataclass(frozen=True)
class Drill:
    name: str
    scenario: Callable[[], str]

    def run(self) -> DrillResult:
        try:
            evidence = self.scenario()
        except QuarryError as refused:
            return DrillResult(
                name=self.name,
                verdict="degraded as designed",
                evidence=f"refused loudly: {refused}",
            )
        except Exception as died:
            return DrillResult(
                name=self.name,
                verdict="FAILED DRILL",
                evidence=f"{type(died).__name__}: {died}",
            )
        return DrillResult(
            name=self.name, verdict="survived", evidence=evidence
        )


@dataclass
class DrillBook:
    drills: list[Drill] = field(default_factory=list)
    history: list[DrillResult] = field(default_factory=list)

    def schedule(self, drill: Drill) -> None:
        if any(held.name == drill.name for held in self.drills):
            raise Invalid(
                f"a drill named {drill.name} is already scheduled; "
                f"two drills sharing a name share a verdict, which "
                f"hides one of them"
            )
        self.drills.append(drill)

    def run_all(self) -> list[DrillResult]:
        if not self.drills:
            raise Invalid(
                "a drill book with no drills certifies nothing"
            )
        results = [drill.run() for drill in self.drills]
        self.history.extend(results)
        return results

    def report(self) -> str:
        if not self.history:
            return "no drills have run"
        lines = [held.line() for held in self.history]
        failed = sum(
            1
            for held in self.history
            if held.verdict == "FAILED DRILL"
        )
        total = len(self.history)
        if failed:
            lines.append(
                f"{failed} of {total} drills FAILED; fix these "
                f"before they schedule themselves at four in the "
                f"morning"
            )
        else:
            lines.append(
                f"all {total} drills held; the failures are still "
                f"rehearsed, not imagined"
            )
        return "\n".join(lines)
