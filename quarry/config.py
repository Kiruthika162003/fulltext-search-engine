"""Engine configuration: every knob validated, every change a diff.

Configuration outlives code reviews: a setting changed in
production at midnight is invisible until it bites, so the config
object validates every knob at construction with the reason each
bound exists, and changes go through apply(), which returns the
diff of what actually moved rather than trusting the caller's
description of what they meant to change. Unknown keys are refused
by name with the roster, because a typoed setting that silently
does nothing is worse than a crash: the operator believes the
knob turned. The frozen marker protects the settings that must
survive the midnight temptation, flush thresholds during an
incident being the classic, and unfreezing is not provided,
because a freeze with an unfreeze beside it is a speed bump, not
a guard.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid

KNOBS = {
    "flush_at": (1, 100_000, "buffered documents before a flush"),
    "cache_capacity": (1, 1_000_000, "result cache slots"),
    "slow_line": (1, 60_000, "ticks before a query is slow"),
    "suggestion_floor": (0, 100, "hits below which corrections show"),
    "merge_fanout": (2, 64, "segments merged per pass"),
}
FROZEN = {"flush_at"}


@dataclass
class EngineConfig:
    values: dict[str, int] = field(default_factory=dict)
    history: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        defaults = {
            "flush_at": 128,
            "cache_capacity": 128,
            "slow_line": 100,
            "suggestion_floor": 3,
            "merge_fanout": 4,
        }
        merged = {**defaults, **self.values}
        for name, value in merged.items():
            self._check(name, value)
        self.values = merged

    def _check(self, name: str, value: int) -> None:
        if name not in KNOBS:
            roster = ", ".join(sorted(KNOBS))
            raise Invalid(
                f"no knob named {name}; the roster is {roster}. A "
                f"typoed setting that silently does nothing is worse "
                f"than this error"
            )
        low, high, why = KNOBS[name]
        if not low <= value <= high:
            raise Invalid(
                f"{name}={value} is outside [{low}, {high}] "
                f"({why})"
            )

    def get(self, name: str) -> int:
        if name not in self.values:
            self._check(name, 0)
        return self.values[name]

    def apply(
        self, changes: dict[str, int], who: str, during_incident: bool = False
    ) -> list[str]:
        if not changes:
            raise Invalid("an empty change set changes nothing; say so")
        for name, value in changes.items():
            self._check(name, value)
            if name in FROZEN and during_incident:
                raise Invalid(
                    f"{name} is frozen during incidents; the midnight "
                    f"temptation is exactly what the freeze is for"
                )
        moved = []
        for name, value in sorted(changes.items()):
            before = self.values[name]
            if before == value:
                continue
            self.values[name] = value
            line = f"{name}: {before} -> {value} (by {who})"
            moved.append(line)
            self.history.append(line)
        return moved

    def show(self) -> str:
        lines = []
        for name in sorted(self.values):
            frozen = " [frozen during incidents]" if name in FROZEN else ""
            _, _, why = KNOBS[name]
            lines.append(
                f"{name} = {self.values[name]} ({why}){frozen}"
            )
        return "\n".join(lines)
