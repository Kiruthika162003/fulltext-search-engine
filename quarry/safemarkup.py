"""Safe result markup: stored text can never become running code.

Search results render into pages, and a document whose title
contains a script tag will execute in every browser that ever
lists it unless the boundary is absolute: stored text is text,
and the only markup in a rendered result is markup this module
wrote. Escaping happens last, after highlighting decides where
the emphasis goes, because escaping first and wrapping later
reopens the hole through the wrapper, and the emphasis markers
are inserted by offset into the escaped string through a
placeholder scheme that cannot collide with document content.
The audit function exists for the renderer's tests: it walks a
rendered fragment and verifies every tag present is one of the
two this module emits, so a template regression that lets raw
text through fails a unit test instead of a disclosure
deadline.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass

from quarry.errors import Invalid

ALLOWED_TAGS = ("<em>", "</em>")
TAG_PATTERN = re.compile(r"<[^>]*>")


def escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


@dataclass(frozen=True)
class Emphasis:
    start: int
    end: int

    def __post_init__(self) -> None:
        if not 0 <= self.start < self.end:
            raise Invalid(
                f"emphasis [{self.start}, {self.end}) is not a "
                f"forward span"
            )


def render_snippet(text: str, marks: list[Emphasis]) -> str:
    for mark in marks:
        if mark.end > len(text):
            raise Invalid(
                f"emphasis ends at {mark.end} but the text holds "
                f"{len(text)} characters"
            )
    ordered = sorted(marks, key=lambda held: held.start)
    for left, right in itertools.pairwise(ordered):
        if right.start < left.end:
            raise Invalid(
                "emphasis spans overlap; two highlights on one "
                "character means the offsets are wrong"
            )
    pieces: list[str] = []
    cursor = 0
    for mark in ordered:
        pieces.append(escape(text[cursor : mark.start]))
        pieces.append("<em>")
        pieces.append(escape(text[mark.start : mark.end]))
        pieces.append("</em>")
        cursor = mark.end
    pieces.append(escape(text[cursor:]))
    return "".join(pieces)


def audit(rendered: str) -> str:
    strays = [
        tag
        for tag in TAG_PATTERN.findall(rendered)
        if tag not in ALLOWED_TAGS
    ]
    if strays:
        listed = ", ".join(sorted(set(strays)))
        raise Invalid(
            f"rendered fragment carries tag(s) this module never "
            f"wrote: {listed}; stored text is leaking through as "
            f"markup"
        )
    opens = rendered.count("<em>")
    closes = rendered.count("</em>")
    if opens != closes:
        raise Invalid(
            f"{opens} <em> against {closes} </em>; the emphasis "
            f"does not close"
        )
    return f"clean: {opens} emphasis span(s), nothing else"
