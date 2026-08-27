"""An afternoon in the relevance lab: the evals run, the knobs answer.

Run with: python -m examples.relevancelab
"""

from __future__ import annotations

from quarry.evals.registry import all_grades
from quarry.interleave import InterleaveExperiment
from quarry.minshould import dial_report
from quarry.schema import Schema
from quarry.segment import SegmentBuilder
from quarry.tokenize import Analyzer


def eval_sweep() -> None:
    print("the standing evals:")
    for grade in all_grades():
        mark = "holds" if grade.holds else "BROKEN"
        print(f"  [{mark}] {grade.eval_name}")


def dial_session() -> None:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    builder = SegmentBuilder(schema=schema)
    builder.add({"body": "wireless noise cancelling headphones"})
    builder.add({"body": "wireless headphones with long battery"})
    builder.add({"body": "noise cancelling earbuds"})
    builder.add({"body": "wired studio headphones"})
    segment = builder.seal("shop")
    terms = tuple(
        Analyzer().terms("wireless noise cancelling headphones")
    )
    print(dial_report(segment, "body", terms))


def click_battle() -> None:
    experiment = InterleaveExperiment(coin=[True, False])
    baseline = [10, 11, 12, 13]
    challenger = [12, 10, 14, 11]
    experiment.serve_and_observe(baseline, challenger, clicked=[12, 14])
    experiment.serve_and_observe(baseline, challenger, clicked=[12])
    experiment.serve_and_observe(baseline, challenger, clicked=[14, 12])
    print(f"interleaving: {experiment.verdict()}")


def main() -> int:
    eval_sweep()
    dial_session()
    click_battle()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
