"""Experiment assignment: users keep their arm, and the split is audited.

An A/B test on ranking dies two quiet deaths: users hopping
between arms mid-experiment, which blends the treatments into
mud, and an assignment split that drifted from its declared
ratio, which biases every downstream number. Assignment here is
deterministic by user and experiment, a hash, not a coin, so the
same user lands in the same arm on every visit and on every
server, and the experiment name is in the hash so one user can
be treatment in one test and control in another without the
arms correlating. The audit method checks the realised split
against the declared ratio with a tolerance, because a 50/50
that realised 70/30 means the hash is biased or the eligibility
filter is, and both invalidate the test more politely than
anyone reports.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from quarry.errors import Invalid

SPLIT_TOLERANCE = 0.05


@dataclass(frozen=True)
class Experiment:
    name: str
    treatment_share: float

    def __post_init__(self) -> None:
        if not self.name:
            raise Invalid("an unnamed experiment cannot be audited")
        if not 0.0 < self.treatment_share < 1.0:
            raise Invalid(
                f"{self.name}: a share of zero or one is not an "
                f"experiment, it is a rollout"
            )


def assign(experiment: Experiment, user: str) -> str:
    if not user:
        raise Invalid("an anonymous user cannot keep an arm")
    digest = hashlib.sha256(
        f"{experiment.name}\x00{user}".encode()
    ).digest()
    position = int.from_bytes(digest[:8], "big") / float(2**64)
    return (
        "treatment"
        if position < experiment.treatment_share
        else "control"
    )


@dataclass
class AssignmentLog:
    experiment: Experiment
    seen: dict[str, str] = field(default_factory=dict)

    def arm_for(self, user: str) -> str:
        arm = assign(self.experiment, user)
        previous = self.seen.get(user)
        if previous is not None and previous != arm:
            raise Invalid(
                f"{user} changed arms from {previous} to {arm}; "
                f"determinism broke and the experiment is mud"
            )
        self.seen[user] = arm
        return arm

    def realised_split(self) -> float:
        if not self.seen:
            raise Invalid("no assignments yet; a split over nothing")
        treated = sum(
            1 for arm in self.seen.values() if arm == "treatment"
        )
        return round(treated / len(self.seen), 4)

    def audit(self, tolerance: float = SPLIT_TOLERANCE) -> str:
        if not 0.0 < tolerance < 0.5:
            raise Invalid("the tolerance is a small fraction")
        realised = self.realised_split()
        declared = self.experiment.treatment_share
        drift = abs(realised - declared)
        if drift <= tolerance:
            return (
                f"split healthy: declared {declared:.0%}, realised "
                f"{realised:.1%} over {len(self.seen)} user(s)"
            )
        return (
            f"SPLIT DRIFTED: declared {declared:.0%}, realised "
            f"{realised:.1%}; the hash or the eligibility filter is "
            f"biased, and every downstream number is suspect"
        )
