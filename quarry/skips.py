"""Skip pointers: long posting lists stop being read end to end.

Intersecting a rare term with a common one walks the common
list mostly to discard it, and skip pointers are the classic
fix: every k-th posting carries a pointer past its block, the
walk peeks at the skip target before stepping through a block,
and blocks that end below the candidate are leapt in one move.
The skip interval is the square root of the list length,
rounded, the textbook balance between pointer overhead and
leap length, computed per list rather than fixed because a
fixed interval tuned for the long list punishes every short
one. The honesty in this module is the probe counter: the
skip walk and the plain walk answer the same membership
questions side by side, both count their probes, and the
savings are reported from those counters, because a data
structure justified by O-notation instead of its own counters
is a data structure nobody ever measured.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from quarry.errors import Invalid


@dataclass(frozen=True)
class SkipList:
    doc_ids: tuple[int, ...]
    interval: int

    def find(self, target: int) -> tuple[bool, int]:
        """Membership plus the probes it cost."""
        probes = 0
        index = 0
        while index + self.interval < len(self.doc_ids):
            probes += 1
            skip_to = self.doc_ids[index + self.interval]
            if skip_to < target:
                index += self.interval
            else:
                break
        while index < len(self.doc_ids):
            probes += 1
            held = self.doc_ids[index]
            if held == target:
                return True, probes
            if held > target:
                return False, probes
            index += 1
        return False, probes


def build_skiplist(doc_ids: list[int]) -> SkipList:
    if not doc_ids:
        raise Invalid("an empty list needs no skips")
    if sorted(set(doc_ids)) != doc_ids:
        raise Invalid(
            "skip pointers over unsorted ids leap into garbage"
        )
    interval = max(2, round(math.sqrt(len(doc_ids))))
    return SkipList(doc_ids=tuple(doc_ids), interval=interval)


def plain_find(doc_ids: tuple[int, ...], target: int) -> tuple[bool, int]:
    probes = 0
    for held in doc_ids:
        probes += 1
        if held == target:
            return True, probes
        if held > target:
            return False, probes
    return False, probes


def probe_report(
    doc_ids: list[int], targets: list[int]
) -> str:
    if not targets:
        raise Invalid("a report over no lookups reports nothing")
    skiplist = build_skiplist(doc_ids)
    skip_probes = 0
    plain_probes = 0
    for target in targets:
        skip_found, cost = skiplist.find(target)
        plain_found, flat_cost = plain_find(
            skiplist.doc_ids, target
        )
        if skip_found != plain_found:
            raise Invalid(
                f"the walks disagree on {target}; a skip that "
                f"changes answers is a bug wearing a speedup"
            )
        skip_probes += cost
        plain_probes += flat_cost
    ratio = plain_probes / max(skip_probes, 1)
    return (
        f"{len(targets)} lookup(s) over {len(doc_ids)} postings "
        f"(interval {skiplist.interval}): {plain_probes} plain "
        f"probes vs {skip_probes} skipped ({ratio:.1f}x), from "
        f"counters, not O-notation"
    )
