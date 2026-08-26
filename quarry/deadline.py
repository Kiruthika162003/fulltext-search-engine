"""Query deadlines: a partial answer on time beats a full answer late.

A search that must finish by a deadline walks its segments with a
budget clock, and when the clock runs out it stops walking and
says so: the response carries which segments answered, which were
never reached, and the flag callers cannot ignore. Partial results
are safe here in a way they would not be elsewhere because
segments are independent: every hit returned is a real hit, the
loss is recall, not correctness, and the report states the loss in
documents unreached, the same honesty rule the sharded gather
follows. The degradation order is deliberate: big segments walk
first, because if the clock dies mid-search it should die having
covered the most corpus it could, not the tidiest.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid
from quarry.query import Query
from quarry.searcher import match_group
from quarry.writer import Index


@dataclass
class BudgetClock:
    """Ticks are charged by the caller; the clock only counts."""

    budget: int
    spent: int = 0

    def __post_init__(self) -> None:
        if self.budget <= 0:
            raise Invalid("a deadline of zero has already passed")

    def charge(self, ticks: int) -> None:
        if ticks < 0:
            raise Invalid("negative charges rewind time")
        self.spent += ticks

    def expired(self) -> bool:
        return self.spent >= self.budget

    def remaining(self) -> int:
        return max(0, self.budget - self.spent)


@dataclass(frozen=True)
class DeadlinePage:
    externals: tuple[int, ...]
    complete: bool
    segments_reached: tuple[str, ...]
    segments_unreached: tuple[str, ...]
    docs_unreached: int


@dataclass
class DeadlineSearcher:
    index: Index
    cost_per_doc: int = 1
    runs: int = 0
    partials: int = 0

    def search(
        self, query: Query, clock: BudgetClock, limit: int = 10
    ) -> DeadlinePage:
        if limit <= 0:
            raise Invalid("a search that wants no results should not run")
        self.runs += 1
        ordered = sorted(
            self.index.segments,
            key=lambda segment: (-segment.doc_count(), segment.name),
        )
        externals: list[int] = []
        reached: list[str] = []
        unreached: list[str] = []
        for segment in ordered:
            if clock.expired():
                unreached.append(segment.name)
                continue
            clock.charge(segment.doc_count() * self.cost_per_doc)
            reached.append(segment.name)
            matched: set[int] = set()
            for group in query.groups:
                matched.update(match_group(segment, group))
            for doc in sorted(matched):
                if segment.is_live(doc):
                    externals.append(
                        self.index.external_id(segment.name, doc)
                    )
        docs_unreached = sum(
            segment.live_count()
            for segment in self.index.segments
            if segment.name in set(unreached)
        )
        complete = not unreached
        if not complete:
            self.partials += 1
        return DeadlinePage(
            externals=tuple(sorted(externals)[:limit]),
            complete=complete,
            segments_reached=tuple(reached),
            segments_unreached=tuple(sorted(unreached)),
            docs_unreached=docs_unreached,
        )

    def partial_share(self) -> float:
        if self.runs == 0:
            raise Invalid("no runs yet; a share of nothing is a shrug")
        return round(self.partials / self.runs, 4)
