"""Log privacy: the query log must not become the data breach.

People type their own names, emails, and phone numbers into search
boxes, which turns every retained query log into personal data
with a retention clock. Scrubbing runs at write time, never as a
later batch job, because the unscrubbed window between ingest and
cleanup is exactly the window subpoenas and breaches arrive in.
The patterns are deliberately narrow, emails, phone-shaped digit
runs, and card-shaped digit runs, each replaced by a typed marker
that preserves the shape of the query for analysis: the analyst
can still count how many people search their own email without
being able to read one. Detection counts ride along per scrub so
drift is visible, and the marker vocabulary is closed, because a
scrubber that invents new markers per run breaks every dashboard
that grouped on the old ones.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from quarry.errors import Invalid

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE = re.compile(r"(?<!\d)(?:\+?\d[\s-]?){7,14}\d(?!\d)")
CARD = re.compile(r"(?<!\d)\d(?:[ -]?\d){12,18}(?!\d)")

MARKERS = {
    "email": "[email]",
    "phone": "[phone]",
    "card": "[card]",
}


@dataclass(frozen=True)
class Scrubbed:
    text: str
    emails: int
    phones: int
    cards: int

    def touched(self) -> bool:
        return bool(self.emails or self.phones or self.cards)


def scrub(text: str) -> Scrubbed:
    if not text:
        raise Invalid("scrubbing nothing hides nothing")
    cards = len(CARD.findall(text))
    text = CARD.sub(MARKERS["card"], text)
    emails = len(EMAIL.findall(text))
    text = EMAIL.sub(MARKERS["email"], text)
    phones = len(PHONE.findall(text))
    text = PHONE.sub(MARKERS["phone"], text)
    return Scrubbed(
        text=text, emails=emails, phones=phones, cards=cards
    )


@dataclass
class ScrubbingLog:
    """A query log that never held what it must not hold."""

    rows: list[str] = field(default_factory=list)
    scrubbed_rows: int = 0
    markers_written: dict[str, int] = field(
        default_factory=lambda: {"email": 0, "phone": 0, "card": 0}
    )

    def log(self, text: str) -> Scrubbed:
        cleaned = scrub(text)
        self.rows.append(cleaned.text)
        if cleaned.touched():
            self.scrubbed_rows += 1
        self.markers_written["email"] += cleaned.emails
        self.markers_written["phone"] += cleaned.phones
        self.markers_written["card"] += cleaned.cards
        return cleaned

    def drift_report(self) -> str:
        total = len(self.rows)
        if total == 0:
            raise Invalid("no rows logged; drift over nothing")
        share = self.scrubbed_rows / total
        counts = ", ".join(
            f"{kind}: {count}"
            for kind, count in sorted(self.markers_written.items())
        )
        return (
            f"{total} rows, {share:.1%} carried personal data "
            f"({counts})"
        )

    def contains_raw_email(self) -> bool:
        """The audit the scrubber must always pass."""
        return any(EMAIL.search(row) for row in self.rows)
