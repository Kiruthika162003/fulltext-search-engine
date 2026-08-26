from __future__ import annotations

import pytest

from quarry.boosts import (
    NEUTRAL,
    BoostedHit,
    BoostProfile,
    PinBoard,
    boosted_search,
)
from quarry.errors import Invalid, Missing
from quarry.multisearch import search_index
from quarry.query import parse
from quarry.schema import Schema
from quarry.writer import Index


def catalogue() -> Index:
    schema = Schema()
    schema.add_text("title")
    schema.add_text("body")
    schema.seal()
    index = Index(schema=schema)
    index.add({"title": "cat care", "body": "feeding and general notes"})
    index.add({"title": "dog training", "body": "the cat next door watches"})
    index.add({"title": "garden birds", "body": "cats stalk the feeder daily"})
    index.flush()
    return index


def both_fields(text: str) -> str:
    return f"title:{text} body:{text}"


class TestProfiles:
    def test_double_boosting_a_field_is_refused(self):
        with pytest.raises(Invalid, match="one field, one number"):
            BoostProfile(
                name="bad", weights=(("title", 2.0), ("title", 3.0))
            )

    def test_nonpositive_boosts_are_refused(self):
        with pytest.raises(Invalid, match="positive"):
            BoostProfile(name="bad", weights=(("title", 0.0),))

    def test_the_diff_reads_field_by_field(self):
        before = BoostProfile(name="a", weights=(("title", 2.0),))
        after = BoostProfile(
            name="b", weights=(("title", 3.0), ("body", 0.5))
        )
        assert before.diff(after) == ["body: 1.0 -> 0.5", "title: 2.0 -> 3.0"]


class TestNeutrality:
    def test_the_neutral_profile_is_plain_bm25(self):
        index = catalogue()
        query = parse(both_fields("cat"))
        plain = [
            (hit.external, hit.score)
            for hit in search_index(index, query).hits
        ]
        neutral = [
            (hit.external, hit.score)
            for hit in boosted_search(index, query, NEUTRAL)
        ]
        assert neutral == plain


class TestBoosting:
    def test_a_title_boost_lifts_the_title_hit(self):
        index = catalogue()
        query = parse(both_fields("cat"))
        neutral_top = boosted_search(index, query, NEUTRAL)[0].external
        titled = BoostProfile(name="titled", weights=(("title", 5.0),))
        boosted_top = boosted_search(index, query, titled)[0].external
        assert boosted_top == 0
        assert neutral_top != 0 or boosted_top == neutral_top

    def test_a_body_boost_pulls_the_other_way(self):
        index = catalogue()
        query = parse(both_fields("cat"))
        bodied = BoostProfile(name="bodied", weights=(("body", 5.0),))
        top = boosted_search(index, query, bodied)[0].external
        assert top in (1, 2)

    def test_a_zero_limit_is_refused(self):
        with pytest.raises(Invalid):
            boosted_search(catalogue(), parse("title:cat"), limit=0)


class TestPins:
    def test_a_pin_needs_a_reason(self):
        with pytest.raises(Invalid, match="quiet override"):
            PinBoard().pin(1, "cat", who="meera", reason="   ")

    def test_a_pin_rides_to_the_front_marked(self):
        index = catalogue()
        pins = PinBoard()
        pins.pin(2, "cat", who="meera", reason="campaign week")
        hits = boosted_search(
            index,
            parse(both_fields("cat")),
            pins=pins,
            query_text="cat",
        )
        assert hits[0] == BoostedHit(external=2, score=0.0, pinned=True)
        assert not hits[1].pinned

    def test_a_pin_cannot_conjure_relevance(self):
        index = catalogue()
        pins = PinBoard()
        pins.pin(0, "zebra", who="raj", reason="wishful thinking")
        with pytest.raises(Missing, match="conjure"):
            boosted_search(
                index,
                parse(both_fields("zebra")),
                pins=pins,
                query_text="zebra",
            )

    def test_the_journal_names_every_override(self):
        pins = PinBoard()
        pins.pin(2, "cat", who="meera", reason="campaign week")
        assert "meera: campaign week" in pins.journal()
        assert PinBoard().journal().startswith("no pins")
