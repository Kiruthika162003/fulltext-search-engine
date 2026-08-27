from __future__ import annotations

import pytest

from quarry.costmodel import classify, estimate
from quarry.errors import Invalid
from quarry.query import parse
from quarry.schema import Schema
from quarry.segment import Segment, SegmentBuilder
from quarry.tokenize import Analyzer


def town() -> Segment:
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


class TestTermCosts:
    def test_a_term_costs_its_document_frequency(self):
        held = estimate(town(), Analyzer(), parse("body:market"))
        assert held.total() == 3

    def test_an_absent_term_costs_nothing(self):
        held = estimate(town(), Analyzer(), parse("body:zeppelin"))
        assert held.total() == 0

    def test_a_union_costs_the_sum_of_branches(self):
        held = estimate(
            town(), Analyzer(), parse("body:market OR body:rain")
        )
        assert held.total() == 6

    def test_an_intersection_credits_down_to_the_smallest(self):
        held = estimate(
            town(), Analyzer(), parse("+body:market +body:square")
        )
        assert held.total() == 2

    def test_a_phrase_costs_its_rarest_word_plus_surcharge(self):
        held = estimate(
            town(), Analyzer(), parse('"market square"')
        )
        assert held.total() == 6

    def test_empty_queries_cost_nothing_and_run_never(self):
        with pytest.raises(Invalid, match="runs never"):
            estimate(town(), Analyzer(), parse("body:the"))


class TestBreakdown:
    def test_every_line_is_decomposable(self):
        held = estimate(
            town(), Analyzer(), parse("+body:market +body:square")
        )
        page = held.breakdown()
        assert "+body:market: 3" in page
        assert "+body:square: 2" in page
        assert "credit: -3" in page
        assert page.endswith("total: 2 postings touched")


class TestClassification:
    def test_cheap_queries_are_under_one_per_document(self):
        held = estimate(town(), Analyzer(), parse("body:market"))
        assert classify(held, town()).startswith("cheap")

    def test_the_expensive_label_suggests_tightening(self):
        wide = estimate(
            town(),
            Analyzer(),
            parse(
                "body:market OR body:rain OR body:square OR "
                "body:market OR body:rain OR body:square OR "
                "body:market OR body:rain"
            ),
        )
        verdict = classify(wide, town())
        assert verdict.startswith("expensive")
        assert "tightening" in verdict
