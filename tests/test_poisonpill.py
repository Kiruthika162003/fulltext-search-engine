from __future__ import annotations

import pytest

from quarry.errors import Frozen, Invalid, Missing
from quarry.poisonpill import PoisonLedger


def poisoned() -> PoisonLedger:
    ledger = PoisonLedger()
    ledger.record_crash("body:bomb", "worker-1")
    ledger.record_crash("body:bomb", "worker-2")
    return ledger


class TestQuarantine:
    def test_one_crash_censors_nothing(self):
        ledger = PoisonLedger()
        message = ledger.record_crash("body:odd", "worker-1")
        assert "many\nmothers" in message or "many mothers" in message
        assert not ledger.quarantined("body:odd")
        assert ledger.admit("body:odd") == "admitted"

    def test_two_crashes_quarantine(self):
        ledger = poisoned()
        assert ledger.quarantined("body:bomb")
        with pytest.raises(Frozen, match="sacrifice"):
            ledger.admit("body:bomb")

    def test_the_refusal_names_the_fallen(self):
        ledger = poisoned()
        with pytest.raises(Frozen, match="worker-1, worker-2"):
            ledger.admit("body:bomb")

    def test_crashes_need_both_names(self):
        with pytest.raises(Invalid, match="both"):
            PoisonLedger().record_crash("body:x", "  ")


class TestParole:
    def test_parole_frees_with_a_named_fix(self):
        ledger = poisoned()
        ledger.parole(
            "body:bomb", who="ops", fix="regex bound in v2.1"
        )
        assert ledger.admit("body:bomb") == "admitted"

    def test_hope_is_not_a_patch(self):
        with pytest.raises(Invalid, match="hope as the patch"):
            poisoned().parole("body:bomb", who="ops", fix=" ")

    def test_paroling_the_innocent_is_refused(self):
        with pytest.raises(Missing, match="not the innocent"):
            PoisonLedger().parole("body:fine", who="ops", fix="x")

    def test_a_crash_after_parole_revokes_it(self):
        ledger = poisoned()
        ledger.parole("body:bomb", who="ops", fix="patched")
        message = ledger.record_crash("body:bomb", "worker-3")
        assert "parole is revoked" in message
        assert ledger.quarantined("body:bomb")


class TestTheReport:
    def test_the_postmortem_starts_written(self):
        ledger = poisoned()
        with pytest.raises(Frozen):
            ledger.admit("body:bomb")
        page = ledger.report()
        assert "body:bomb: 2 crash(es) (worker-1, worker-2)" in page
        assert "[QUARANTINED]" in page
        assert "1 admission(s) refused" in page

    def test_states_are_distinguished(self):
        ledger = poisoned()
        ledger.record_crash("body:odd", "worker-9")
        ledger.parole("body:bomb", who="ops", fix="patched")
        page = ledger.report()
        assert "[watching]" in page
        assert "PAROLED: ops: patched" in page
