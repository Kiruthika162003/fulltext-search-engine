"""Shadow indexing: the new pipeline proves itself on real traffic.

Rebuilding an index on a new pipeline and cutting over on faith
is how relevance regressions ship at scale, so the shadow runs
both: every write goes to the live index and its shadow, every
sampled query runs against both, and the comparator records
where they disagree, docs present on one side only, rankings
that inverted, latencies that diverged. Writes to the shadow
must never fail the live path, a shadow write error is counted
and the live answer ships, because the shadow is an experiment
and experiments do not get to break production. Cutover has a
numeric bar declared up front, agreement above the threshold
over at least the minimum sampled queries, and the readiness
report says exactly which number is still short, so the
cutover meeting is a reading, not a debate.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid

AGREEMENT_BAR = 0.95
MIN_SAMPLES = 50


@dataclass
class ShadowLedger:
    live_writes: int = 0
    shadow_writes: int = 0
    shadow_write_errors: int = 0
    compared: int = 0
    agreed: int = 0
    disagreements: list[str] = field(default_factory=list)

    def record_write(self, shadow_ok: bool) -> str:
        self.live_writes += 1
        if shadow_ok:
            self.shadow_writes += 1
            return "written to both"
        self.shadow_write_errors += 1
        return (
            "live write landed; the shadow write failed and was "
            "counted, not raised"
        )

    def record_comparison(
        self,
        canonical: str,
        live_ids: list[int],
        shadow_ids: list[int],
    ) -> str:
        self.compared += 1
        if live_ids == shadow_ids:
            self.agreed += 1
            return "agreed"
        live_only = [
            doc for doc in live_ids if doc not in shadow_ids
        ]
        shadow_only = [
            doc for doc in shadow_ids if doc not in live_ids
        ]
        if live_only or shadow_only:
            detail = (
                f"membership: live-only {live_only}, shadow-only "
                f"{shadow_only}"
            )
        else:
            detail = "same documents, different order"
        self.disagreements.append(f"{canonical!r}: {detail}")
        return f"disagreed ({detail})"

    def agreement(self) -> float:
        if self.compared == 0:
            raise Invalid(
                "no comparisons yet; agreement over nothing is a "
                "shrug"
            )
        return round(self.agreed / self.compared, 4)

    def ready_to_cut(self) -> tuple[bool, str]:
        shortfalls = []
        if self.compared < MIN_SAMPLES:
            shortfalls.append(
                f"only {self.compared} of {MIN_SAMPLES} sampled "
                f"queries"
            )
        if self.compared > 0 and self.agreement() < AGREEMENT_BAR:
            shortfalls.append(
                f"agreement {self.agreement()} under the "
                f"{AGREEMENT_BAR} bar"
            )
        if self.shadow_write_errors > 0:
            shortfalls.append(
                f"{self.shadow_write_errors} shadow write "
                f"error(s) unexplained"
            )
        if shortfalls:
            return False, "NOT READY: " + "; ".join(shortfalls)
        return True, (
            f"READY: {self.agreement():.0%} agreement over "
            f"{self.compared} queries, shadow writes clean"
        )

    def disagreement_digest(self, top_n: int = 5) -> str:
        if not self.disagreements:
            return "no disagreements recorded"
        lines = self.disagreements[:top_n]
        remaining = len(self.disagreements) - len(lines)
        if remaining > 0:
            lines.append(f"and {remaining} more")
        return "\n".join(lines)
