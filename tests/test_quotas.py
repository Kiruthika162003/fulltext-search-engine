from __future__ import annotations

import pytest

from quarry.errors import Frozen, Invalid, Missing
from quarry.quotas import Quota, QuotaBoard, TenantMeter


def small_quota() -> Quota:
    return Quota(documents=3, searches_per_window=4)


class TestTheQuotaItself:
    def test_zero_quotas_are_bans_in_disguise(self):
        with pytest.raises(Invalid, match="ban"):
            Quota(documents=0, searches_per_window=5)


class TestDocuments:
    def test_admission_counts_up_to_the_line(self):
        meter = TenantMeter(quota=small_quota())
        for _ in range(3):
            meter.admit_document()
        with pytest.raises(Frozen, match="3 of 3 held"):
            meter.admit_document()

    def test_release_reopens_the_door(self):
        meter = TenantMeter(quota=small_quota())
        for _ in range(3):
            meter.admit_document()
        meter.release_document()
        meter.admit_document()
        assert meter.documents_held == 3

    def test_releasing_below_zero_exposes_double_counting(self):
        with pytest.raises(Invalid, match="double"):
            TenantMeter(quota=small_quota()).release_document()


class TestSearches:
    def test_a_burst_inside_the_window_is_refused(self):
        meter = TenantMeter(quota=small_quota())
        for tick in range(4):
            meter.admit_search(tick)
        with pytest.raises(Frozen, match="room opens in"):
            meter.admit_search(3)

    def test_old_searches_age_out_of_the_window(self):
        meter = TenantMeter(quota=small_quota())
        for tick in range(4):
            meter.admit_search(tick)
        meter.admit_search(10)
        assert len(meter.window) == 1

    def test_the_refusal_does_arithmetic_for_the_caller(self):
        meter = TenantMeter(quota=small_quota())
        for tick in range(4):
            meter.admit_search(tick)
        with pytest.raises(Frozen, match="4 searches inside"):
            meter.admit_search(3)


class TestTheBoard:
    def test_enrollment_is_once(self):
        board = QuotaBoard()
        board.enroll("acme", small_quota())
        with pytest.raises(Invalid, match="already enrolled"):
            board.enroll("acme", small_quota())

    def test_unknown_tenants_are_missing(self):
        with pytest.raises(Missing, match="no quota enrolled"):
            QuotaBoard().meter("ghost")

    def test_raises_are_on_the_record(self):
        board = QuotaBoard()
        board.enroll("acme", small_quota())
        board.grant_raise(
            "acme",
            Quota(documents=10, searches_per_window=8),
            author="ops",
        )
        assert "raised to 10 documents" in board.board_report()
        assert "by ops" in board.board_report()

    def test_shrinking_under_held_documents_is_refused(self):
        board = QuotaBoard()
        board.enroll("acme", small_quota())
        meter = board.meter("acme")
        for _ in range(3):
            meter.admit_document()
        with pytest.raises(Invalid, match="strands data"):
            board.grant_raise(
                "acme",
                Quota(documents=2, searches_per_window=4),
                author="ops",
            )

    def test_the_report_reads_per_tenant(self):
        board = QuotaBoard()
        board.enroll("acme", small_quota())
        board.meter("acme").admit_document()
        assert board.board_report() == (
            "acme: 1/3 documents, 0/4 recent searches"
        )
