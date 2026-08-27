"""A write-ahead journal: the add is durable before it is visible.

The gap between accepted and flushed is where crashes eat
documents, so every mutation writes to the journal first and the
buffer second: a crash replays the journal against the last
flushed state and loses nothing that was acknowledged. Entries
are numbered densely and carry a checksum of their own payload,
replay verifies both, stops at the first corrupt entry, and
reports what it kept and what it refused rather than silently
truncating, because the difference between recovered cleanly
and lost the tail is a difference the operator must see. A
checkpoint records the sequence the flush covered; replay
starts after it, and truncating the journal below the
checkpoint is the one deliberately irreversible act, guarded by
requiring the checkpoint sequence to be repeated back.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from quarry.errors import Invalid, Stale

VERBS = ("add", "delete")


def _checksum(sequence: int, verb: str, payload: str) -> str:
    body = f"{sequence}|{verb}|{payload}"
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]


@dataclass(frozen=True)
class JournalEntry:
    sequence: int
    verb: str
    payload: str
    checksum: str

    def intact(self) -> bool:
        return (
            _checksum(self.sequence, self.verb, self.payload)
            == self.checksum
        )


@dataclass
class Journal:
    entries: list[JournalEntry] = field(default_factory=list)
    checkpoint: int = -1

    def append(self, verb: str, payload: str) -> JournalEntry:
        if verb not in VERBS:
            raise Invalid(
                f"the journal records {', '.join(VERBS)}; "
                f"{verb!r} is neither"
            )
        if not payload.strip():
            raise Invalid("an empty payload journals nothing")
        sequence = len(self.entries)
        entry = JournalEntry(
            sequence=sequence,
            verb=verb,
            payload=payload,
            checksum=_checksum(sequence, verb, payload),
        )
        self.entries.append(entry)
        return entry

    def mark_checkpoint(self, sequence: int) -> str:
        if sequence < self.checkpoint:
            raise Stale(
                f"checkpoint {sequence} is behind the standing "
                f"checkpoint {self.checkpoint}; checkpoints only "
                f"advance"
            )
        if sequence >= len(self.entries):
            raise Invalid(
                f"checkpoint {sequence} covers entries that do not "
                f"exist; the journal ends at {len(self.entries) - 1}"
            )
        self.checkpoint = sequence
        return f"checkpoint at {sequence}; replay starts after it"

    def replay(self) -> tuple[list[JournalEntry], str]:
        kept: list[JournalEntry] = []
        for entry in self.entries:
            if entry.sequence <= self.checkpoint:
                continue
            if not entry.intact():
                return kept, (
                    f"REPLAY STOPPED at #{entry.sequence}: checksum "
                    f"mismatch; {len(kept)} entrie(s) recovered, the "
                    f"tail from #{entry.sequence} is lost"
                )
            kept.append(entry)
        return kept, (
            f"recovered cleanly: {len(kept)} entrie(s) after "
            f"checkpoint {self.checkpoint}"
        )

    def truncate_to_checkpoint(self, confirm_sequence: int) -> str:
        if self.checkpoint < 0:
            raise Invalid(
                "no checkpoint exists; truncating now would eat "
                "unflushed history"
            )
        if confirm_sequence != self.checkpoint:
            raise Invalid(
                f"truncation requires repeating the checkpoint "
                f"back: expected {self.checkpoint}, got "
                f"{confirm_sequence}"
            )
        dropped = sum(
            1
            for entry in self.entries
            if entry.sequence <= self.checkpoint
        )
        self.entries = [
            entry
            for entry in self.entries
            if entry.sequence > self.checkpoint
        ]
        return (
            f"dropped {dropped} flushed entrie(s); "
            f"{len(self.entries)} remain"
        )

    def status(self) -> str:
        return (
            f"{len(self.entries)} entrie(s), checkpoint at "
            f"{self.checkpoint}, "
            f"{sum(1 for held in self.entries if held.sequence > self.checkpoint)} "
            f"pending replay"
        )
