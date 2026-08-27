"""Date fields: strings become epoch days once, at the door, or never.

Dates arrive as strings in whatever shape the exporter fancied,
and the two crimes are parsing them lazily at query time, which
makes every search pay the parse and every malformed date a
delayed surprise, and guessing ambiguous forms, which files a
March 4th under April 3rd for customers on the wrong side of an
ocean. Parsing happens at the door with an explicit format list
tried in order, the winner recorded per parse so drift in feed
formats is visible in the tally, and the ambiguous numeric form
is refused outright when both readings are plausible, because
04/03 has two honest meanings and choosing one silently is how
birthdays move. Storage is epoch days, an integer that sorts,
ranges, and buckets with the machinery numerics already have,
which is the entire point of parsing at the door.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from quarry.errors import Invalid

EPOCH = date(1970, 1, 1)


def to_epoch_days(year: int, month: int, day: int) -> int:
    try:
        return (date(year, month, day) - EPOCH).days
    except ValueError as impossible:
        raise Invalid(
            f"{year}-{month:02d}-{day:02d} is not a date: {impossible}"
        ) from impossible


def from_epoch_days(days: int) -> str:
    return date.fromordinal(EPOCH.toordinal() + days).isoformat()


@dataclass
class DateParser:
    tally: dict[str, int] = field(default_factory=dict)

    def parse(self, text: str) -> int:
        cleaned = text.strip()
        if not cleaned:
            raise Invalid("an empty date is not a date")
        for name, days in (
            ("iso", self._iso(cleaned)),
            ("compact", self._compact(cleaned)),
            ("slashed", self._slashed(cleaned)),
        ):
            if days is not None:
                self.tally[name] = self.tally.get(name, 0) + 1
                return days
        raise Invalid(
            f"{text!r} matched no known date shape; the formats tried "
            f"were iso (2024-03-04), compact (20240304), and slashed "
            f"(2024/03/04)"
        )

    def _iso(self, text: str) -> int | None:
        parts = text.split("-")
        if len(parts) != 3 or not all(part.isdigit() for part in parts):
            return None
        year, month, day = (int(part) for part in parts)
        if len(parts[0]) != 4:
            return None
        return to_epoch_days(year, month, day)

    def _compact(self, text: str) -> int | None:
        if len(text) != 8 or not text.isdigit():
            return None
        return to_epoch_days(
            int(text[:4]), int(text[4:6]), int(text[6:8])
        )

    def _slashed(self, text: str) -> int | None:
        parts = text.split("/")
        if len(parts) != 3 or not all(part.isdigit() for part in parts):
            return None
        if len(parts[0]) == 4:
            year, first, second = (int(part) for part in parts)
            return to_epoch_days(year, first, second)
        first, second, year = (int(part) for part in parts)
        if len(parts[2]) != 4:
            return None
        if first <= 12 and second <= 12 and first != second:
            raise Invalid(
                f"{text!r} is ambiguous: both {first}/{second} and "
                f"{second}/{first} are plausible, and choosing one "
                f"silently is how birthdays move. Use the iso form"
            )
        if first > 12:
            return to_epoch_days(year, second, first)
        return to_epoch_days(year, first, second)

    def drift_tally(self) -> str:
        if not self.tally:
            return "no dates parsed yet"
        rows = ", ".join(
            f"{name}: {count}"
            for name, count in sorted(self.tally.items())
        )
        return f"formats seen: {rows}"
