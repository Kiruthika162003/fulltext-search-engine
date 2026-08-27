"""SLO accounting: the error budget is arithmetic, not a mood.

A service level objective is a promise with a denominator: this
share of searches under this latency, this share succeeding,
measured over a window. The tracker turns each observation into
budget arithmetic, a target of 99 percent means one bad request
per hundred is affordable, and the burn report says how much of
the window's budget is spent, not whether things feel fine.
Alerts fire on burn rate, spent faster than the window is
passing, because that is the only signal that predicts breach
before it happens. The two SLO sins are refused: retroactively
widening a target mid-window, which is moving the goalposts
after the shot, and reporting compliance without the sample
count, which is how one lucky request becomes a green
dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Frozen, Invalid

MIN_SAMPLE = 20


@dataclass(frozen=True)
class Objective:
    name: str
    target_share: float
    latency_ceiling: int | None = None

    def __post_init__(self) -> None:
        if not 0.5 <= self.target_share < 1.0:
            raise Invalid(
                f"{self.name}: a target of {self.target_share} is "
                f"outside [0.5, 1.0); promising everything or "
                f"nothing is not an objective"
            )

    def budget_share(self) -> float:
        return round(1.0 - self.target_share, 6)


@dataclass
class SloTracker:
    objective: Objective
    window_size: int
    good: int = 0
    bad: int = 0
    sealed: bool = False
    breaches: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.window_size < MIN_SAMPLE:
            raise Invalid(
                f"a window of {self.window_size} cannot hold a "
                f"defensible verdict; {MIN_SAMPLE} is the floor"
            )

    def observe(
        self, ok: bool, latency: int | None = None
    ) -> None:
        if self.sealed:
            raise Frozen(
                "this window is sealed; open the next one instead "
                "of backfilling history"
            )
        good = ok
        ceiling = self.objective.latency_ceiling
        if good and ceiling is not None:
            if latency is None:
                raise Invalid(
                    "the objective has a latency ceiling; an "
                    "observation without latency cannot be judged"
                )
            good = latency <= ceiling
        if good:
            self.good += 1
        else:
            self.bad += 1

    def seen(self) -> int:
        return self.good + self.bad

    def budget_total(self) -> float:
        return self.window_size * self.objective.budget_share()

    def budget_spent_share(self) -> float:
        total = self.budget_total()
        return round(self.bad / total, 4) if total else 0.0

    def burn_rate(self) -> float:
        if self.seen() == 0:
            raise Invalid("no observations; the burn is not a number")
        window_share = self.seen() / self.window_size
        return round(self.budget_spent_share() / window_share, 4)

    def alerting(self) -> bool:
        return self.seen() >= MIN_SAMPLE and self.burn_rate() > 2.0

    def retarget(self, target_share: float) -> None:
        del target_share
        raise Frozen(
            f"{self.objective.name}: the target does not move "
            f"mid-window; that is moving the goalposts after the "
            f"shot. Close this window, then declare the new "
            f"objective"
        )

    def report(self) -> str:
        if self.seen() < MIN_SAMPLE:
            return (
                f"{self.objective.name}: {self.seen()} of "
                f"{MIN_SAMPLE} observations needed before a verdict "
                f"is defensible"
            )
        spent = self.budget_spent_share()
        state = "BREACHED" if spent > 1.0 else "within budget"
        return (
            f"{self.objective.name}: {self.good}/{self.seen()} good, "
            f"budget {spent:.0%} spent at burn rate "
            f"{self.burn_rate()} ({state}, n={self.seen()})"
        )

    def close(self) -> str:
        self.sealed = True
        spent = self.budget_spent_share()
        if spent > 1.0:
            self.breaches.append(
                f"window closed breached at {spent:.0%}"
            )
        return self.report() if self.seen() >= MIN_SAMPLE else (
            f"{self.objective.name}: window closed thin with "
            f"{self.seen()} observation(s); no verdict"
        )
