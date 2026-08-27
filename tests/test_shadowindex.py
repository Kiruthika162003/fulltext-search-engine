from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.shadowindex import MIN_SAMPLES, ShadowLedger


class TestWrites:
    def test_shadow_failures_never_break_the_live_path(self):
        ledger = ShadowLedger()
        message = ledger.record_write(shadow_ok=False)
        assert "counted, not raised" in message
        assert ledger.live_writes == 1
        assert ledger.shadow_write_errors == 1

    def test_clean_writes_land_on_both(self):
        ledger = ShadowLedger()
        assert ledger.record_write(shadow_ok=True) == "written to both"


class TestComparisons:
    def test_agreement_is_exact_order_agreement(self):
        ledger = ShadowLedger()
        assert ledger.record_comparison("q", [1, 2], [1, 2]) == "agreed"
        assert ledger.agreement() == 1.0

    def test_membership_differences_are_itemized(self):
        ledger = ShadowLedger()
        message = ledger.record_comparison("q", [1, 2, 3], [2, 3, 4])
        assert "live-only [1]" in message
        assert "shadow-only [4]" in message

    def test_pure_reorderings_are_named_as_such(self):
        ledger = ShadowLedger()
        message = ledger.record_comparison("q", [1, 2], [2, 1])
        assert "same documents, different order" in message

    def test_agreement_over_nothing_is_a_shrug(self):
        with pytest.raises(Invalid, match="shrug"):
            ShadowLedger().agreement()


def seasoned_ledger(agree: int, disagree: int) -> ShadowLedger:
    ledger = ShadowLedger()
    for n in range(agree):
        ledger.record_comparison(f"a{n}", [1], [1])
    for n in range(disagree):
        ledger.record_comparison(f"d{n}", [1], [2])
    return ledger


class TestCutover:
    def test_thin_sampling_is_named_first(self):
        ready, page = seasoned_ledger(10, 0).ready_to_cut()
        assert not ready
        assert f"10 of {MIN_SAMPLES}" in page

    def test_low_agreement_is_named_with_the_bar(self):
        ready, page = seasoned_ledger(48, 12).ready_to_cut()
        assert not ready
        assert "agreement 0.8 under the 0.95 bar" in page

    def test_unexplained_write_errors_block(self):
        ledger = seasoned_ledger(60, 0)
        ledger.record_write(shadow_ok=False)
        ready, page = ledger.ready_to_cut()
        assert not ready
        assert "1 shadow write error(s) unexplained" in page

    def test_a_clean_shadow_reads_ready(self):
        ledger = seasoned_ledger(58, 2)
        ready, page = ledger.ready_to_cut()
        assert ready
        assert page.startswith("READY: 97% agreement over 60")


class TestTheDigest:
    def test_the_digest_caps_and_counts_the_rest(self):
        ledger = seasoned_ledger(0, 8)
        page = ledger.disagreement_digest(top_n=3)
        assert page.count("membership") == 3
        assert page.endswith("and 5 more")

    def test_a_clean_ledger_says_so(self):
        assert (
            ShadowLedger().disagreement_digest()
            == "no disagreements recorded"
        )
