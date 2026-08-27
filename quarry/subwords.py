"""Subword splitting: code identifiers are phrases wearing no spaces.

Searching a codebase or a product catalogue meets getUserName,
snake_case_config, and HTTPResponse2, and a tokenizer that treats
each as one opaque term makes them findable only by people who
already know the exact spelling. The splitter breaks on case
boundaries, separators, and letter-digit seams, keeps the original
whole token beside the parts so exact spellings still match best,
and handles the acronym run correctly: HTTPResponse splits to HTTP
and Response, not H-T-T-P-R, because the boundary is the last
capital before a lowercase, the rule every human applies without
noticing. Splitting is a declared analyzer choice like every
other, and the parts inherit one position each so phrase queries
over split identifiers behave like phrases over words.
"""

from __future__ import annotations

from quarry.errors import Invalid

SEPARATORS = set("_-./:")


def split_identifier(token: str) -> list[str]:
    if not token:
        raise Invalid("an empty identifier splits into philosophy")
    pieces: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            pieces.append("".join(current))
            current.clear()

    previous = ""
    for index, char in enumerate(token):
        if char in SEPARATORS:
            flush()
            previous = char
            continue
        if current:
            case_seam = (
                char.isupper()
                and previous.islower()
            )
            acronym_end = (
                char.islower()
                and previous.isupper()
                and len(current) > 1
            )
            digit_seam = (
                char.isdigit() != previous.isdigit()
                and previous not in SEPARATORS
            )
            if case_seam or digit_seam:
                flush()
            elif acronym_end:
                last = current.pop()
                flush()
                current.append(last)
        current.append(char)
        previous = char
        del index
    flush()
    return [piece for piece in pieces if piece]


def expand_token(token: str) -> list[str]:
    """The whole token first, then its parts, lowered, deduplicated."""
    parts = split_identifier(token)
    out: list[str] = []
    seen: set[str] = set()
    for candidate in [token, *parts]:
        lowered = candidate.lower()
        if lowered not in seen:
            seen.add(lowered)
            out.append(lowered)
    return out


def split_report(identifiers: list[str]) -> str:
    if not identifiers:
        raise Invalid("a report over nothing reports nothing")
    lines = []
    for identifier in identifiers:
        parts = split_identifier(identifier)
        joined = " + ".join(parts)
        lines.append(f"{identifier} -> {joined}")
    return "\n".join(lines)
