"""Correction accounting: did-you-mean is a product, so it gets a ledger.

Offering corrections costs trust when they are wrong and earns it
when they are right, and without accounting nobody knows which is
happening. The ledger records every correction offered, whether
the user took it, and what happened after: a taken correction that
led to a click is a save, a taken correction with no click is a
polite dead end, and a correction the user ignored while their
original query went on to succeed is a false alarm, the one kind
that actively teaches users to ignore the feature. The acceptance
rate alone flatters, since users take suggestions out of habit, so
the ledger's headline is the save rate among taken corrections,
with false alarms reported beside it, and a false alarm share
past the tripwire is the signal to raise the correction floor
before the feature trains everyone to skip it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid

FALSE_ALARM_TRIPWIRE = 0.2


@dataclass(frozen=True)
class CorrectionOutcome:
    original: str
    offered: str
    taken: bool
    clicked_after: bool
    original_succeeded: bool


@dataclass
class CorrectionLedger:
    rows: list[CorrectionOutcome] = field(default_factory=list)

    def record(
        self,
        original: str,
        offered: str,
        taken: bool,
        clicked_after: bool,
        original_succeeded: bool = False,
    ) -> None:
        if original == offered:
            raise Invalid(
                "a correction identical to the original is a no-op "
                "wearing a banner"
            )
        if taken and original_succeeded:
            raise Invalid(
                "a taken correction cannot also have the original "
                "succeeding; the instrumentation crossed two sessions"
            )
        self.rows.append(
            CorrectionOutcome(
                original=original,
                offered=offered,
                taken=taken,
                clicked_after=clicked_after,
                original_succeeded=original_succeeded,
            )
        )

    def offered_count(self) -> int:
        return len(self.rows)

    def acceptance_rate(self) -> float:
        if not self.rows:
            raise Invalid("no corrections offered; a rate over nothing")
        taken = sum(1 for row in self.rows if row.taken)
        return round(taken / len(self.rows), 4)

    def save_rate(self) -> float:
        """Among taken corrections, the share that led anywhere."""
        taken = [row for row in self.rows if row.taken]
        if not taken:
            raise Invalid("nothing taken yet; saves need takers")
        saves = sum(1 for row in taken if row.clicked_after)
        return round(saves / len(taken), 4)

    def false_alarm_share(self) -> float:
        if not self.rows:
            raise Invalid("no corrections offered")
        alarms = sum(
            1
            for row in self.rows
            if not row.taken and row.original_succeeded
        )
        return round(alarms / len(self.rows), 4)

    def verdict(self) -> str:
        headline = (
            f"{self.offered_count()} offered, "
            f"{self.acceptance_rate():.0%} taken, save rate "
            f"{self.save_rate():.0%} among takers"
        )
        alarms = self.false_alarm_share()
        if alarms >= FALSE_ALARM_TRIPWIRE:
            return (
                f"{headline}; FALSE ALARMS at {alarms:.0%}, past the "
                f"{FALSE_ALARM_TRIPWIRE:.0%} tripwire: raise the "
                f"correction floor before users learn to skip the "
                f"feature"
            )
        return f"{headline}; false alarms at {alarms:.0%}, inside the line"
