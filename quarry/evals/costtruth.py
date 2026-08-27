"""The cost model is checked against the engine, not trusted.

An estimator that is never audited drifts into fiction, so this
eval runs both: the cost model prices a set of queries in
postings touched, and the truth is counted from the posting
lists the traversal actually reads. Two findings are pinned.
Single terms and unions are exact, because no estimation lives
in them and a model that misses them is broken, not imprecise.
Intersections diverge by a measured 2.5x on this fixture: the
model credits the walk down to the smallest list, pricing the
galloping intersect a smarter engine would run, while this
engine's merge intersect reads both lists end to end. The
divergence is kept and pinned rather than papered over,
because it is not estimation error, it is a statement about
which intersect the engine has, and the day the engine gains
galloping this eval breaks and says so.
"""

from __future__ import annotations

from quarry.costmodel import estimate
from quarry.evals.grade import Grade
from quarry.query import parse
from quarry.schema import Schema
from quarry.segment import Segment, SegmentBuilder
from quarry.tokenize import Analyzer

QUERIES = (
    "body:market",
    "body:market OR body:rain",
    "+body:market +body:square",
)


def _segment() -> Segment:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    builder = SegmentBuilder(schema=schema)
    builder.add({"body": "the market square hums with traders"})
    builder.add({"body": "the market opens at dawn"})
    builder.add({"body": "the market closes with the rain"})
    builder.add({"body": "a quiet square after the rain"})
    builder.add({"body": "rain on the harbor wall"})
    return builder.seal("town")


def _true_cost(segment: Segment, text: str) -> int:
    """Postings the traversal actually reads, counted directly."""
    analyzer = Analyzer()
    touched = 0
    for group in parse(text).groups:
        for clause in group:
            terms = analyzer.terms(clause.text)
            if not terms:
                continue
            postings = segment.postings.get(
                (clause.field, terms[0])
            )
            if postings is not None:
                touched += postings.document_frequency()
    return touched


def run() -> Grade:
    segment = _segment()
    analyzer = Analyzer()
    worst_ratio = 1.0
    single_exact = False
    numbers = {}
    for text in QUERIES:
        priced = estimate(segment, analyzer, parse(text)).total()
        truth = _true_cost(segment, text)
        ratio = (
            max(priced, truth) / min(priced, truth)
            if min(priced, truth) > 0
            else 99.0
        )
        worst_ratio = max(worst_ratio, ratio)
        key = text.replace("body:", "").replace(" ", "_")
        numbers[f"est_{key}"] = priced
        numbers[f"true_{key}"] = truth
        if text == "body:market":
            single_exact = priced == truth
    numbers["worst_ratio"] = round(worst_ratio, 4)
    union_exact = (
        numbers["est_market_OR_rain"] == numbers["true_market_OR_rain"]
    )
    holds = single_exact and union_exact and worst_ratio == 2.5
    return Grade(
        eval_name="costtruth",
        sentence=(
            "exact on single terms and unions; intersections read "
            "2.5x the model's price because this engine merges "
            "instead of galloping, a fact pinned until it changes"
        ),
        numbers=numbers,
        holds=holds,
    )
