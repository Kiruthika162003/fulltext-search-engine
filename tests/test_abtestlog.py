from __future__ import annotations

import pytest

from quarry.abtestlog import AssignmentLog, Experiment, assign
from quarry.errors import Invalid


def ranking_test() -> Experiment:
    return Experiment(name="bm25-vs-boosted", treatment_share=0.5)


class TestAssignment:
    def test_the_same_user_keeps_the_same_arm(self):
        experiment = ranking_test()
        arms = {assign(experiment, "ada") for _ in range(20)}
        assert len(arms) == 1

    def test_different_experiments_decorrelate(self):
        first = Experiment(name="test-one", treatment_share=0.5)
        second = Experiment(name="test-two", treatment_share=0.5)
        users = [f"user-{n}" for n in range(200)]
        both_same = sum(
            1
            for user in users
            if assign(first, user) == assign(second, user)
        )
        assert 60 < both_same < 140

    def test_a_rollout_is_not_an_experiment(self):
        with pytest.raises(Invalid, match="rollout"):
            Experiment(name="x", treatment_share=1.0)

    def test_anonymous_users_cannot_keep_arms(self):
        with pytest.raises(Invalid):
            assign(ranking_test(), "")


class TestTheLog:
    def test_arm_hopping_is_named_mud(self):
        log = AssignmentLog(experiment=ranking_test())
        log.arm_for("ada")
        log.seen["ada"] = (
            "treatment"
            if log.seen["ada"] == "control"
            else "control"
        )
        with pytest.raises(Invalid, match="mud"):
            log.arm_for("ada")

    def test_the_realised_split_tracks_the_declared(self):
        log = AssignmentLog(experiment=ranking_test())
        for number in range(400):
            log.arm_for(f"user-{number}")
        assert abs(log.realised_split() - 0.5) < 0.08

    def test_the_audit_blesses_a_healthy_split(self):
        log = AssignmentLog(experiment=ranking_test())
        for number in range(400):
            log.arm_for(f"user-{number}")
        assert log.audit(tolerance=0.08).startswith("split healthy")

    def test_the_audit_names_the_drift_and_the_suspects(self):
        log = AssignmentLog(experiment=ranking_test())
        for number in range(50):
            log.seen[f"user-{number}"] = "treatment"
        verdict = log.audit()
        assert verdict.startswith("SPLIT DRIFTED")
        assert "every downstream number is suspect" in verdict

    def test_empty_logs_refuse_the_split(self):
        with pytest.raises(Invalid):
            AssignmentLog(experiment=ranking_test()).realised_split()
