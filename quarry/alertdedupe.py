"""Alert deduplication: one incident, one page, however many signals.

A single hot shard fires the latency alert, the queue-depth
alert, and the error-rate alert, and three pages for one
problem teach responders to silence pages. The deduper groups
alerts into incidents by their declared cause key, only the
first alert of an incident pages while the rest attach as
evidence, and flapping, the alert that clears and refires
inside the cool-down, reuses its incident rather than opening
a fresh one, because a flapping alert is one problem with a
nervous signal, not many problems. Suppression is bounded: an
incident that keeps accumulating evidence past the escalation
count re-pages at a higher urgency, since the difference
between deduplicated and ignored is exactly that bound, and
closing an incident writes how many signals it absorbed so the
noisiest causes can be found and fixed at the source.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid, Missing

COOLDOWN_TICKS = 30
ESCALATE_AT = 5


@dataclass
class Incident:
    cause_key: str
    opened_at: int
    evidence: list[str] = field(default_factory=list)
    closed_at: int | None = None
    escalated: bool = False

    def open_now(self) -> bool:
        return self.closed_at is None

    def absorbed(self) -> int:
        return len(self.evidence)


@dataclass
class AlertDeduper:
    incidents: dict[str, Incident] = field(default_factory=dict)
    pages_sent: list[str] = field(default_factory=list)
    closed: list[Incident] = field(default_factory=list)

    def signal(
        self, cause_key: str, description: str, tick: int
    ) -> str:
        if not cause_key.strip():
            raise Invalid(
                "an alert without a cause key cannot be grouped; "
                "declare what it is about"
            )
        held = self.incidents.get(cause_key)
        if held is not None and not held.open_now():
            if tick - held.closed_at <= COOLDOWN_TICKS:
                held.closed_at = None
                held.evidence.append(
                    f"[{tick}] refired inside cooldown: {description}"
                )
                return (
                    f"{cause_key}: flapped back open; same "
                    f"incident, no new page"
                )
            self.closed.append(held)
            held = None
        if held is None:
            fresh = Incident(cause_key=cause_key, opened_at=tick)
            fresh.evidence.append(f"[{tick}] {description}")
            self.incidents[cause_key] = fresh
            self.pages_sent.append(
                f"PAGE {cause_key} at {tick}: {description}"
            )
            return f"{cause_key}: incident opened, page sent"
        held.evidence.append(f"[{tick}] {description}")
        if (
            held.absorbed() >= ESCALATE_AT
            and not held.escalated
        ):
            held.escalated = True
            self.pages_sent.append(
                f"ESCALATE {cause_key} at {tick}: "
                f"{held.absorbed()} signals and climbing"
            )
            return (
                f"{cause_key}: evidence past {ESCALATE_AT}, "
                f"re-paged at higher urgency"
            )
        return (
            f"{cause_key}: attached as evidence "
            f"({held.absorbed()} total)"
        )

    def clear(self, cause_key: str, tick: int) -> str:
        held = self.incidents.get(cause_key)
        if held is None or not held.open_now():
            raise Missing(
                f"no open incident for {cause_key}; clearing what "
                f"is not open usually means the wrong key"
            )
        held.closed_at = tick
        return (
            f"{cause_key} closed at {tick} having absorbed "
            f"{held.absorbed()} signal(s)"
        )

    def noisiest(self) -> str:
        finished = self.closed + [
            held
            for held in self.incidents.values()
            if not held.open_now()
        ]
        if not finished:
            return "no closed incidents yet"
        finished.sort(
            key=lambda held: (-held.absorbed(), held.cause_key)
        )
        top = finished[0]
        return (
            f"noisiest cause: {top.cause_key} with "
            f"{top.absorbed()} signal(s); fix it at the source"
        )
