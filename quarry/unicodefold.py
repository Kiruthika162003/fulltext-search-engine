"""Accent folding: cafe and café are the same word to a searcher.

Users type without accents on the wrong keyboard, paste text with
them from the right one, and expect both to find the same
documents. Folding strips combining marks after Unicode
decomposition, so café becomes cafe and naïve becomes naive, with
the ligature table handling the characters decomposition cannot,
æ to ae and ß to ss. The rule about where folding happens is the
same one-pipeline rule the analyzer already enforces: fold on both
sides or neither, because an index that folded meeting a query
that did not is the unfindable-document bug wearing a beret. The
fold is declared in the analyzer identity like every other choice,
and the deliberate limit is stated: this folds marks, it does not
transliterate scripts, and Cyrillic stays Cyrillic because
pretending otherwise is how search engines embarrass themselves
in languages their authors do not read.
"""

from __future__ import annotations

import unicodedata

from quarry.errors import Invalid

LIGATURES = {
    "æ": "ae",
    "Æ": "AE",
    "œ": "oe",
    "Œ": "OE",
    "ß": "ss",
    "ø": "o",
    "Ø": "O",
    "đ": "d",
    "Đ": "D",
    "ł": "l",
    "Ł": "L",
}


def fold(text: str) -> str:
    expanded = "".join(LIGATURES.get(char, char) for char in text)
    decomposed = unicodedata.normalize("NFD", expanded)
    stripped = "".join(
        char
        for char in decomposed
        if not unicodedata.combining(char)
    )
    return unicodedata.normalize("NFC", stripped)


def folds_to_same(left: str, right: str) -> bool:
    if not left or not right:
        raise Invalid("comparing emptiness folds nothing")
    return fold(left).lower() == fold(right).lower()


def folding_report(terms: list[str]) -> str:
    """Which distinct spellings collapse together under the fold."""
    if not terms:
        raise Invalid("a report over no terms reports nothing")
    families: dict[str, list[str]] = {}
    for term in terms:
        families.setdefault(fold(term).lower(), []).append(term)
    collapsed = {
        folded: sorted(set(spellings))
        for folded, spellings in families.items()
        if len(set(spellings)) > 1
    }
    if not collapsed:
        return "no spellings collapse; the fold changes nothing here"
    lines = [f"{len(collapsed)} famil(ies) collapse under folding:"]
    for folded in sorted(collapsed):
        joined = ", ".join(collapsed[folded])
        lines.append(f"  {folded}: {joined}")
    return "\n".join(lines)
