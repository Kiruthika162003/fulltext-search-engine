"""Phrase suggestions: the corpus completes the phrase, not the word.

Word completion answers depa with department, but a searcher who
typed department store wants the next word, and the corpus knows
which words actually follow: a bigram book built at index time
counts every adjacent pair, and suggestions for a phrase are the
words that followed its last word, ranked by how often, ties
broken alphabetically so the order is stable across runs. The
book refuses to suggest continuations seen fewer times than the
floor, because a pair seen once is as likely a typo as an idiom,
and every suggestion carries its count so the caller can draw a
confidence line wherever the product wants it. Suggestions are
built from documents alone, never from other users' queries, so
nothing anyone typed can surface in a stranger's dropdown.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

from quarry.errors import Invalid
from quarry.tokenize import Analyzer

PAIR_FLOOR = 2


@dataclass(frozen=True)
class Continuation:
    word: str
    count: int

    def line(self) -> str:
        return f"{self.word} (seen {self.count}x)"


@dataclass
class BigramBook:
    analyzer: Analyzer = field(default_factory=Analyzer)
    pairs: dict[str, dict[str, int]] = field(default_factory=dict)
    documents_read: int = 0

    def learn(self, text: str) -> int:
        terms = self.analyzer.terms(text)
        added = 0
        for left, right in itertools.pairwise(terms):
            followers = self.pairs.setdefault(left, {})
            followers[right] = followers.get(right, 0) + 1
            added += 1
        self.documents_read += 1
        return added

    def continuations(
        self, phrase: str, limit: int = 5
    ) -> list[Continuation]:
        if limit <= 0:
            raise Invalid("a dropdown with no rows should not open")
        terms = self.analyzer.terms(phrase)
        if not terms:
            raise Invalid(
                "the phrase analyzed to nothing; there is no last "
                "word to continue"
            )
        followers = self.pairs.get(terms[-1], {})
        rows = [
            Continuation(word=word, count=count)
            for word, count in followers.items()
            if count >= PAIR_FLOOR
        ]
        rows.sort(key=lambda held: (-held.count, held.word))
        return rows[:limit]

    def suggest_phrases(
        self, phrase: str, limit: int = 5
    ) -> list[str]:
        cleaned = " ".join(self.analyzer.terms(phrase))
        return [
            f"{cleaned} {held.word}"
            for held in self.continuations(phrase, limit=limit)
        ]

    def coverage(self) -> str:
        pair_count = sum(
            len(followers) for followers in self.pairs.values()
        )
        confident = sum(
            1
            for followers in self.pairs.values()
            for count in followers.values()
            if count >= PAIR_FLOOR
        )
        return (
            f"{self.documents_read} documents read, {pair_count} "
            f"distinct pairs, {confident} at or above the floor "
            f"of {PAIR_FLOOR}"
        )
