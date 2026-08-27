"""Scroll export: the whole corpus, one stable page at a time.

Search pagination serves people; scroll export serves programs
that want everything, and the two must not share machinery: a
ranked page shifts under its reader whenever a commit lands,
while an export promises each live document exactly once. The
scroll here anchors to a generation number captured when the
scroll opens: documents indexed after the anchor are not part
of this export, deletions after the anchor still exclude the
document because shipping deleted data is worse than a stale
export, and the cursor is the last external id served, which is
stable because external ids never reorder. A scroll that is
not advanced within its lease expires and says so, rather than
holding the generation pin forever for a client that went home,
and reading an expired scroll names the lease, not a vague
error, so the fix is in the message.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid, Stale

LEASE_TICKS = 10


@dataclass
class ScrollSource:
    """The exportable view: external id -> (generation, live)."""

    records: dict[int, tuple[int, bool]] = field(
        default_factory=dict
    )
    generation: int = 0

    def add(self, external: int) -> None:
        self.generation += 1
        self.records[external] = (self.generation, True)

    def delete(self, external: int) -> None:
        held = self.records.get(external)
        if held is None:
            raise Invalid(f"doc {external} was never indexed")
        self.generation += 1
        self.records[external] = (held[0], False)


@dataclass
class Scroll:
    source: ScrollSource
    page_size: int
    anchor_generation: int = -1
    cursor: int = -1
    opened_at_tick: int = 0
    last_advance_tick: int = 0
    exhausted: bool = False

    def __post_init__(self) -> None:
        if self.page_size <= 0:
            raise Invalid("a page of zero documents exports nothing")
        if self.anchor_generation < 0:
            self.anchor_generation = self.source.generation

    def _expired(self, tick: int) -> bool:
        return tick - self.last_advance_tick > LEASE_TICKS

    def next_page(self, tick: int) -> list[int]:
        if self.exhausted:
            raise Stale(
                "this scroll is exhausted; open a new one for a "
                "fresh export"
            )
        if self._expired(tick):
            raise Stale(
                f"the scroll lease lapsed: last advanced at tick "
                f"{self.last_advance_tick}, now {tick}, lease "
                f"{LEASE_TICKS}; open a new scroll"
            )
        self.last_advance_tick = tick
        page: list[int] = []
        for external in sorted(self.source.records):
            if external <= self.cursor:
                continue
            indexed_generation, live = self.source.records[external]
            if indexed_generation > self.anchor_generation:
                continue
            if not live:
                continue
            page.append(external)
            if len(page) == self.page_size:
                break
        if page:
            self.cursor = page[-1]
        if len(page) < self.page_size:
            self.exhausted = True
        return page

    def progress(self) -> str:
        eligible = sum(
            1
            for external, (generation, live) in self.source.records.items()
            if generation <= self.anchor_generation and live
        )
        state = "exhausted" if self.exhausted else "open"
        return (
            f"scroll {state}: cursor at {self.cursor}, anchored at "
            f"generation {self.anchor_generation}, {eligible} "
            f"document(s) eligible"
        )


def full_export(
    source: ScrollSource, page_size: int, start_tick: int
) -> list[list[int]]:
    scroll = Scroll(
        source=source,
        page_size=page_size,
        opened_at_tick=start_tick,
        last_advance_tick=start_tick,
    )
    pages = []
    tick = start_tick
    while not scroll.exhausted:
        page = scroll.next_page(tick)
        if page:
            pages.append(page)
        tick += 1
    return pages
