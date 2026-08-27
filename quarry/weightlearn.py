"""Learning field weights from pairwise judgments, transparently.

When a searcher says this result should have beaten that one,
the pair is a training signal for field weights: each document
side is a vector of per-field match scores, and the learner
nudges weights toward scoring the preferred document higher
using the perceptron update, the simplest learner that works
and the only one whose every step can be printed. Three
constraints keep the learned weights sane: weights stay
nonnegative because a negative title weight means matching the
title hurts, which is never the intended lesson from sparse
pairs; weights normalize to sum to the field count so they are
comparable across retrainings; and the learner reports its
disagreement rate on the training pairs afterward, because a
learner that cannot state how many pairs it still gets wrong
is a learner nobody should deploy.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid

LEARNING_RATE = 0.1
SWEEPS = 20


@dataclass(frozen=True)
class JudgedPair:
    winner: dict[str, float]
    loser: dict[str, float]

    def fields(self) -> set[str]:
        return set(self.winner) | set(self.loser)


@dataclass
class WeightLearner:
    field_names: tuple[str, ...]
    weights: dict[str, float] = field(default_factory=dict)
    updates: int = 0

    def __post_init__(self) -> None:
        if not self.field_names:
            raise Invalid("no fields means nothing to weight")
        if not self.weights:
            self.weights = dict.fromkeys(self.field_names, 1.0)

    def _score(self, vector: dict[str, float]) -> float:
        return sum(
            self.weights[name] * vector.get(name, 0.0)
            for name in self.field_names
        )

    def _check_pair(self, pair: JudgedPair) -> None:
        strays = pair.fields() - set(self.field_names)
        if strays:
            raise Invalid(
                f"pair mentions unweighted field(s) "
                f"{', '.join(sorted(strays))}"
            )

    def train(self, pairs: list[JudgedPair]) -> str:
        if not pairs:
            raise Invalid("training on no pairs learns nothing")
        for pair in pairs:
            self._check_pair(pair)
        for _ in range(SWEEPS):
            wrong = 0
            for pair in pairs:
                if self._score(pair.winner) > self._score(pair.loser):
                    continue
                wrong += 1
                self.updates += 1
                for name in self.field_names:
                    delta = pair.winner.get(name, 0.0) - pair.loser.get(
                        name, 0.0
                    )
                    self.weights[name] = max(
                        0.0,
                        self.weights[name] + LEARNING_RATE * delta,
                    )
            if wrong == 0:
                break
        self._normalize()
        return self.report(pairs)

    def _normalize(self) -> None:
        total = sum(self.weights.values())
        if total == 0:
            raise Invalid(
                "all weights collapsed to zero; the pairs "
                "contradict so thoroughly that no field helps"
            )
        scale = len(self.field_names) / total
        self.weights = {
            name: round(weight * scale, 4)
            for name, weight in self.weights.items()
        }

    def disagreements(self, pairs: list[JudgedPair]) -> int:
        return sum(
            1
            for pair in pairs
            if self._score(pair.winner) <= self._score(pair.loser)
        )

    def report(self, pairs: list[JudgedPair]) -> str:
        shown = ", ".join(
            f"{name}={self.weights[name]}"
            for name in self.field_names
        )
        wrong = self.disagreements(pairs)
        return (
            f"weights: {shown}; {self.updates} update(s); still "
            f"wrong on {wrong} of {len(pairs)} training pair(s)"
        )
