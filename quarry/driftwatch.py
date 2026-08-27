"""Corpus drift watch: the index notices when the world changes.

Relevance rots without a single failing test when the corpus
drifts out from under the tuning: documents grow longer, new
vocabulary floods in, and last quarter's constants quietly stop
fitting. The watch keeps a baseline profile, average document
length, vocabulary size per thousand documents, and the top
term share, then compares each new period against it with
declared tolerances, reporting per metric whether the movement
is noise or drift and by how much. Two rules keep it honest:
the baseline is only replaced deliberately, never by the
period that just breached it, because a baseline that follows
the drift cannot see it; and one breach is a note while a
double breach in the same period is a page, since single
metrics wobble but correlated movement means the corpus
actually changed.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid

TOLERANCES = {
    "avg_length": 0.2,
    "vocab_per_thousand": 0.3,
    "top_term_share": 0.5,
}


@dataclass(frozen=True)
class CorpusProfile:
    label: str
    avg_length: float
    vocab_per_thousand: float
    top_term_share: float

    def __post_init__(self) -> None:
        if self.avg_length <= 0 or self.vocab_per_thousand <= 0:
            raise Invalid(
                f"{self.label}: a profile with empty metrics "
                f"profiles an empty corpus; do not baseline that"
            )
        if not 0.0 < self.top_term_share <= 1.0:
            raise Invalid(
                f"{self.label}: top term share must sit in (0, 1]"
            )

    def metric(self, name: str) -> float:
        return {
            "avg_length": self.avg_length,
            "vocab_per_thousand": self.vocab_per_thousand,
            "top_term_share": self.top_term_share,
        }[name]


@dataclass(frozen=True)
class DriftFinding:
    metric_name: str
    baseline: float
    observed: float
    moved_share: float
    breached: bool

    def line(self) -> str:
        state = "DRIFT" if self.breached else "noise"
        return (
            f"{self.metric_name}: {self.baseline} -> "
            f"{self.observed} ({self.moved_share:+.0%}, {state})"
        )


@dataclass
class DriftWatch:
    baseline: CorpusProfile
    replacements: int = 0

    def compare(
        self, period: CorpusProfile
    ) -> tuple[list[DriftFinding], str]:
        if period.label == self.baseline.label:
            raise Invalid(
                "the period carries the baseline's label; comparing "
                "a profile to itself sees no drift by construction"
            )
        findings = []
        for name, tolerance in TOLERANCES.items():
            base = self.baseline.metric(name)
            seen = period.metric(name)
            moved = (seen - base) / base
            findings.append(
                DriftFinding(
                    metric_name=name,
                    baseline=base,
                    observed=seen,
                    moved_share=round(moved, 4),
                    breached=abs(moved) > tolerance,
                )
            )
        breaches = sum(1 for held in findings if held.breached)
        if breaches == 0:
            verdict = "steady: all metrics inside tolerance"
        elif breaches == 1:
            verdict = (
                "note: one metric drifted; single metrics wobble"
            )
        else:
            verdict = (
                f"PAGE: {breaches} metrics drifted together; the "
                f"corpus actually changed"
            )
        return findings, verdict

    def rebaseline(
        self, profile: CorpusProfile, reason: str
    ) -> str:
        if not reason.strip():
            raise Invalid(
                "rebaselining without a reason lets the baseline "
                "follow the drift it exists to see"
            )
        old = self.baseline.label
        self.baseline = profile
        self.replacements += 1
        return (
            f"baseline {old} -> {profile.label}: {reason} "
            f"(replacement {self.replacements})"
        )
