from __future__ import annotations

import pytest

from quarry.config import EngineConfig
from quarry.errors import Invalid


class TestValidation:
    def test_defaults_stand_up_on_their_own(self):
        config = EngineConfig()
        assert config.get("flush_at") == 128
        assert config.get("merge_fanout") == 4

    def test_typos_are_refused_with_the_roster(self):
        with pytest.raises(Invalid, match="the roster is"):
            EngineConfig(values={"flush_att": 10})

    def test_bounds_carry_their_reasons(self):
        with pytest.raises(Invalid, match="buffered documents"):
            EngineConfig(values={"flush_at": 0})

    def test_overrides_at_construction_are_validated(self):
        config = EngineConfig(values={"slow_line": 500})
        assert config.get("slow_line") == 500


class TestApplying:
    def test_the_diff_reports_what_actually_moved(self):
        config = EngineConfig()
        moved = config.apply(
            {"slow_line": 200, "merge_fanout": 4}, who="meera"
        )
        assert moved == ["slow_line: 100 -> 200 (by meera)"]

    def test_history_accumulates_the_moves(self):
        config = EngineConfig()
        config.apply({"slow_line": 200}, who="meera")
        config.apply({"slow_line": 300}, who="raj")
        assert config.history == [
            "slow_line: 100 -> 200 (by meera)",
            "slow_line: 200 -> 300 (by raj)",
        ]

    def test_an_empty_change_set_is_refused(self):
        with pytest.raises(Invalid, match="say so"):
            EngineConfig().apply({}, who="meera")

    def test_bad_values_never_partially_apply(self):
        config = EngineConfig()
        with pytest.raises(Invalid):
            config.apply(
                {"slow_line": 200, "merge_fanout": 999}, who="meera"
            )
        assert config.get("slow_line") == 100


class TestTheFreeze:
    def test_frozen_knobs_refuse_the_midnight_temptation(self):
        config = EngineConfig()
        with pytest.raises(Invalid, match="midnight temptation"):
            config.apply(
                {"flush_at": 1}, who="tired-oncall", during_incident=True
            )

    def test_the_same_change_lands_in_calm_weather(self):
        config = EngineConfig()
        moved = config.apply({"flush_at": 64}, who="meera")
        assert moved == ["flush_at: 128 -> 64 (by meera)"]

    def test_show_marks_the_frozen(self):
        page = EngineConfig().show()
        assert "flush_at = 128" in page
        assert "[frozen during incidents]" in page
        assert "slow_line = 100 (ticks before a query is slow)" in page
