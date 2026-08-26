"""Highlighting: show the reader why this document answered.

The offsets saved at tokenization time pay off here: highlighting
re-analyzes the stored text with the field's own analyzer, marks
every token whose term matched the query, and never touches the
original bytes between the marks, so what the reader sees is their
document, not a normalised ghost of it. Snippet selection is a
windowing problem stated honestly: score each window by matches
held, break ties toward the earliest, and widen to word boundaries
so no snippet opens mid-word. When nothing matched in a field the
snippet falls back to the opening of the text, because an empty
highlight box reads as a broken page while the first line reads as
an answer that happened to match elsewhere.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

from quarry.errors import Invalid
from quarry.tokenize import Analyzer

OPEN_MARK = "["
CLOSE_MARK = "]"
SNIPPET_WIDTH = 60


@dataclass(frozen=True)
class Span:
    start: int
    end: int


def matched_spans(
    text: str, analyzer: Analyzer, terms: set[str]
) -> list[Span]:
    return [
        Span(start=token.start, end=token.end)
        for token in analyzer.tokens(text)
        if token.text in terms
    ]


def mark(text: str, spans: list[Span]) -> str:
    if not spans:
        return text
    ordered = sorted(spans, key=lambda span: span.start)
    for before, after in itertools.pairwise(ordered):
        if after.start < before.end:
            raise Invalid("overlapping spans cannot be marked sanely")
    pieces: list[str] = []
    cursor = 0
    for span in ordered:
        pieces.append(text[cursor : span.start])
        pieces.append(OPEN_MARK)
        pieces.append(text[span.start : span.end])
        pieces.append(CLOSE_MARK)
        cursor = span.end
    pieces.append(text[cursor:])
    return "".join(pieces)


def _widen_to_words(text: str, start: int, end: int) -> tuple[int, int]:
    while start > 0 and text[start - 1].isalnum():
        start -= 1
    while end < len(text) and text[end].isalnum():
        end += 1
    return start, end


def best_window(
    text: str, spans: list[Span], width: int = SNIPPET_WIDTH
) -> tuple[int, int]:
    if width <= 0:
        raise Invalid("a snippet needs width")
    if not spans:
        return _widen_to_words(text, 0, min(width, len(text)))
    ordered = sorted(spans, key=lambda span: span.start)
    best_start = ordered[0].start
    best_held = -1
    for anchor in ordered:
        window_end = anchor.start + width
        held = sum(
            1 for span in ordered if anchor.start <= span.start and span.end <= window_end
        )
        if held > best_held:
            best_held = held
            best_start = anchor.start
    start = max(0, min(best_start, len(text) - width))
    end = min(len(text), start + width)
    return _widen_to_words(text, start, end)


def snippet(
    text: str,
    analyzer: Analyzer,
    terms: set[str],
    width: int = SNIPPET_WIDTH,
) -> str:
    spans = matched_spans(text, analyzer, terms)
    start, end = best_window(text, spans, width)
    inside = [
        Span(start=span.start - start, end=span.end - start)
        for span in spans
        if start <= span.start and span.end <= end
    ]
    body = mark(text[start:end], inside)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{body}{suffix}"
