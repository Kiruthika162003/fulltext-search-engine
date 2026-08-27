"""A partial answer on time is honest exactly when it says so.

Three segments of different sizes hold seven harbor documents.
With a generous clock the search is complete and recall is 1.0,
the baseline that proves the fixture. With a clock that only
covers the biggest segment the search returns fewer harbors,
recall drops to the measured share, and three promises are
checked instead of assumed: the complete flag is down, every
hit returned is still a real harbor because partial loses
recall, never correctness, and docs_unreached equals exactly
the live documents of the segments never walked, arithmetic a
dashboard can subtract. The share of runs that went partial is
read off the searcher afterward, because an engine that serves
partials without counting them is quietly redefining fast.
"""

from __future__ import annotations

from quarry.deadline import BudgetClock, DeadlineSearcher
from quarry.evals.grade import Grade, precision, recall
from quarry.query import parse
from quarry.schema import Schema
from quarry.writer import Index

HARBORS = {0, 1, 2, 3, 4}


def _index() -> Index:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    index = Index(schema=schema)
    for text in (
        "the harbor wall at dawn",
        "a harbor full of sails",
        "the harbor master's ledger",
        "gulls above the harbor",
    ):
        index.add({"body": text})
    index.flush()
    for text in (
        "one more harbor, smaller",
        "a field with no water at all",
    ):
        index.add({"body": text})
    index.flush()
    index.add({"body": "an inland town"})
    index.flush()
    return index


def run() -> Grade:
    index = _index()
    searcher = DeadlineSearcher(index=index)
    query = parse("body:harbor")

    generous = searcher.search(query, BudgetClock(budget=100))
    full_recall = recall(list(generous.externals), HARBORS)

    tight = searcher.search(query, BudgetClock(budget=4))
    tight_recall = recall(list(tight.externals), HARBORS)
    tight_precision = precision(list(tight.externals), HARBORS)
    unreached_truth = sum(
        segment.live_count()
        for segment in index.segments
        if segment.name in tight.segments_unreached
    )

    holds = (
        full_recall == 1.0
        and generous.complete
        and not tight.complete
        and tight_recall == 0.8
        and tight_precision == 1.0
        and tight.docs_unreached == unreached_truth == 3
        and searcher.partial_share() == 0.5
    )
    return Grade(
        eval_name="deadlinehonesty",
        sentence=(
            "a tight clock loses recall, never correctness, and "
            "the loss is stated in documents"
        ),
        numbers={
            "full_recall": full_recall,
            "tight_recall": tight_recall,
            "tight_precision": tight_precision,
            "docs_unreached": tight.docs_unreached,
            "partial_share": searcher.partial_share(),
        },
        holds=holds,
    )
