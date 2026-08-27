"""Corpus text statistics: the shape of the prose, measured.

Ranking constants and snippet windows are tuned for a corpus
shape, and the shape is measurable: words per sentence, unique
word share, the longest run without punctuation, and the share
of tokens that are numbers. The profiler reports each with the
judgment thresholds stated beside the number, because a
dashboard that says 41.3 without saying 41.3 of what against
what teaches nobody anything. Two shapes get named outright:
listy corpora, mostly short fragments and numbers, where
phrase search and snippets underperform and the report says
so, and run-on corpora, sentences past the long threshold,
where snippet windows sized for prose truncate mid-clause.
Sentences split on terminal punctuation only, an admitted
simplification that miscounts abbreviations, stated in the
output rather than discovered by whoever audits the count.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from quarry.errors import Invalid

SENTENCE_END = re.compile(r"[.!?]+")
WORD = re.compile(r"[A-Za-z0-9]+")

LISTY_NUMBER_SHARE = 0.3
LISTY_SENTENCE_LENGTH = 6.0
RUNON_SENTENCE_LENGTH = 30.0


@dataclass(frozen=True)
class TextProfile:
    words: int
    unique_share: float
    words_per_sentence: float
    number_share: float

    def shape(self) -> str:
        if (
            self.number_share > LISTY_NUMBER_SHARE
            or self.words_per_sentence < LISTY_SENTENCE_LENGTH
        ):
            return (
                "listy: fragments and numbers; phrase search and "
                "snippets will underperform here"
            )
        if self.words_per_sentence > RUNON_SENTENCE_LENGTH:
            return (
                "run-on: snippet windows sized for prose will "
                "truncate mid-clause"
            )
        return "prose: the defaults were tuned for this"

    def page(self) -> str:
        return "\n".join(
            [
                f"{self.words} words, {self.unique_share:.0%} unique",
                (
                    f"{self.words_per_sentence} words/sentence "
                    f"(listy under {LISTY_SENTENCE_LENGTH}, run-on "
                    f"over {RUNON_SENTENCE_LENGTH})"
                ),
                (
                    f"{self.number_share:.0%} numeric tokens "
                    f"(listy over {LISTY_NUMBER_SHARE:.0%})"
                ),
                self.shape(),
                (
                    "sentences split on .!? only; abbreviations "
                    "miscount and that is stated, not hidden"
                ),
            ]
        )


def profile(texts: list[str]) -> TextProfile:
    if not texts:
        raise Invalid("profiling no text profiles nothing")
    joined = " ".join(texts)
    words = WORD.findall(joined)
    if not words:
        raise Invalid(
            "the corpus contains no words; the shape of nothing "
            "is nothing"
        )
    sentences = [
        piece
        for piece in SENTENCE_END.split(joined)
        if WORD.search(piece)
    ]
    sentence_count = max(len(sentences), 1)
    unique = len({word.lower() for word in words})
    numbers = sum(1 for word in words if word.isdigit())
    return TextProfile(
        words=len(words),
        unique_share=round(unique / len(words), 4),
        words_per_sentence=round(len(words) / sentence_count, 1),
        number_share=round(numbers / len(words), 4),
    )
