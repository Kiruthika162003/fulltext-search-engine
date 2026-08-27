"""Notification routing: the right noise, the right channel, asleep.

Alert content is solved elsewhere; this is delivery discipline.
Severities map to channels declaratively, page wakes a human,
chat interrupts a working one, digest waits for morning, and
the map is data so the review can read who gets woken for what
without reading code. Quiet hours demote chat to digest but
never demote a page, because the whole point of a page is that
sleep does not excuse it, and the demotion is recorded on the
message so morning readers know it arrived quietly on purpose.
Per-channel flood caps hold the pathology of alarm storms: past
the cap, further messages fold into one summary line with a
count, since forty messages in a channel carry less
information than the sentence forty messages arrived. Unknown
severities refuse at the door; inventing a severity mid-outage
is how messages route to nowhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid

ROUTES = {
    "critical": "page",
    "warning": "chat",
    "info": "digest",
}
FLOOD_CAP = 5


@dataclass(frozen=True)
class Delivery:
    channel: str
    text: str
    note: str

    def line(self) -> str:
        suffix = f" [{self.note}]" if self.note else ""
        return f"{self.channel}: {self.text}{suffix}"


@dataclass
class Notifier:
    quiet: bool = False
    delivered: dict[str, list[Delivery]] = field(
        default_factory=dict
    )
    folded: dict[str, int] = field(default_factory=dict)

    def send(self, severity: str, text: str) -> str:
        channel = ROUTES.get(severity)
        if channel is None:
            raise Invalid(
                f"{severity!r} is not a severity; inventing one "
                f"mid-outage routes the message to nowhere. The "
                f"scale is {', '.join(ROUTES)}"
            )
        if not text.strip():
            raise Invalid("an empty notification notifies nothing")
        note = ""
        if self.quiet and channel == "chat":
            channel = "digest"
            note = "demoted by quiet hours, on purpose"
        held = self.delivered.setdefault(channel, [])
        if channel != "page" and len(held) >= FLOOD_CAP:
            self.folded[channel] = self.folded.get(channel, 0) + 1
            return (
                f"{channel} is past its flood cap; folded into "
                f"the summary line"
            )
        held.append(
            Delivery(channel=channel, text=text, note=note)
        )
        return f"delivered to {channel}"

    def channel_page(self, channel: str) -> str:
        held = self.delivered.get(channel, [])
        folded = self.folded.get(channel, 0)
        if not held and not folded:
            return f"{channel}: quiet"
        lines = [delivery.line() for delivery in held]
        if folded:
            lines.append(
                f"{channel}: and {folded} more message(s) folded; "
                f"forty messages carry less information than this "
                f"sentence"
            )
        return "\n".join(lines)

    def wake_audit(self) -> str:
        pages = self.delivered.get("page", [])
        if not pages:
            return "nobody was woken"
        return (
            f"{len(pages)} page(s) woke a human; every one "
            f"should survive the morning review"
        )
