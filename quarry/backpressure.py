"""Backpressure: the indexer slows writers down instead of falling over.

An indexer that accepts everything during a burst dies holding
everything, so pressure is measured where it hurts, the unflushed
buffer, and the response escalates in declared stages: green
admits everything, amber admits but tells the writer to slow
with a number it can obey, red refuses bulk traffic while still
admitting single urgent documents, and black refuses everything
except the flush that fixes it. Stage changes are hysteretic,
climbing at the trigger but descending only below a lower floor,
because a buffer oscillating around one threshold would flap
between welcome and refusal on every document. Every refusal
names the stage, the fill, and what would help, and the ledger
counts time spent in each stage so capacity planning reads
history instead of anecdotes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Frozen, Invalid

STAGES = ("green", "amber", "red", "black")
CLIMB = {"amber": 0.5, "red": 0.75, "black": 0.9}
DESCEND = {"amber": 0.4, "red": 0.6, "black": 0.8}


@dataclass
class Backpressure:
    capacity: int
    filled: int = 0
    stage: str = "green"
    stage_ticks: dict[str, int] = field(
        default_factory=lambda: dict.fromkeys(STAGES, 0)
    )
    refusals: int = 0

    def __post_init__(self) -> None:
        if self.capacity <= 0:
            raise Invalid("a buffer with no capacity is a wall")

    def fill_ratio(self) -> float:
        return self.filled / self.capacity

    def _restage(self) -> None:
        """Step until stable so a deep flush descends every stage."""
        while True:
            before = self.stage
            self._step()
            if self.stage == before:
                return

    def _step(self) -> None:
        ratio = self.fill_ratio()
        if self.stage == "green":
            if ratio >= CLIMB["black"]:
                self.stage = "black"
            elif ratio >= CLIMB["red"]:
                self.stage = "red"
            elif ratio >= CLIMB["amber"]:
                self.stage = "amber"
        elif self.stage == "amber":
            if ratio >= CLIMB["black"]:
                self.stage = "black"
            elif ratio >= CLIMB["red"]:
                self.stage = "red"
            elif ratio < DESCEND["amber"]:
                self.stage = "green"
        elif self.stage == "red":
            if ratio >= CLIMB["black"]:
                self.stage = "black"
            elif ratio < DESCEND["amber"]:
                self.stage = "green"
            elif ratio < DESCEND["red"]:
                self.stage = "amber"
        elif ratio < DESCEND["black"]:
            self.stage = "red"

    def tick(self) -> None:
        self.stage_ticks[self.stage] += 1

    def admit(self, bulk: bool = False, urgent: bool = False) -> str:
        self._restage()
        if self.filled >= self.capacity:
            self.refusals += 1
            raise Frozen(
                f"the buffer is full at {self.filled}; only a flush "
                f"helps now"
            )
        if self.stage == "black" and not urgent:
            self.refusals += 1
            raise Frozen(
                f"stage black at {self.fill_ratio():.0%} full; "
                f"refusing until a flush drops the buffer below "
                f"{DESCEND['black']:.0%}"
            )
        if self.stage == "red" and bulk:
            self.refusals += 1
            raise Frozen(
                f"stage red at {self.fill_ratio():.0%} full; bulk "
                f"traffic waits, single documents still land"
            )
        self.filled += 1
        self._restage()
        if self.stage == "amber":
            return (
                f"admitted; stage amber at {self.fill_ratio():.0%}, "
                f"halve your send rate"
            )
        return "admitted"

    def flush(self, drained: int) -> str:
        if drained <= 0:
            raise Invalid("a flush that drains nothing is a no-op lie")
        if drained > self.filled:
            raise Invalid(
                f"draining {drained} from {self.filled} invents "
                f"documents"
            )
        self.filled -= drained
        before = self.stage
        self._restage()
        return f"drained {drained}; stage {before} -> {self.stage}"

    def ledger(self) -> str:
        spent = ", ".join(
            f"{stage}: {self.stage_ticks[stage]}"
            for stage in STAGES
        )
        return (
            f"stage now {self.stage} at {self.fill_ratio():.0%}; "
            f"ticks {spent}; {self.refusals} refusal(s)"
        )
