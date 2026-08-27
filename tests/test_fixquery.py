from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.fixquery import repair


class TestNoTouch:
    def test_a_healthy_query_is_never_touched(self):
        held = repair("body:cat +body:dog")
        assert held.mends == ()
        assert held.narrated() == "parsed as typed"
        assert held.query.canonical() == "body:cat +body:dog"


class TestMends:
    def test_the_unclosed_quote_closes_at_the_end(self):
        held = repair('body:"deep work')
        assert held.mends == (
            "closed the unclosed quote at the end",
        )
        assert held.query.canonical() == 'body:"deep work"'

    def test_the_trailing_or_is_dropped(self):
        held = repair("body:cat OR")
        assert held.query.canonical() == "body:cat"
        assert "trailing OR" in held.mends[0]

    def test_the_trailing_plus_is_dropped(self):
        held = repair("body:cat +")
        assert held.query.canonical() == "body:cat"
        assert "trailing +" in held.mends[0]

    def test_the_fieldless_colon_is_stripped(self):
        held = repair(":cat")
        assert held.query.canonical() == "body:cat"
        assert "no field before it" in held.mends[0]

    def test_repairs_are_narrated_for_the_interface(self):
        held = repair("body:cat OR")
        assert held.narrated().startswith("searched with repairs:")


class TestTheCap:
    def test_two_mends_can_stack(self):
        held = repair('body:"deep work OR')
        assert len(held.mends) <= 2

    def test_noise_falls_through_to_the_honest_error(self):
        with pytest.raises(Invalid, match="noise wearing"):
            repair("OR OR OR OR")
