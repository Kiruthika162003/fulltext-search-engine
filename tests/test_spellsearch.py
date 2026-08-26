from __future__ import annotations

import pytest

from quarry.engine import Engine
from quarry.errors import Invalid
from quarry.schema import Schema
from quarry.spellsearch import spellchecked_search


def library() -> Engine:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    engine = Engine(schema=schema)
    engine.add({"body": "the black cat sat on the mat"})
    engine.add({"body": "cats and their curious habits"})
    engine.add({"body": "a xylophone in the attic"})
    engine.commit()
    return engine


class TestTheTwoPasses:
    def test_a_healthy_first_pass_is_served_literally(self):
        answer = spellchecked_search(library(), "cat")
        assert answer.corrected_from is None
        assert answer.banner() is None
        assert len(answer.served.hits) == 2

    def test_a_typo_earns_the_rescue_with_the_banner(self):
        answer = spellchecked_search(library(), "catz")
        assert answer.corrected_from == "catz"
        assert answer.served.query == "cat"
        assert len(answer.served.hits) == 2
        assert answer.banner() == (
            "showing results for 'cat' (searched instead of 'catz')"
        )

    def test_the_literal_pass_rides_along_for_audit(self):
        answer = spellchecked_search(library(), "catz")
        assert answer.literal.hits == ()

    def test_unrescuable_gibberish_gets_the_honest_empty_page(self):
        answer = spellchecked_search(library(), "qqqqq")
        assert answer.corrected_from is None
        assert answer.served.hits == ()

    def test_an_unusual_word_typed_on_purpose_is_never_corrected(self):
        answer = spellchecked_search(library(), "xylophone")
        assert answer.corrected_from is None
        assert len(answer.served.hits) == 1

    def test_field_prefixes_survive_the_correction(self):
        answer = spellchecked_search(library(), "body:catz")
        assert answer.served.query == "body:cat"

    def test_a_rescue_floor_under_one_is_refused(self):
        with pytest.raises(Invalid, match="did not drown"):
            spellchecked_search(library(), "cat", rescue_floor=0)
