"""Metrics: the engine's vital signs, in one registry with units.

Every subsystem already counts things; this registry is where the
counts become legible. Counters only go up, gauges go anywhere,
and every metric declares a unit at registration because a
dashboard mixing milliseconds with microseconds has killed more
oncalls than any outage. The scrape renders in a stable sorted
order so diffs of two scrapes read as changes, not shuffles, and
the delta method answers the only question two scrapes ever get
asked: what moved, by how much, in what unit. Unregistered names
fail loudly at record time rather than creating themselves,
because a typo that mints a fresh metric splits the graph into
two lines nobody notices until the incident review.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid, Missing


@dataclass
class Metric:
    name: str
    kind: str
    unit: str
    value: float = 0.0


@dataclass
class Registry:
    metrics: dict[str, Metric] = field(default_factory=dict)

    def counter(self, name: str, unit: str) -> None:
        self._register(name, "counter", unit)

    def gauge(self, name: str, unit: str) -> None:
        self._register(name, "gauge", unit)

    def _register(self, name: str, kind: str, unit: str) -> None:
        if not name or not unit:
            raise Invalid("metrics need a name and a unit; no exceptions")
        if name in self.metrics:
            raise Invalid(f"{name} is already registered")
        self.metrics[name] = Metric(name=name, kind=kind, unit=unit)

    def increment(self, name: str, by: float = 1.0) -> None:
        held = self._get(name)
        if held.kind != "counter":
            raise Invalid(f"{name} is a {held.kind}; increment counters")
        if by < 0:
            raise Invalid(
                f"{name}: counters only go up; a decrement is a gauge "
                f"wearing the wrong hat"
            )
        held.value += by

    def set_gauge(self, name: str, to: float) -> None:
        held = self._get(name)
        if held.kind != "gauge":
            raise Invalid(f"{name} is a {held.kind}; set gauges")
        held.value = to

    def _get(self, name: str) -> Metric:
        if name not in self.metrics:
            raise Missing(
                f"no metric named {name}; a typo that mints a fresh "
                f"metric splits the graph"
            )
        return self.metrics[name]

    def read(self, name: str) -> float:
        return self._get(name).value

    def scrape(self) -> str:
        lines = []
        for name in sorted(self.metrics):
            held = self.metrics[name]
            lines.append(
                f"{held.name} {held.value} {held.unit} ({held.kind})"
            )
        return "\n".join(lines)

    def delta(self, before: dict[str, float]) -> list[str]:
        """What moved since the snapshot, by how much, in what unit."""
        moved = []
        for name in sorted(self.metrics):
            held = self.metrics[name]
            previous = before.get(name)
            if previous is None:
                moved.append(f"{name}: new since the snapshot")
                continue
            if held.value != previous:
                moved.append(
                    f"{name}: {previous} -> {held.value} "
                    f"({held.value - previous:+g} {held.unit})"
                )
        return moved

    def snapshot(self) -> dict[str, float]:
        return {
            name: held.value for name, held in self.metrics.items()
        }


def engine_registry() -> Registry:
    """The standard roster every quarry deployment starts with."""
    registry = Registry()
    registry.counter("queries_served", unit="queries")
    registry.counter("documents_indexed", unit="documents")
    registry.counter("flushes", unit="flushes")
    registry.counter("merges", unit="merges")
    registry.counter("cache_hits", unit="lookups")
    registry.counter("cache_misses", unit="lookups")
    registry.gauge("segments_live", unit="segments")
    registry.gauge("searchable_documents", unit="documents")
    registry.gauge("tombstone_share", unit="fraction")
    return registry
