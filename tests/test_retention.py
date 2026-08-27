from __future__ import annotations

import pytest

from quarry.errors import Invalid, Missing
from quarry.retention import RetentionPolicy, RetentionRule

TODAY = 20000


def office_policy() -> RetentionPolicy:
    policy = RetentionPolicy()
    policy.declare(RetentionRule("log", keep_days=30))
    policy.declare(RetentionRule("contract", keep_days=3650))
    return policy


def office_docs() -> list[tuple[int, str, int]]:
    return [
        (0, "log", TODAY - 10),
        (1, "log", TODAY - 45),
        (2, "log", TODAY - 90),
        (3, "contract", TODAY - 400),
        (4, "contract", TODAY - 4000),
    ]


class TestRules:
    def test_zero_day_retention_is_refused(self):
        with pytest.raises(Invalid, match="refuse at the door"):
            RetentionRule("temp", keep_days=0)

    def test_unclassified_documents_do_not_live_forever(self):
        policy = office_policy()
        with pytest.raises(Missing, match="silently live forever"):
            policy.expired([(9, "mystery", TODAY - 5)], TODAY)

    def test_future_documents_expose_broken_clocks(self):
        policy = office_policy()
        with pytest.raises(Invalid, match="future"):
            policy.expired([(9, "log", TODAY + 5)], TODAY)


class TestExpiry:
    def test_each_expiry_names_its_rule_and_age(self):
        doomed = office_policy().expired(office_docs(), TODAY)
        assert (1, "log kept 30d, aged 45d") in doomed
        assert (4, "contract kept 3650d, aged 4000d") in doomed

    def test_the_young_survive(self):
        doomed = dict(office_policy().expired(office_docs(), TODAY))
        assert 0 not in doomed
        assert 3 not in doomed


class TestHolds:
    def test_a_hold_outranks_the_calendar(self):
        policy = office_policy()
        policy.hold(1, "litigation 44-2026")
        doomed = dict(policy.expired(office_docs(), TODAY))
        assert 1 not in doomed
        assert 2 in doomed

    def test_holds_need_reasons(self):
        with pytest.raises(Invalid, match="deposition"):
            office_policy().hold(1, "  ")

    def test_releasing_a_phantom_hold_is_named(self):
        with pytest.raises(Missing, match="wrong id"):
            office_policy().release_hold(7)

    def test_released_holds_expire_again(self):
        policy = office_policy()
        policy.hold(1, "litigation 44-2026")
        policy.release_hold(1)
        doomed = dict(policy.expired(office_docs(), TODAY))
        assert 1 in doomed


class TestTheSweep:
    def test_the_sweep_reports_its_arithmetic(self):
        policy = office_policy()
        policy.hold(2, "litigation 44-2026")
        removed, report = policy.sweep(office_docs(), TODAY)
        assert removed == [1, 4]
        assert report == (
            "swept 2 of 5; 1 under hold survived regardless"
        )

    def test_a_policy_typo_dies_in_the_dry_run(self):
        policy = RetentionPolicy()
        policy.declare(RetentionRule("log", keep_days=1))
        docs = [(n, "log", TODAY - 100) for n in range(4)]
        with pytest.raises(Invalid, match="guard"):
            policy.sweep(docs, TODAY)

    def test_the_ledger_traces_deletions_to_rules(self):
        policy = office_policy()
        policy.hold(2, "litigation 44-2026")
        policy.sweep(office_docs(), TODAY)
        page = policy.ledger()
        assert "doc 1: log kept 30d, aged 45d" in page

    def test_sweeping_nothing_is_refused(self):
        with pytest.raises(Invalid, match="sweeps nothing"):
            office_policy().sweep([], TODAY)
