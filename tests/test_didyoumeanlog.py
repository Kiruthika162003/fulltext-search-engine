from __future__ import annotations

import pytest

from quarry.didyoumeanlog import CorrectionLedger
from quarry.errors import Invalid


def a_week() -> CorrectionLedger:
    ledger = CorrectionLedger()
    for _ in range(6):
        ledger.record(
            "catz", "cats", taken=True, clicked_after=True
        )
    ledger.record("catz", "cats", taken=True, clicked_after=False)
    for _ in range(2):
        ledger.record(
            "java",
            "java script",
            taken=False,
            clicked_after=False,
            original_succeeded=True,
        )
    ledger.record(
        "zzqqk", "zzqq", taken=False, clicked_after=False
    )
    return ledger


class TestRecording:
    def test_a_noop_correction_is_refused(self):
        with pytest.raises(Invalid, match="wearing a banner"):
            CorrectionLedger().record(
                "cats", "cats", taken=True, clicked_after=True
            )

    def test_crossed_sessions_blame_the_instrumentation(self):
        with pytest.raises(Invalid, match="crossed two sessions"):
            CorrectionLedger().record(
                "catz",
                "cats",
                taken=True,
                clicked_after=True,
                original_succeeded=True,
            )


class TestRates:
    def test_acceptance_flatters_and_saves_correct(self):
        ledger = a_week()
        assert ledger.acceptance_rate() == 0.7
        assert ledger.save_rate() == pytest.approx(6 / 7, abs=1e-4)

    def test_false_alarms_are_ignored_corrections_that_were_wrong(self):
        assert a_week().false_alarm_share() == 0.2

    def test_empty_ledgers_refuse_every_rate(self):
        ledger = CorrectionLedger()
        with pytest.raises(Invalid):
            ledger.acceptance_rate()
        with pytest.raises(Invalid):
            ledger.false_alarm_share()

    def test_saves_need_takers(self):
        ledger = CorrectionLedger()
        ledger.record(
            "a", "b", taken=False, clicked_after=False
        )
        with pytest.raises(Invalid, match="need takers"):
            ledger.save_rate()


class TestTheVerdict:
    def test_the_tripwire_names_the_fix(self):
        verdict = a_week().verdict()
        assert "FALSE ALARMS at 20%" in verdict
        assert "raise the correction floor" in verdict

    def test_a_clean_week_reads_inside_the_line(self):
        ledger = CorrectionLedger()
        for _ in range(5):
            ledger.record(
                "catz", "cats", taken=True, clicked_after=True
            )
        assert "inside the line" in ledger.verdict()
