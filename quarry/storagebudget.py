"""Storage budgeting: every byte category accounted, none surprising.

Indexes grow in four places, postings, positions, stored
fields, and tombstone bookkeeping, and the bill arrives as one
number unless someone keeps the categories apart. The budget
does exactly that: each category reports its estimated bytes
with the arithmetic it used, cost per posting or per position
stated as constants that are visibly guesses, calibratable
against a measured segment, and the projection multiplies
today's per-document averages by tomorrow's document count so
the answer to can we afford double is a subtraction, not a
meeting. The one hard rule is that positions dominate and the
report must say so when they do, because the common surprise
is a phrase-heavy schema paying triple for positions nobody
queries, and the fix, disabling positions on fields that never
see phrases, is only found when the category is visible.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid

POSTING_BYTES = 8
POSITION_BYTES = 4
TOMBSTONE_BYTES = 4
STORED_OVERHEAD = 16


@dataclass(frozen=True)
class StorageEstimate:
    postings_bytes: int
    positions_bytes: int
    stored_bytes: int
    tombstone_bytes: int

    def total(self) -> int:
        return (
            self.postings_bytes
            + self.positions_bytes
            + self.stored_bytes
            + self.tombstone_bytes
        )

    def dominant(self) -> str:
        pairs = [
            ("postings", self.postings_bytes),
            ("positions", self.positions_bytes),
            ("stored fields", self.stored_bytes),
            ("tombstones", self.tombstone_bytes),
        ]
        pairs.sort(key=lambda pair: -pair[1])
        return pairs[0][0]

    def report(self) -> str:
        total = self.total()
        if total == 0:
            return "an empty index stores nothing"
        lines = []
        for label, count in (
            ("postings", self.postings_bytes),
            ("positions", self.positions_bytes),
            ("stored fields", self.stored_bytes),
            ("tombstones", self.tombstone_bytes),
        ):
            share = count / total
            lines.append(f"{label}: {count} bytes ({share:.0%})")
        lines.append(f"total: {total} bytes")
        leader = self.dominant()
        if leader == "positions":
            lines.append(
                "positions dominate: if phrase queries are rare "
                "on some fields, disabling positions there is the "
                "cheap win"
            )
        return "\n".join(lines)


def estimate_storage(
    posting_entries: int,
    position_entries: int,
    stored_chars: int,
    tombstones: int,
) -> StorageEstimate:
    if min(
        posting_entries, position_entries, stored_chars, tombstones
    ) < 0:
        raise Invalid("negative counts are counting bugs")
    if position_entries < posting_entries:
        raise Invalid(
            f"{position_entries} positions under {posting_entries} "
            f"postings is impossible; every posting holds at least "
            f"one position"
        )
    return StorageEstimate(
        postings_bytes=posting_entries * POSTING_BYTES,
        positions_bytes=position_entries * POSITION_BYTES,
        stored_bytes=stored_chars + STORED_OVERHEAD,
        tombstone_bytes=tombstones * TOMBSTONE_BYTES,
    )


def project_growth(
    current: StorageEstimate,
    current_docs: int,
    future_docs: int,
    budget_bytes: int,
) -> str:
    if current_docs <= 0:
        raise Invalid("projection needs at least one current document")
    if future_docs < current_docs:
        raise Invalid(
            "projecting shrinkage with a growth tool inverts the "
            "arithmetic; use the numbers directly"
        )
    scale = future_docs / current_docs
    projected = int(current.total() * scale)
    if projected <= budget_bytes:
        headroom = budget_bytes - projected
        return (
            f"{future_docs} documents project to {projected} bytes; "
            f"fits with {headroom} to spare"
        )
    overrun = projected - budget_bytes
    return (
        f"{future_docs} documents project to {projected} bytes; "
        f"OVER BUDGET by {overrun}, dominated by "
        f"{current.dominant()}"
    )
