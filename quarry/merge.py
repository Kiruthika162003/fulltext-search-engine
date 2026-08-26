"""Merging: many small segments become one, and the dead stay behind.

Every flush adds a segment, and every segment adds a term lookup to
every query, so an unmerged index gets slower at answering the same
question. The merger rewrites a set of segments into one, dropping
tombstoned documents on the way through, renumbering survivors
densely, and handing back the id remapping so the index can move
its bookmarks. The policy decides when: tiered merging picks the
smallest segments first because merge cost is proportional to what
you rewrite, and a waste trigger forces a merge when tombstones
cross a share threshold, since dead documents cost query time
forever but merge time once. Merging preserves search results by
construction, and the tests hold the merger to exactly that: same
queries, same answers, before and after.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid
from quarry.segment import Segment, SegmentBuilder
from quarry.writer import Index

TIER_FANOUT = 4
WASTE_TRIGGER = 0.25


@dataclass(frozen=True)
class MergePlan:
    segment_names: tuple[str, ...]
    reason: str


def plan_merge(index: Index) -> MergePlan | None:
    """Smallest-first tiers, with waste overriding size."""
    wasteful = [
        segment
        for segment in index.segments
        if segment.waste_share() >= WASTE_TRIGGER
    ]
    if wasteful:
        return MergePlan(
            segment_names=tuple(
                sorted(segment.name for segment in wasteful)
            ),
            reason=(
                f"waste: {len(wasteful)} segment(s) at or past "
                f"{WASTE_TRIGGER:.0%} tombstones"
            ),
        )
    if len(index.segments) < TIER_FANOUT:
        return None
    smallest = sorted(
        index.segments, key=lambda segment: (segment.doc_count(), segment.name)
    )[:TIER_FANOUT]
    return MergePlan(
        segment_names=tuple(sorted(segment.name for segment in smallest)),
        reason=f"tier: {len(index.segments)} segments, merging the "
        f"{TIER_FANOUT} smallest",
    )


def merge(index: Index, plan: MergePlan) -> Segment:
    if not plan.segment_names:
        raise Invalid("a merge of nothing produces nothing")
    chosen = [
        segment
        for segment in index.segments
        if segment.name in plan.segment_names
    ]
    if len(chosen) != len(plan.segment_names):
        missing = set(plan.segment_names) - {s.name for s in chosen}
        raise Invalid(f"the plan names absent segments: {sorted(missing)}")
    builder = SegmentBuilder(schema=index.schema)
    name = f"seg{index.next_segment}"
    index.next_segment += 1
    moved: dict[tuple[str, int], int] = {}
    for segment in chosen:
        for local in range(segment.doc_count()):
            if not segment.is_live(local):
                continue
            new_local = builder.add(segment.stored[local])
            moved[(segment.name, local)] = new_local
    if not moved:
        index.segments = [
            segment
            for segment in index.segments
            if segment.name not in plan.segment_names
        ]
        for external, (seg_name, _) in list(index.locations.items()):
            if seg_name in plan.segment_names:
                del index.locations[external]
        raise Invalid(
            "every document in the plan was dead; the segments were "
            "dropped and there is nothing to seal"
        )
    merged = builder.seal(name)
    index.segments = [
        segment
        for segment in index.segments
        if segment.name not in plan.segment_names
    ]
    index.segments.append(merged)
    for external, (seg_name, local) in list(index.locations.items()):
        if seg_name in plan.segment_names:
            key = (seg_name, local)
            if key in moved:
                index.locations[external] = (name, moved[key])
            else:
                del index.locations[external]
    return merged


def maintain(index: Index, rounds: int = 10) -> list[str]:
    """Run the policy to quiescence, reporting each merge taken."""
    taken = []
    for _ in range(rounds):
        plan = plan_merge(index)
        if plan is None:
            return taken
        try:
            merged = merge(index, plan)
            taken.append(
                f"{plan.reason} -> {merged.name} "
                f"({merged.doc_count()} docs)"
            )
        except Invalid as swept:
            taken.append(f"{plan.reason} -> {swept}")
    return taken
