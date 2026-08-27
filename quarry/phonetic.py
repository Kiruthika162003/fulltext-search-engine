"""Phonetic coding: names that sound alike file under one key.

Name search fails letter matching constantly, Smith and Smyth,
Jansen and Janssen, and the phonetic code is the fix that has
worked since paper filing: collapse each name to a key of its
first letter plus digits for the consonant classes that
survive saying it aloud, so spellings that sound alike collide
on purpose. The classing follows the classic table, labials
together, gutturals together, vowels dropped after the first
letter, doubled classes collapsed because a held consonant is
one sound, and the key pads or cuts to four characters so the
index of keys stays fixed-width. The honesty clauses: this is
tuned for anglophone name traditions and says so rather than
pretending universality, and lookup returns the colliding
names for a human to pick from, never auto-merging records,
because sounding alike is a reason to ask, not a reason to
assume.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid

CLASSES = {
    "b": "1", "f": "1", "p": "1", "v": "1",
    "c": "2", "g": "2", "j": "2", "k": "2",
    "q": "2", "s": "2", "x": "2", "z": "2",
    "d": "3", "t": "3",
    "l": "4",
    "m": "5", "n": "5",
    "r": "6",
}
KEY_WIDTH = 4


def code(name: str) -> str:
    cleaned = "".join(
        char for char in name.lower() if char.isalpha()
    )
    if not cleaned:
        raise Invalid(
            f"{name!r} holds no letters; silence has no sound"
        )
    first = cleaned[0].upper()
    digits = []
    previous = CLASSES.get(cleaned[0], "")
    for char in cleaned[1:]:
        digit = CLASSES.get(char, "")
        if digit and digit != previous:
            digits.append(digit)
        previous = digit
    key = (first + "".join(digits))[:KEY_WIDTH]
    return key.ljust(KEY_WIDTH, "0")


def sound_alike(left: str, right: str) -> bool:
    return code(left) == code(right)


@dataclass
class PhoneticIndex:
    by_key: dict[str, list[str]] = field(default_factory=dict)

    def admit(self, name: str) -> str:
        key = code(name)
        held = self.by_key.setdefault(key, [])
        if name not in held:
            held.append(name)
        return key

    def candidates(self, name: str) -> list[str]:
        """Colliding names for a human to pick from, never a merge."""
        key = code(name)
        return sorted(
            held
            for held in self.by_key.get(key, [])
            if held != name
        )

    def collision_report(self) -> str:
        crowded = {
            key: names
            for key, names in self.by_key.items()
            if len(names) > 1
        }
        if not crowded:
            return (
                "no collisions; either a small index or a "
                "suspiciously careful one"
            )
        lines = []
        for key in sorted(crowded):
            listed = ", ".join(sorted(crowded[key]))
            lines.append(f"{key}: {listed}")
        lines.append(
            f"{len(crowded)} crowded key(s); tuned for anglophone "
            f"name traditions, stated rather than pretended away"
        )
        return "\n".join(lines)
