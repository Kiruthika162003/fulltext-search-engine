"""A Bloom filter: definite absence, probable presence, measured.

Checking a slow store for documents that are usually absent
wastes the round trip on nothing, and the Bloom filter is the
classic gatekeeper: absent means certainly absent, skip the
trip; present means probably, pay the trip and maybe find
nothing. The filter here states its contract in numbers: bits
and hash count are derived from the declared capacity and
target false-positive rate with the standard formulas, filling
past capacity is refused rather than silently degrading,
because a filter at twice its capacity quietly answers
probably to everything, and the measured rate ships beside the
target, computed by probing keys never added, since a
probabilistic structure that never measures itself against its
own promise is one bad hash away from being a random number
generator with confidence.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field

from quarry.errors import Frozen, Invalid


def _bit_positions(
    key: str, hashes: int, bits: int
) -> list[int]:
    out = []
    for round_index in range(hashes):
        digest = hashlib.sha256(
            f"{round_index}|{key}".encode()
        ).digest()
        out.append(int.from_bytes(digest[:8], "big") % bits)
    return out


@dataclass
class BloomFilter:
    capacity: int
    target_rate: float
    bits: int = 0
    hashes: int = 0
    table: set[int] = field(default_factory=set)
    added: int = 0

    def __post_init__(self) -> None:
        if self.capacity <= 0:
            raise Invalid("a filter for nothing filters nothing")
        if not 0.0 < self.target_rate < 0.5:
            raise Invalid(
                "the target rate lives in (0, 0.5); past that, "
                "flip a coin instead"
            )
        if self.bits == 0:
            self.bits = max(
                8,
                math.ceil(
                    -self.capacity
                    * math.log(self.target_rate)
                    / (math.log(2) ** 2)
                ),
            )
        if self.hashes == 0:
            self.hashes = max(
                1,
                round(self.bits / self.capacity * math.log(2)),
            )

    def add(self, key: str) -> None:
        if self.added >= self.capacity:
            raise Frozen(
                f"the filter holds its declared {self.capacity}; "
                f"past capacity it quietly answers probably to "
                f"everything, so it refuses instead"
            )
        for position in _bit_positions(key, self.hashes, self.bits):
            self.table.add(position)
        self.added += 1

    def maybe_contains(self, key: str) -> bool:
        return all(
            position in self.table
            for position in _bit_positions(
                key, self.hashes, self.bits
            )
        )

    def measured_rate(self, probes: int = 500) -> float:
        if probes <= 0:
            raise Invalid("measuring with no probes measures nothing")
        hits = sum(
            1
            for index in range(probes)
            if self.maybe_contains(f"never-added-{index}")
        )
        return round(hits / probes, 4)

    def contract_page(self) -> str:
        measured = self.measured_rate()
        state = (
            "inside its promise"
            if measured <= self.target_rate * 2
            else "PAST ITS PROMISE, distrust the probablys"
        )
        return (
            f"{self.added}/{self.capacity} keys, {self.bits} bits, "
            f"{self.hashes} hash(es); target {self.target_rate}, "
            f"measured {measured} ({state})"
        )
