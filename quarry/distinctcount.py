"""Distinct counting by sketch: cardinality at register price.

How many distinct queries ran today is a set-size question, and
holding the set costs what the set costs; the register sketch
answers from fixed memory: hash every member, route it to a
register by its low bits, keep per register the longest run of
leading zeros any member showed, and estimate the cardinality
from the harmonic mean of the registers, because a set that
produced a twelve-zero run somewhere was probably thousands
deep. The module keeps the classic's disciplines: register
count is a power of two so routing is a mask rather than a
modulo with opinions, the estimate carries its expected error,
roughly one over the square root of the register count, small
counts fall back to exact counting through the same interface
because the sketch is embarrassing under a few dozen, and
merging sketches takes the register-wise maximum, which is the
whole reason shards can count together without sharing sets.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field

from quarry.errors import Invalid

REGISTER_BITS = 6
REGISTERS = 1 << REGISTER_BITS
SMALL_EXACT = 3 * REGISTERS


def _hashed(member: str) -> int:
    digest = hashlib.sha256(member.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _leading_zero_run(value: int, width: int = 58) -> int:
    for run, shift in enumerate(range(width - 1, -1, -1)):
        if value & (1 << shift):
            return run
    return width


@dataclass
class DistinctCounter:
    registers: list[int] = field(
        default_factory=lambda: [0] * REGISTERS
    )
    small: set[str] = field(default_factory=set)

    def observe(self, member: str) -> None:
        if not member:
            raise Invalid("the empty string is nobody")
        if len(self.small) <= SMALL_EXACT:
            self.small.add(member)
        hashed = _hashed(member)
        register = hashed & (REGISTERS - 1)
        remainder = hashed >> REGISTER_BITS
        run = _leading_zero_run(remainder) + 1
        self.registers[register] = max(self.registers[register], run)

    def estimate(self) -> tuple[int, str]:
        if len(self.small) <= SMALL_EXACT:
            return len(self.small), (
                f"exact: {len(self.small)} distinct (under "
                f"{SMALL_EXACT}, the sketch is embarrassing here)"
            )
        alpha = 0.709
        harmonic = sum(
            2.0**-run for run in self.registers
        )
        raw = alpha * REGISTERS * REGISTERS / harmonic
        error = 1.04 / math.sqrt(REGISTERS)
        return round(raw), (
            f"~{round(raw)} distinct +/- {error:.0%} "
            f"({REGISTERS} registers)"
        )


def merged(counters: list[DistinctCounter]) -> DistinctCounter:
    if not counters:
        raise Invalid("merging no counters counts nothing")
    out = DistinctCounter()
    for held in counters:
        for index in range(REGISTERS):
            out.registers[index] = max(
                out.registers[index], held.registers[index]
            )
        out.small |= held.small
    return out
