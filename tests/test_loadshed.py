from __future__ import annotations

import pytest

from quarry.errors import Frozen, Invalid
from quarry.loadshed import LoadShedder


class TestLevels:
    def test_calm_admits_anything(self):
        shedder = LoadShedder()
        assert "admitted at calm" in shedder.admit(1_000_000)

    def test_unknown_levels_show_the_scale(self):
        with pytest.raises(Invalid, match="calm, busy"):
            LoadShedder().set_level("panicking")

    def test_the_transition_is_narrated(self):
        shedder = LoadShedder()
        assert shedder.set_level("busy") == "pressure calm -> busy"


class TestShedding:
    def test_the_ceiling_tightens_with_pressure(self):
        shedder = LoadShedder()
        shedder.set_level("busy")
        assert "admitted" in shedder.admit(400)
        shedder.set_level("strained")
        with pytest.raises(Frozen, match="ceiling of 100"):
            shedder.admit(400)

    def test_critical_still_serves_the_cheap(self):
        shedder = LoadShedder()
        shedder.set_level("critical")
        assert "admitted" in shedder.admit(15)

    def test_the_refusal_carries_estimate_and_hint(self):
        shedder = LoadShedder()
        shedder.set_level("critical")
        with pytest.raises(Frozen, match="narrow it or retry"):
            shedder.admit(500)

    def test_negative_estimates_are_not_estimates(self):
        with pytest.raises(Invalid, match="not an estimate"):
            LoadShedder().admit(-1)


class TestBatchPolicy:
    def test_batch_faces_a_quarter_of_the_ceiling(self):
        shedder = LoadShedder()
        shedder.set_level("busy")
        assert "admitted" in shedder.admit(400, interactive=True)
        with pytest.raises(Frozen, match="batch"):
            shedder.admit(400, interactive=False)

    def test_cheap_batch_still_lands(self):
        shedder = LoadShedder()
        shedder.set_level("busy")
        assert "admitted" in shedder.admit(100, interactive=False)


class TestTheLedger:
    def test_sheds_are_counted_per_level(self):
        shedder = LoadShedder()
        shedder.set_level("strained")
        with pytest.raises(Frozen):
            shedder.admit(500)
        shedder.set_level("critical")
        with pytest.raises(Frozen):
            shedder.admit(500)
        shedder.admit(10)
        page = shedder.ledger()
        assert "strained: 1" in page
        assert "critical: 1" in page
        assert "admitted 1" in page
