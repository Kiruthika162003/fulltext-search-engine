from __future__ import annotations

import pytest

from quarry.errors import Invalid, Missing
from quarry.percolate import Percolator
from quarry.schema import Schema


def newsroom() -> Percolator:
    schema = Schema()
    schema.add_text("body")
    schema.add_keyword("section")
    schema.seal()
    percolator = Percolator(schema=schema)
    percolator.subscribe("cat-news", "cat")
    percolator.subscribe("storm-watch", '"heavy rain"')
    percolator.subscribe("finance-cats", "+cat +section:finance")
    return percolator


class TestSubscribing:
    def test_double_subscription_is_refused(self):
        percolator = newsroom()
        with pytest.raises(Invalid, match="already subscribed"):
            percolator.subscribe("cat-news", "dog")

    def test_a_pure_exclusion_cannot_subscribe(self):
        percolator = newsroom()
        with pytest.raises(Invalid):
            percolator.subscribe("no-dogs", "-dog")

    def test_unsubscribing_the_unknown_is_named(self):
        with pytest.raises(Missing):
            newsroom().unsubscribe("ghost")


class TestFiring:
    def test_a_matching_document_fires_the_subscription(self):
        result = newsroom().percolate(
            {"body": "a cat stuck in a tree", "section": "local"}
        )
        assert result.fired == ("cat-news",)

    def test_phrases_demand_adjacency_at_fire_time(self):
        percolator = newsroom()
        apart = percolator.percolate(
            {"body": "rain was heavy across town"}
        )
        together = percolator.percolate(
            {"body": "heavy rain flooded the underpass"}
        )
        assert "storm-watch" not in apart.fired
        assert "storm-watch" in together.fired

    def test_keyword_clauses_bind_at_fire_time(self):
        percolator = newsroom()
        wrong_section = percolator.percolate(
            {"body": "cat markets rally", "section": "local"}
        )
        right_section = percolator.percolate(
            {"body": "cat markets rally", "section": "finance"}
        )
        assert "finance-cats" not in wrong_section.fired
        assert "finance-cats" in right_section.fired

    def test_unsubscribed_queries_stop_firing(self):
        percolator = newsroom()
        percolator.unsubscribe("cat-news")
        result = percolator.percolate({"body": "a cat on the loose"})
        assert "cat-news" not in result.fired


class TestTheShortcut:
    def test_the_map_skips_the_unrelated(self):
        result = newsroom().percolate({"body": "quiet gardening tips"})
        assert result.fired == ()
        assert result.candidates_checked == 0
        assert result.skipped_by_the_map == 3

    def test_the_skip_count_stays_auditable_on_hits(self):
        result = newsroom().percolate({"body": "the cat sat"})
        assert result.candidates_checked >= 1
        assert (
            result.candidates_checked + result.skipped_by_the_map == 3
        )

    def test_no_false_fires_from_the_shortcut(self):
        percolator = newsroom()
        result = percolator.percolate(
            {"body": "heavy traffic, light rain"}
        )
        assert "storm-watch" not in result.fired
        assert result.candidates_checked >= 1
