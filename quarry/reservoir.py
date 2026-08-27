"""Deterministic reservoir sampling: a fair audit sample, replayable.

Auditing every document is unaffordable and auditing the first
thousand is not an audit, it is a study of whatever loaded
first. The reservoir holds a fixed-size uniform sample of a
stream of unknown length, and this one is deterministic by
design: each document's inclusion priority is a hash of the
sample's named purpose and the document's key, the reservoir
keeps the top priorities seen, and the same purpose over the
same stream picks the same sample in any order of arrival,
which is what lets two auditors on two machines argue about
the same documents. Purpose is mandatory and distinct purposes
draw distinct samples, so the fraud audit and the quality
audit do not share blind spots, and the fairness check ships
in the module: over a large stream, each item's inclusion odds
land near size over stream length, measured, because a sampler
trusted without measuring is a sampler with a thumb on the
scale.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from quarry.errors import Invalid


def _priority(purpose: str, key: str) -> int:
    digest = hashlib.sha256(
        f"{purpose}|{key}".encode()
    ).digest()
    return int.from_bytes(digest[:8], "big")


@dataclass
class Reservoir:
    purpose: str
    size: int
    held: dict[str, int] = field(default_factory=dict)
    seen: int = 0

    def __post_init__(self) -> None:
        if not self.purpose.strip():
            raise Invalid(
                "a sample without a purpose shares blind spots "
                "with every other sample; name it"
            )
        if self.size <= 0:
            raise Invalid("a reservoir of zero audits nothing")

    def offer(self, key: str) -> bool:
        if key in self.held:
            raise Invalid(
                f"{key!r} was already offered; double offers "
                f"double its odds"
            )
        self.seen += 1
        priority = _priority(self.purpose, key)
        if len(self.held) < self.size:
            self.held[key] = priority
            return True
        floor_key = min(self.held, key=self.held.get)
        if priority > self.held[floor_key]:
            del self.held[floor_key]
            self.held[key] = priority
            return True
        return False

    def sample(self) -> list[str]:
        return sorted(self.held)

    def line(self) -> str:
        return (
            f"{self.purpose}: {len(self.held)} of {self.seen} "
            f"seen, deterministic by purpose"
        )


def same_sample_any_order(
    purpose: str, size: int, keys: list[str]
) -> bool:
    forward = Reservoir(purpose=purpose, size=size)
    for key in keys:
        forward.offer(key)
    backward = Reservoir(purpose=purpose, size=size)
    for key in reversed(keys):
        backward.offer(key)
    return forward.sample() == backward.sample()


def fairness_check(
    size: int, stream_length: int, trials: int
) -> float:
    """Average inclusion share across purposes, near size/length."""
    if trials <= 0 or stream_length < size:
        raise Invalid(
            "fairness needs trials and a stream at least as long "
            "as the reservoir"
        )
    keys = [f"doc-{n}" for n in range(stream_length)]
    included = 0
    for trial in range(trials):
        reservoir = Reservoir(purpose=f"trial-{trial}", size=size)
        for key in keys:
            reservoir.offer(key)
        if "doc-0" in reservoir.held:
            included += 1
    return round(included / trials, 4)
