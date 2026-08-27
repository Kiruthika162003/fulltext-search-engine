"""Poison pill quarantine: the query that kills workers stops arriving.

Some queries crash the worker that runs them, and the retry
loop turns one poison query into a full outage as each worker
picks it up, dies, and hands it to the next. The quarantine
breaks the loop with a crash ledger per query fingerprint: a
query that has crashed workers twice is quarantined and refused
at admission with its history, because the third worker is not
an experiment, it is a sacrifice. Fingerprints are the
canonical query form so cosmetic variations share a ledger, a
quarantined query can be paroled by a human after a fix ships
with the parole recorded, and one crash alone quarantines
nothing since crashes have many mothers and a single
coincidence must not censor a working query. The ledger names
every crash with its worker so the postmortem starts written.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Frozen, Invalid, Missing

QUARANTINE_AT = 2


@dataclass
class PoisonLedger:
    crashes: dict[str, list[str]] = field(default_factory=dict)
    paroles: dict[str, str] = field(default_factory=dict)
    refusals: int = 0

    def record_crash(self, canonical: str, worker: str) -> str:
        if not canonical.strip() or not worker.strip():
            raise Invalid(
                "a crash needs both the query and the worker it "
                "took down"
            )
        held = self.crashes.setdefault(canonical, [])
        held.append(worker)
        if canonical in self.paroles and len(held) > QUARANTINE_AT:
            del self.paroles[canonical]
            return (
                f"{canonical!r} crashed again after parole; the "
                f"parole is revoked"
            )
        count = len(held)
        if count >= QUARANTINE_AT:
            return (
                f"{canonical!r} has crashed {count} worker(s); "
                f"quarantined"
            )
        return (
            f"{canonical!r} crashed {worker}; one crash has many "
            f"mothers, watching"
        )

    def quarantined(self, canonical: str) -> bool:
        if canonical in self.paroles:
            return False
        return len(self.crashes.get(canonical, [])) >= QUARANTINE_AT

    def admit(self, canonical: str) -> str:
        if self.quarantined(canonical):
            self.refusals += 1
            workers = ", ".join(self.crashes[canonical])
            raise Frozen(
                f"{canonical!r} is quarantined: it took down "
                f"{workers}; the third worker is a sacrifice, not "
                f"an experiment. Fix, then parole"
            )
        return "admitted"

    def parole(self, canonical: str, who: str, fix: str) -> str:
        if not self.quarantined(canonical):
            raise Missing(
                f"{canonical!r} is not quarantined; parole frees "
                f"the imprisoned, not the innocent"
            )
        if not fix.strip():
            raise Invalid(
                "parole without a named fix reruns the crash with "
                "hope as the patch"
            )
        self.paroles[canonical] = f"{who}: {fix}"
        return f"{canonical!r} paroled by {who} ({fix})"

    def report(self) -> str:
        if not self.crashes:
            return "no crashes recorded"
        lines = []
        for canonical in sorted(self.crashes):
            workers = self.crashes[canonical]
            state = (
                "PAROLED: " + self.paroles[canonical]
                if canonical in self.paroles
                else "QUARANTINED"
                if len(workers) >= QUARANTINE_AT
                else "watching"
            )
            lines.append(
                f"{canonical}: {len(workers)} crash(es) "
                f"({', '.join(workers)}) [{state}]"
            )
        lines.append(f"{self.refusals} admission(s) refused")
        return "\n".join(lines)
