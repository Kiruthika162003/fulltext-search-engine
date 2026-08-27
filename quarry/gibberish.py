"""A gibberish gate: keyboard mash is scored, not pattern-matched.

Autocomplete and did-you-mean should never learn from asdfjkl,
and blocklisting mash by regex loses to every new mash. The
gate scores strings by character bigram likelihood: trained on
a sample of real corpus text, it knows th and er and an are
how the language walks, while zx and qq and fj are how elbows
walk, and a string whose average bigram log-probability falls
under the trained threshold is mash however novel it is. The
disciplines: the model trains on the corpus it will judge,
because English bigrams misjudge German customers; unseen
bigrams cost a floor probability instead of zero, since one
rare pair must dent a score, not annihilate it; the threshold
is calibrated from held-out real words, set below the worst of
them, and the calibration is part of training, not a magic
number; and short strings pass ungated because two characters
are not enough evidence to call anyone's elbows.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field

from quarry.errors import Invalid

FLOOR_PROBABILITY = 1e-4
MIN_JUDGED_LENGTH = 4


@dataclass
class GibberishGate:
    bigram_counts: dict[str, int] = field(default_factory=dict)
    total_bigrams: int = 0
    threshold: float = 0.0
    trained: bool = False

    def _bigrams(self, text: str) -> list[str]:
        cleaned = "".join(
            char for char in text.lower() if char.isalpha()
        )
        return [
            left + right
            for left, right in itertools.pairwise(cleaned)
        ]

    def train(
        self, corpus_words: list[str], holdout: list[str]
    ) -> str:
        if len(corpus_words) < 20 or len(holdout) < 5:
            raise Invalid(
                "training wants at least twenty corpus words and "
                "five held out; less is a model of an anecdote"
            )
        for word in corpus_words:
            for bigram in self._bigrams(word):
                self.bigram_counts[bigram] = (
                    self.bigram_counts.get(bigram, 0) + 1
                )
                self.total_bigrams += 1
        if self.total_bigrams == 0:
            raise Invalid("the corpus held no letter pairs at all")
        self.trained = True
        worst = min(self.score(word) for word in holdout)
        self.threshold = worst - 0.5
        return (
            f"trained on {self.total_bigrams} bigram(s); "
            f"threshold {self.threshold:.2f}, set under the worst "
            f"held-out real word"
        )

    def score(self, text: str) -> float:
        if not self.trained:
            raise Invalid(
                "an untrained gate judges nobody; train on the "
                "corpus it will judge"
            )
        bigrams = self._bigrams(text)
        if not bigrams:
            raise Invalid(
                f"{text!r} holds no letter pairs to score"
            )
        total = 0.0
        for bigram in bigrams:
            count = self.bigram_counts.get(bigram, 0)
            probability = max(
                count / self.total_bigrams, FLOOR_PROBABILITY
            )
            total += math.log(probability)
        return round(total / len(bigrams), 4)

    def is_mash(self, text: str) -> tuple[bool, str]:
        cleaned = "".join(
            char for char in text.lower() if char.isalpha()
        )
        if len(cleaned) < MIN_JUDGED_LENGTH:
            return False, (
                f"{text!r} passes ungated: {len(cleaned)} "
                f"letter(s) cannot convict anyone's elbows"
            )
        held = self.score(text)
        if held < self.threshold:
            return True, (
                f"{text!r} scores {held} under the "
                f"{self.threshold:.2f} threshold: mash"
            )
        return False, f"{text!r} scores {held}: walks like language"
