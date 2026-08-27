"""Freeze windows: change stops when the stakes say so, on the record.

Every retailer freezes deploys for the peak weekend and every
search team forgets one job that mutates the index anyway, so
the freeze is enforced where mutations enter rather than in a
calendar nobody reads: a window is declared with a span, a
reason, and an owner, mutating operations check the freeze
before running, and reads never check because a freeze that
blocks queries defends the index by making it useless. The
override exists because production is production, but it is
loud by design: named person, named reason, single operation,
logged into the window's own record, so the review after the
weekend reads every hole punched through the wall and who
punched it. Overlapping windows are refused, one wall at a
time, because two authorities over one calendar is how both
get ignored.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Frozen, Invalid

MUTATING = frozenset(
    {"add", "delete", "merge", "reindex", "schema_migrate"}
)
READING = frozenset({"search", "explain", "export", "health"})


@dataclass
class FreezeWindow:
    start: int
    end: int
    reason: str
    owner: str
    overrides: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise Invalid(
                f"a window from {self.start} to {self.end} never "
                f"happens"
            )
        if not self.reason.strip() or not self.owner.strip():
            raise Invalid(
                "a freeze without a reason and an owner is a wall "
                "nobody may question; both are required"
            )

    def covers(self, tick: int) -> bool:
        return self.start <= tick < self.end


@dataclass
class FreezeBoard:
    windows: list[FreezeWindow] = field(default_factory=list)

    def declare(self, window: FreezeWindow) -> str:
        for standing in self.windows:
            if (
                window.start < standing.end
                and standing.start < window.end
            ):
                raise Invalid(
                    f"the window [{window.start}, {window.end}) "
                    f"overlaps [{standing.start}, {standing.end}); "
                    f"one wall at a time"
                )
        self.windows.append(window)
        return (
            f"frozen [{window.start}, {window.end}): "
            f"{window.reason} ({window.owner})"
        )

    def _active(self, tick: int) -> FreezeWindow | None:
        for window in self.windows:
            if window.covers(tick):
                return window
        return None

    def check(self, operation: str, tick: int) -> str:
        if operation in READING:
            return f"{operation} proceeds; freezes never block reads"
        if operation not in MUTATING:
            raise Invalid(
                f"{operation!r} is neither a read nor a known "
                f"mutation; classify it before it runs during a "
                f"freeze"
            )
        window = self._active(tick)
        if window is None:
            return f"{operation} proceeds; no freeze covers {tick}"
        raise Frozen(
            f"{operation} is frozen until {window.end}: "
            f"{window.reason} (owner {window.owner}); overrides "
            f"go through punch_through, loudly"
        )

    def punch_through(
        self, operation: str, tick: int, who: str, why: str
    ) -> str:
        if not who.strip() or not why.strip():
            raise Invalid(
                "an override without a name and a reason is a "
                "hole nobody owns"
            )
        window = self._active(tick)
        if window is None:
            raise Invalid(
                f"nothing is frozen at {tick}; run the operation "
                f"normally instead of practicing overrides"
            )
        if operation not in MUTATING:
            raise Invalid(
                f"{operation!r} is not a mutation; reads need no "
                f"hole"
            )
        window.overrides.append(
            f"[{tick}] {who}: {operation} ({why})"
        )
        return (
            f"{operation} passes through the freeze once; the "
            f"hole is on the record"
        )

    def review(self) -> str:
        if not self.windows:
            return "no freeze windows declared"
        lines = []
        for window in self.windows:
            lines.append(
                f"[{window.start}, {window.end}) {window.reason} "
                f"({window.owner}): {len(window.overrides)} "
                f"override(s)"
            )
            lines.extend(
                f"  {hole}" for hole in window.overrides
            )
        return "\n".join(lines)
