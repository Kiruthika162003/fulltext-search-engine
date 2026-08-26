"""The query log: what people actually ask is the roadmap nobody wrote.

Every query is a user telling the engine what the corpus should
contain, and the log is where those messages pile up unread. The
analysis here reads them: top queries by volume, the zero-result
list ranked by how often people hit the wall, the abandoned queries
where nobody clicked anything, and the reformulation pairs where a
user gave up on one phrasing and tried another within the same
session. The reformulation report is the jewel: when forty sessions
go from "cheap flights" to "budget airlines", that edge is a
synonym candidate mined from behaviour instead of guessed in a
meeting, and the mining threshold is explicit because a synonym
suggested by one frustrated user is an anecdote wearing a trend's
clothes.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

from quarry.errors import Invalid

REFORMULATION_FLOOR = 3


@dataclass(frozen=True)
class LoggedQuery:
    session: str
    text: str
    results: int
    clicked: bool


@dataclass
class QueryLog:
    rows: list[LoggedQuery] = field(default_factory=list)

    def log(
        self, session: str, text: str, results: int, clicked: bool
    ) -> None:
        if not session or not text.strip():
            raise Invalid("a log row needs a session and a query")
        if results < 0:
            raise Invalid("negative result counts are a bug upstream")
        if clicked and results == 0:
            raise Invalid(
                "a click on zero results is a contradiction; check the "
                "instrumentation"
            )
        self.rows.append(
            LoggedQuery(
                session=session,
                text=text.strip(),
                results=results,
                clicked=clicked,
            )
        )

    def top_queries(self, limit: int = 5) -> list[tuple[str, int]]:
        if limit <= 0:
            raise Invalid("a top list with no rows should not print")
        counts: dict[str, int] = {}
        for row in self.rows:
            counts[row.text] = counts.get(row.text, 0) + 1
        ranked = sorted(counts.items(), key=lambda held: (-held[1], held[0]))
        return ranked[:limit]

    def zero_result_wall(self, limit: int = 5) -> list[tuple[str, int]]:
        """The queries people keep hitting that return nothing."""
        if limit <= 0:
            raise Invalid("a wall with no rows should not print")
        counts: dict[str, int] = {}
        for row in self.rows:
            if row.results == 0:
                counts[row.text] = counts.get(row.text, 0) + 1
        ranked = sorted(counts.items(), key=lambda held: (-held[1], held[0]))
        return ranked[:limit]

    def abandonment_rate(self) -> float:
        served = [row for row in self.rows if row.results > 0]
        if not served:
            raise Invalid("no served queries yet; nothing to abandon")
        walked_away = sum(1 for row in served if not row.clicked)
        return round(walked_away / len(served), 4)

    def reformulations(self) -> dict[tuple[str, str], int]:
        """Session-adjacent pairs where the first try found nothing."""
        pairs: dict[tuple[str, str], int] = {}
        by_session: dict[str, list[LoggedQuery]] = {}
        for row in self.rows:
            by_session.setdefault(row.session, []).append(row)
        for held in by_session.values():
            for first, second in itertools.pairwise(held):
                if (
                    first.results == 0
                    and second.results > 0
                    and first.text != second.text
                ):
                    key = (first.text, second.text)
                    pairs[key] = pairs.get(key, 0) + 1
        return pairs

    def synonym_candidates(
        self, floor: int = REFORMULATION_FLOOR
    ) -> list[tuple[str, str, int]]:
        if floor < 2:
            raise Invalid(
                "a floor under two promotes anecdotes to trends"
            )
        rows = [
            (before, after, count)
            for (before, after), count in self.reformulations().items()
            if count >= floor
        ]
        rows.sort(key=lambda held: (-held[2], held[0]))
        return rows

    def briefing(self) -> str:
        lines = [f"{len(self.rows)} queries logged"]
        wall = self.zero_result_wall(3)
        if wall:
            worst = ", ".join(f"{text} ({count})" for text, count in wall)
            lines.append(f"the wall: {worst}")
        candidates = (
            self.synonym_candidates() if self.reformulations() else []
        )
        for before, after, count in candidates:
            lines.append(
                f"synonym candidate: {before!r} -> {after!r}, "
                f"{count} sessions agree"
            )
        return "\n".join(lines)
