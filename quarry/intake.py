"""The intake pipeline: one door, every gate, in declared order.

Documents enter production through cleaning, validation, quota,
journal, and only then the index, and the failure mode this
module exists to prevent is the second door: the batch job that
skips the quota check, the migration script that writes without
journaling, each a bypass that works until the audit. The
pipeline runs the gates in declared order and stops at the
first refusal with the gate named, because a document refused
by quota after being journaled would burn a journal entry for
nothing, so the order is cheap checks first and the journal
last before indexing. The receipt returned for every admission
lists each gate passed, which turns where did this document
come from into a lookup, and the pipeline counts refusals per
gate so the noisiest gate, usually validation after a feed
change, is visible on one line.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import QuarryError
from quarry.ingestclean import CleanLedger
from quarry.journal import Journal
from quarry.quotas import TenantMeter

GATES = ("clean", "validate", "quota", "journal", "index")


@dataclass(frozen=True)
class Receipt:
    external: int
    gates_passed: tuple[str, ...]

    def line(self) -> str:
        walked = " -> ".join(self.gates_passed)
        return f"doc {self.external}: {walked}"


@dataclass
class IntakePipeline:
    cleaner: CleanLedger
    meter: TenantMeter
    journal: Journal
    indexed: list[dict[str, object]] = field(default_factory=list)
    refusals: dict[str, int] = field(default_factory=dict)

    def _refuse(self, gate: str, reason: str) -> str:
        self.refusals[gate] = self.refusals.get(gate, 0) + 1
        return f"refused at {gate}: {reason}"

    def admit(
        self, body: str, required_words: int = 1
    ) -> tuple[Receipt | None, str]:
        passed: list[str] = []
        try:
            cleaned = self.cleaner.clean(body)
        except QuarryError as refused:
            return None, self._refuse("clean", str(refused))
        passed.append("clean")

        words = cleaned.split()
        if len(words) < required_words:
            return None, self._refuse(
                "validate",
                f"{len(words)} word(s) after cleaning, "
                f"{required_words} required; the feed sent "
                f"packaging",
            )
        passed.append("validate")

        try:
            self.meter.admit_document()
        except QuarryError as refused:
            return None, self._refuse("quota", str(refused))
        passed.append("quota")

        try:
            entry = self.journal.append("add", cleaned)
        except QuarryError as refused:
            self.meter.release_document()
            return None, self._refuse(
                "journal",
                f"{refused} (the quota admission was rolled back)",
            )
        passed.append("journal")

        external = entry.sequence
        self.indexed.append({"external": external, "body": cleaned})
        passed.append("index")
        return (
            Receipt(external=external, gates_passed=tuple(passed)),
            "admitted",
        )

    def gate_report(self) -> str:
        admitted = len(self.indexed)
        refused = sum(self.refusals.values())
        lines = [
            f"{admitted} admitted, {refused} refused"
        ]
        for gate in GATES:
            count = self.refusals.get(gate, 0)
            if count:
                lines.append(f"  {gate}: {count} refusal(s)")
        if self.refusals:
            noisiest = max(
                self.refusals.items(),
                key=lambda pair: (pair[1], pair[0]),
            )
            lines.append(
                f"noisiest gate: {noisiest[0]}; after a feed "
                f"change it is usually validation"
            )
        return "\n".join(lines)
