"""Tokenization: the index can only find what the analyzer kept.

Every search miss traces back to one of two analyzers disagreeing:
the one that indexed the document and the one that read the query.
The pipeline here is therefore one function used on both sides,
deterministic and inspectable: lowercase fold, split on anything
that is not a letter or digit, drop stopwords, and apply a light
suffix stemmer, with every stage optional but the same choices
frozen into the schema so a field cannot be indexed one way and
queried another. Positions are assigned after dropping, not
before, so a phrase query over "the black cat" matches "black cat"
with the stopword gone from both sides of the equation, and the
token stream carries each token's source offsets because
highlighting is a promise made at tokenization time.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid

STOPWORDS = frozenset(
    ["a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "he", "in", "is", "it", "its", "of", "on", "or", "that", "the", "to", "was", "were", "will", "with"]
)

SUFFIXES = ("ingly", "edly", "ing", "ies", "ed", "es", "s", "ly")
STEM_FLOOR = 3


@dataclass(frozen=True)
class Token:
    text: str
    position: int
    start: int
    end: int


def stem(word: str) -> str:
    """A light suffix strip, honest about being one.

    This is deliberately not Porter: it never rewrites a stem, only
    removes one suffix when what remains is long enough to stand.
    The trade is stated so nobody mistakes it: "running" becomes
    "runn", not "run", and both sides of the index make the same
    mistake, which is what actually matters for matching.
    """
    for suffix in SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= STEM_FLOOR:
            return word[: -len(suffix)]
    return word


@dataclass(frozen=True)
class Analyzer:
    lowercase: bool = True
    drop_stopwords: bool = True
    stemming: bool = True

    def tokens(self, text: str) -> list[Token]:
        raw: list[tuple[str, int, int]] = []
        start = None
        for index, char in enumerate(text):
            if char.isalnum():
                if start is None:
                    start = index
            elif start is not None:
                raw.append((text[start:index], start, index))
                start = None
        if start is not None:
            raw.append((text[start:], start, len(text)))
        kept: list[Token] = []
        position = 0
        for word, begin, end in raw:
            shaped = word.lower() if self.lowercase else word
            if self.drop_stopwords and shaped in STOPWORDS:
                continue
            if self.stemming:
                shaped = stem(shaped)
            kept.append(
                Token(text=shaped, position=position, start=begin, end=end)
            )
            position += 1
        return kept

    def terms(self, text: str) -> list[str]:
        return [token.text for token in self.tokens(text)]

    def identity(self) -> str:
        return (
            f"lower={int(self.lowercase)}"
            f"|stop={int(self.drop_stopwords)}"
            f"|stem={int(self.stemming)}"
        )


def ngrams(term: str, width: int) -> list[str]:
    """Character n-grams for fuzzy lookup; the term padded at both ends."""
    if width < 2:
        raise Invalid("an n-gram needs width at least 2")
    padded = f"\x02{term}\x03"
    if len(padded) < width:
        return [padded]
    return [
        padded[index : index + width]
        for index in range(len(padded) - width + 1)
    ]
