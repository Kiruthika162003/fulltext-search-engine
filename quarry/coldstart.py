"""Cold start policy: the empty index answers honestly, not blankly.

Every search deployment is empty on day one and thin for a
month, and features tuned for a full corpus misbehave in the
cold: suggestions trained on three documents suggest garbage
confidently, trending over ten queries crowns every typo, and
relevance evals graded on five documents grade noise. The
policy declares readiness floors per feature, documents or
queries required before the feature speaks, and the gate
answers three ways with the arithmetic shown: ready, warming
with the shortfall counted, and silent for features whose cold
output is actively harmful, where the honest response is
nothing rather than a hedge. The warming report lists every
feature with its floor and its progress so day-one operators
watch capabilities arrive instead of filing bugs about
features that were never on, and floors only come from this
table, never per-call overrides, because a floor negotiable at
the call site is a floor already gone.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid, Missing

FLOORS = {
    "search": 1,
    "snippets": 1,
    "suggestions": 50,
    "trending": 500,
    "relevance-evals": 200,
    "click-model": 1000,
}

SILENT_WHEN_COLD = frozenset({"suggestions", "trending"})


@dataclass(frozen=True)
class FeatureState:
    feature: str
    have: int
    floor: int

    def ready(self) -> bool:
        return self.have >= self.floor

    def line(self) -> str:
        if self.ready():
            return f"{self.feature}: ready ({self.have}/{self.floor})"
        state = (
            "silent"
            if self.feature in SILENT_WHEN_COLD
            else "warming"
        )
        return (
            f"{self.feature}: {state}, {self.floor - self.have} "
            f"more needed ({self.have}/{self.floor})"
        )


def gate(feature: str, have: int) -> FeatureState:
    floor = FLOORS.get(feature)
    if floor is None:
        raise Missing(
            f"{feature!r} has no readiness floor; every feature "
            f"declares one before it ships"
        )
    if have < 0:
        raise Invalid("a negative count is a counting bug")
    return FeatureState(feature=feature, have=have, floor=floor)


def may_speak(feature: str, have: int) -> tuple[bool, str]:
    state = gate(feature, have)
    if state.ready():
        return True, f"{feature} speaks: past its floor"
    if feature in SILENT_WHEN_COLD:
        return False, (
            f"{feature} stays SILENT: cold output here is "
            f"actively harmful, and nothing beats a hedge"
        )
    return False, (
        f"{feature} warms: degraded output allowed, labeled, "
        f"{state.floor - have} short of the floor"
    )


def warming_report(counts: dict[str, int]) -> str:
    strays = sorted(set(counts) - set(FLOORS))
    if strays:
        raise Invalid(
            f"count(s) for unknown feature(s) "
            f"{', '.join(strays)}; the floor table is the roster"
        )
    lines = []
    ready = 0
    for feature in sorted(FLOORS):
        have = counts.get(feature, 0)
        state = gate(feature, have)
        if state.ready():
            ready += 1
        lines.append(state.line())
    lines.append(
        f"{ready} of {len(FLOORS)} features ready; the rest are "
        f"arriving, not broken"
    )
    return "\n".join(lines)
