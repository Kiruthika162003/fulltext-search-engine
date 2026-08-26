"""An eval is an experiment whose conclusion is chained to its numbers.

Each eval module builds a fixture corpus, runs real queries through
the real engine, and returns a Grade: the sentence the experiment
supports, the metric numbers behind it, and whether the checks that
make the sentence true still pass. A grade whose checks fail is
kept and reported, not hidden, because a broken expectation is the
most informative thing a quality suite produces. The metrics here
are the standard ones with their edges stated: precision is of the
returned, recall is of the relevant, reciprocal rank rewards the
first good answer, and all three refuse to average over nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quarry.errors import Invalid


@dataclass(frozen=True)
class Grade:
    eval_name: str
    sentence: str
    numbers: dict = field(default_factory=dict)
    holds: bool = True

    def line(self) -> str:
        mark = "holds" if self.holds else "BROKEN"
        shown = ", ".join(
            f"{key}={value}" for key, value in sorted(self.numbers.items())
        )
        return f"{self.eval_name}: {self.sentence} [{mark}] ({shown})"


def precision(returned: list[int], relevant: set[int]) -> float:
    if not returned:
        raise Invalid("precision over an empty return is not a number")
    hits = sum(1 for doc in returned if doc in relevant)
    return round(hits / len(returned), 4)


def recall(returned: list[int], relevant: set[int]) -> float:
    if not relevant:
        raise Invalid("recall needs at least one relevant document")
    hits = sum(1 for doc in returned if doc in relevant)
    return round(hits / len(relevant), 4)


def reciprocal_rank(returned: list[int], relevant: set[int]) -> float:
    for position, doc in enumerate(returned, start=1):
        if doc in relevant:
            return round(1.0 / position, 4)
    return 0.0


def mean_reciprocal_rank(
    runs: list[tuple[list[int], set[int]]]
) -> float:
    if not runs:
        raise Invalid("a mean over no runs is not a number")
    total = sum(
        reciprocal_rank(returned, relevant) for returned, relevant in runs
    )
    return round(total / len(runs), 4)
