"""Compound splitting: a long word searched by its halves, carefully.

Catalogs are full of welded words, bookshelf and steamship and
motorway, and a user searching shelf deserves the bookshelf row.
The splitter breaks a word into parts only when every part is a
known vocabulary word of respectable length, because splitting
against an open dictionary turns carpet into car and pet and
floods the index with noise. Splits are found by walking every
cut position with backtracking, the split with the fewest parts
wins because two honest halves beat four fragments, and a word
that resists splitting is kept whole rather than mangled. At
index time the parts are added alongside the whole word, never
instead of it, so exact matches for the compound still rank
above matches assembled from its pieces.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid

MIN_PART = 3


@dataclass(frozen=True)
class Split:
    word: str
    parts: tuple[str, ...]

    def explain(self) -> str:
        if len(self.parts) == 1:
            return f"{self.word}: kept whole, no split survived"
        joined = " + ".join(self.parts)
        return f"{self.word}: split as {joined}"


@dataclass
class CompoundSplitter:
    vocabulary: frozenset[str]

    def __post_init__(self) -> None:
        short = sorted(
            word for word in self.vocabulary if len(word) < MIN_PART
        )
        if short:
            raise Invalid(
                f"vocabulary words shorter than {MIN_PART} letters "
                f"({', '.join(short)}) would shred long words into "
                f"confetti; leave them out"
            )

    def split(self, word: str) -> Split:
        cleaned = word.strip().lower()
        if not cleaned:
            raise Invalid("an empty word has no parts")
        best = self._search(cleaned)
        if best is None or len(best) <= 1:
            return Split(word=cleaned, parts=(cleaned,))
        return Split(word=cleaned, parts=tuple(best))

    def _search(self, word: str) -> list[str] | None:
        """Fewest-parts split where every part is vocabulary."""
        if word in self.vocabulary:
            return [word]
        best: list[str] | None = None
        for cut in range(len(word) - MIN_PART, MIN_PART - 1, -1):
            head = word[:cut]
            if head not in self.vocabulary:
                continue
            tail = self._search(word[cut:])
            if tail is None:
                continue
            candidate = [head, *tail]
            if best is None or len(candidate) < len(best):
                best = candidate
        return best

    def index_terms(self, word: str) -> list[str]:
        """The whole word always, the parts beside it when found."""
        found = self.split(word)
        if len(found.parts) == 1:
            return [found.word]
        return [found.word, *found.parts]

    def expand_query_term(self, term: str) -> list[str]:
        """Query side stays whole: parts were added at index time."""
        return [term.strip().lower()]


def splitter_report(
    splitter: CompoundSplitter, words: list[str]
) -> str:
    lines = []
    split_count = 0
    for word in words:
        found = splitter.split(word)
        if len(found.parts) > 1:
            split_count += 1
        lines.append(found.explain())
    lines.append(
        f"outcome: {split_count} of {len(words)} words split"
    )
    return "\n".join(lines)
