"""Sessionizing: the gap defines the session, and the gap is declared.

A search session is a burst of activity with silence on both
sides, and everything downstream, abandonment, reformulation,
success rates, changes meaning with the silence threshold. So the
threshold is a declared parameter stamped onto every session the
splitter emits, never a buried constant, and the sensitivity
report shows how session counts move across candidate thresholds
so choosing one is an informed act instead of an inheritance.
Events must arrive time-ordered per user and the splitter refuses
disorder rather than sorting silently, because out-of-order events
usually mean two devices sharing one id, and gluing a phone and a
laptop into one session invents a user who searches from two
places at once. The success label is conservative: a session
succeeds only if its last query was clicked, since success in the
middle followed by more searching is a story about not finding
it after all.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid

IDLE_GAP = 30


@dataclass(frozen=True)
class SearchEvent:
    user: str
    at: int
    query: str
    clicked: bool


@dataclass(frozen=True)
class Session:
    user: str
    started: int
    ended: int
    queries: tuple[str, ...]
    succeeded: bool
    gap_used: int

    def length(self) -> int:
        return len(self.queries)


@dataclass
class Sessionizer:
    idle_gap: int = IDLE_GAP
    last_seen: dict[str, int] = field(default_factory=dict)
    open_sessions: dict[str, list[SearchEvent]] = field(
        default_factory=dict
    )
    closed: list[Session] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.idle_gap <= 0:
            raise Invalid("an idle gap of zero splits every keystroke")

    def observe(self, event: SearchEvent) -> None:
        previous = self.last_seen.get(event.user)
        if previous is not None and event.at < previous:
            raise Invalid(
                f"{event.user}: event at {event.at} arrived after "
                f"{previous}; disorder usually means two devices "
                f"sharing one id, and gluing them invents a user"
            )
        if (
            previous is not None
            and event.at - previous > self.idle_gap
        ):
            self._close(event.user)
        self.open_sessions.setdefault(event.user, []).append(event)
        self.last_seen[event.user] = event.at

    def _close(self, user: str) -> None:
        events = self.open_sessions.pop(user, [])
        if not events:
            return
        self.closed.append(
            Session(
                user=user,
                started=events[0].at,
                ended=events[-1].at,
                queries=tuple(event.query for event in events),
                succeeded=events[-1].clicked,
                gap_used=self.idle_gap,
            )
        )

    def close_all(self) -> list[Session]:
        for user in sorted(self.open_sessions):
            self._close(user)
        return self.closed

    def success_rate(self) -> float:
        if not self.closed:
            raise Invalid("no closed sessions; a rate over nothing")
        won = sum(1 for session in self.closed if session.succeeded)
        return round(won / len(self.closed), 4)


def threshold_sensitivity(
    events: list[SearchEvent], gaps: tuple[int, ...]
) -> str:
    """Session counts across candidate gaps: choose informed."""
    if not gaps:
        raise Invalid("sensitivity across no candidates informs nothing")
    lines = ["sessions by idle gap:"]
    for gap in gaps:
        splitter = Sessionizer(idle_gap=gap)
        for event in events:
            splitter.observe(event)
        count = len(splitter.close_all())
        lines.append(f"  gap {gap}: {count} session(s)")
    return "\n".join(lines)
