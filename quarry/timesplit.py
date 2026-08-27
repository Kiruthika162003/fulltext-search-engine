"""Time-split evaluation: the model never grades its own future.

Relevance experiments leak the future constantly: judgments
collected in March tuning a ranker evaluated on February
queries, click models trained through the boundary they are
scored on. The splitter enforces the only honest cut, a single
timestamp: everything before trains, everything at or after
tests, no shuffling, because shuffled splits let twins of test
queries into training and the offline gain evaporates in
production. The refusals carry the reasoning: a split leaving
either side thinner than the floor refuses since a verdict
from six test queries is an anecdote with an axis; records
bearing the same timestamp as the cut go to TEST, the rule
stated because whichever side they land on someone will assume
the other; and the leakage check takes a pair of supposedly
split sets and hunts for shared query keys across the
boundary, the audit that catches the pipeline bug after
someone refactors the loader.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid

SIDE_FLOOR = 10


@dataclass(frozen=True)
class Stamped:
    key: str
    day: int


def split(
    records: list[Stamped], cut_day: int
) -> tuple[list[Stamped], list[Stamped]]:
    if not records:
        raise Invalid("splitting nothing trains nothing")
    train = [held for held in records if held.day < cut_day]
    test = [held for held in records if held.day >= cut_day]
    if len(train) < SIDE_FLOOR or len(test) < SIDE_FLOOR:
        raise Invalid(
            f"the cut at {cut_day} leaves train={len(train)} and "
            f"test={len(test)} against a floor of {SIDE_FLOOR}; a "
            f"verdict from a handful of queries is an anecdote "
            f"with an axis"
        )
    return train, test


def cut_at_boundary_rule() -> str:
    return (
        f"records stamped exactly at the cut go to TEST; stated "
        f"because whichever side they land on, someone assumes "
        f"the other. Floors: {SIDE_FLOOR} per side"
    )


def leakage_audit(
    train: list[Stamped], test: list[Stamped]
) -> str:
    if not train or not test:
        raise Invalid("auditing an empty side audits nothing")
    train_keys = {held.key for held in train}
    test_keys = {held.key for held in test}
    shared = sorted(train_keys & test_keys)
    if shared:
        listed = ", ".join(shared[:5])
        more = (
            f" and {len(shared) - 5} more" if len(shared) > 5 else ""
        )
        raise Invalid(
            f"LEAKAGE: {len(shared)} query key(s) on both sides "
            f"({listed}{more}); the offline gain will evaporate "
            f"in production"
        )
    newest_train = max(held.day for held in train)
    oldest_test = min(held.day for held in test)
    if newest_train >= oldest_test:
        raise Invalid(
            f"TIME LEAK: training reaches day {newest_train} while "
            f"testing starts at {oldest_test}; the model grades "
            f"its own future"
        )
    return (
        f"clean split: train ends day {newest_train}, test "
        f"begins day {oldest_test}, no shared keys"
    )
