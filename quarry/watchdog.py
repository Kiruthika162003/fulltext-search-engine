"""The watchdog: components prove liveness, silence is an alarm.

Dead components rarely announce themselves; they just stop
talking, and a monitoring system that waits for error reports
waits forever. The watchdog inverts the burden: every component
checks in on a heartbeat cadence it declared for itself, missing
one beat is noted because networks hiccup, missing the declared
tolerance in a row raises the alarm with the silence measured
in beats, and a component that returns after an alarm is
welcomed back with its outage length recorded rather than
silently marked green, because the gap in the record is the
evidence the postmortem needs. Cadences are per component
since an indexer beating every minute and a nightly merge
beating daily are both healthy, and the watchdog refuses
identical duplicate registrations, the classic bug where two
copies of a service each answer half the beats and the
watchdog sees a healthy whole.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid, Missing

MISSED_TOLERANCE = 3


@dataclass
class Watch:
    component: str
    cadence_ticks: int
    last_beat: int
    missed_alarmed: bool = False
    outages: list[str] = field(default_factory=list)

    def beats_missed(self, now: int) -> int:
        return max(0, (now - self.last_beat) // self.cadence_ticks)


@dataclass
class Watchdog:
    watches: dict[str, Watch] = field(default_factory=dict)

    def register(
        self, component: str, cadence_ticks: int, now: int
    ) -> str:
        if cadence_ticks <= 0:
            raise Invalid(
                f"{component}: a cadence of {cadence_ticks} beats "
                f"never; declare how often health speaks"
            )
        if component in self.watches:
            raise Invalid(
                f"{component} is already registered; two copies "
                f"answering half the beats each would look like "
                f"one healthy whole"
            )
        self.watches[component] = Watch(
            component=component,
            cadence_ticks=cadence_ticks,
            last_beat=now,
        )
        return (
            f"{component} watched at every {cadence_ticks} tick(s)"
        )

    def beat(self, component: str, now: int) -> str:
        watch = self.watches.get(component)
        if watch is None:
            raise Missing(
                f"{component} never registered; a heartbeat from a "
                f"stranger is its own alarm"
            )
        if watch.missed_alarmed:
            silent_beats = watch.beats_missed(now)
            watch.outages.append(
                f"returned at tick {now} after "
                f"{silent_beats} silent beat(s)"
            )
            watch.missed_alarmed = False
            watch.last_beat = now
            return (
                f"{component} is back; the outage is on the record"
            )
        watch.last_beat = now
        return f"{component} healthy"

    def patrol(self, now: int) -> list[str]:
        findings = []
        for component in sorted(self.watches):
            watch = self.watches[component]
            missed = watch.beats_missed(now)
            if missed == 0:
                continue
            if missed < MISSED_TOLERANCE:
                findings.append(
                    f"{component}: {missed} beat(s) quiet; "
                    f"networks hiccup, watching"
                )
            elif not watch.missed_alarmed:
                watch.missed_alarmed = True
                findings.append(
                    f"{component}: ALARM, {missed} beats of "
                    f"silence against a tolerance of "
                    f"{MISSED_TOLERANCE}"
                )
            else:
                findings.append(
                    f"{component}: still silent ({missed} beats)"
                )
        return findings

    def record(self, component: str) -> str:
        watch = self.watches.get(component)
        if watch is None:
            raise Missing(f"{component} never registered")
        if not watch.outages:
            return f"{component}: no outages on record"
        lines = [f"{component}:"]
        lines.extend(f"  {outage}" for outage in watch.outages)
        return "\n".join(lines)
