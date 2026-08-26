"""Fuzzy matching: a typo is a small edit, and candidates come cheap.

Comparing the query against every vocabulary term is quadratic
regret, so lookup runs in two stages. The n-gram stage is a coarse
net: terms sharing few character grams with the query cannot be
close, so the index over grams returns a shortlist plus a count of
how much of the vocabulary it skipped, keeping the shortcut honest.
The edit-distance stage is exact, a banded dynamic program that
stops the moment a row's minimum exceeds the cap, because a term
already two edits away cannot come back under one. Suggestions
rank by distance first and term popularity second, since the user
who typed "catz" almost always meant the common "cats" and not the
rare "catz" that happens to live in one document.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid
from quarry.tokenize import ngrams

GRAM_WIDTH = 3
DEFAULT_CAP = 2


def edit_distance(left: str, right: str, cap: int = DEFAULT_CAP) -> int:
    """Banded Levenshtein: exact up to the cap, cap+1 past it."""
    if cap < 0:
        raise Invalid("a negative edit cap asks for nothing")
    if abs(len(left) - len(right)) > cap:
        return cap + 1
    previous = list(range(len(right) + 1))
    for row, left_char in enumerate(left, start=1):
        current = [row]
        low = cap + 1
        for column, right_char in enumerate(right, start=1):
            cost = 0 if left_char == right_char else 1
            value = min(
                previous[column] + 1,
                current[column - 1] + 1,
                previous[column - 1] + cost,
            )
            current.append(value)
            low = min(low, value)
        if low > cap:
            return cap + 1
        previous = current
    return min(previous[-1], cap + 1)


@dataclass
class FuzzyIndex:
    gram_width: int = GRAM_WIDTH
    by_gram: dict[str, set[str]] = field(default_factory=dict)
    popularity: dict[str, int] = field(default_factory=dict)

    def admit(self, term: str, weight: int = 1) -> None:
        if not term:
            raise Invalid("an empty term cannot be found, fuzzily or not")
        if term not in self.popularity:
            for gram in ngrams(term, self.gram_width):
                self.by_gram.setdefault(gram, set()).add(term)
        self.popularity[term] = self.popularity.get(term, 0) + weight

    def vocabulary_size(self) -> int:
        return len(self.popularity)

    def shortlist(self, query: str) -> tuple[list[str], int]:
        """Terms sharing at least one gram, and how many were skipped."""
        found: set[str] = set()
        for gram in ngrams(query, self.gram_width):
            found |= self.by_gram.get(gram, set())
        return sorted(found), self.vocabulary_size() - len(found)


@dataclass(frozen=True)
class Suggestion:
    term: str
    distance: int
    popularity: int


def suggest(
    index: FuzzyIndex, query: str, cap: int = DEFAULT_CAP, limit: int = 3
) -> list[Suggestion]:
    if limit <= 0:
        raise Invalid("asking for zero suggestions should not run")
    shortlist, _ = index.shortlist(query)
    scored = []
    for term in shortlist:
        distance = edit_distance(query, term, cap=cap)
        if distance > cap:
            continue
        scored.append(
            Suggestion(
                term=term,
                distance=distance,
                popularity=index.popularity[term],
            )
        )
    scored.sort(
        key=lambda held: (held.distance, -held.popularity, held.term)
    )
    return scored[:limit]


def did_you_mean(
    index: FuzzyIndex, query: str, cap: int = DEFAULT_CAP
) -> str | None:
    """The one-line correction, offered only when it beats the query.

    An exact vocabulary hit suggests nothing, because correcting a
    word the corpus contains insults the user who typed it on
    purpose. Otherwise the best suggestion wins only if it exists.
    """
    if query in index.popularity:
        return None
    best = suggest(index, query, cap=cap, limit=1)
    return best[0].term if best else None
