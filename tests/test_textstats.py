from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.textstats import profile


class TestProfiling:
    def test_the_numbers_are_arithmetic(self):
        held = profile(
            [
                "The kettle sat on the stove.",
                "The stove was warm.",
            ]
        )
        assert held.words == 10
        assert held.words_per_sentence == 5.0
        assert held.unique_share == 0.7

    def test_numeric_tokens_are_counted(self):
        held = profile(["sku 1001 price 40 stock 3"])
        assert held.number_share == 0.5

    def test_emptiness_is_refused(self):
        with pytest.raises(Invalid, match="profiles nothing"):
            profile([])
        with pytest.raises(Invalid, match="shape of nothing"):
            profile(["...", "!!!"])


class TestShapes:
    def test_catalogs_read_as_listy(self):
        held = profile(
            ["sku 1001 40 kettle", "sku 1002 45 kettle"]
        )
        assert held.shape().startswith("listy")

    def test_prose_reads_as_prose(self):
        held = profile(
            [
                "The copper kettle sat quietly on the old stove "
                "while the winter light crossed the kitchen floor."
            ]
        )
        assert held.shape().startswith("prose")

    def test_runons_are_warned_about(self):
        one_breath = " ".join(["word"] * 45) + "."
        held = profile([one_breath])
        assert "truncate mid-clause" in held.shape()


class TestThePage:
    def test_every_number_states_its_thresholds(self):
        page = profile(["The kettle sat on the stove."]).page()
        assert "listy under 6.0" in page
        assert "run-on over 30.0" in page
        assert "listy over 30%" in page
        assert "stated, not hidden" in page
