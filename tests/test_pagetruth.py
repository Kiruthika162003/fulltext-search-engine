from __future__ import annotations

from quarry.evals import pagetruth
from quarry.evals.registry import EVALS


class TestPageTruth:
    def test_the_grade_holds(self):
        assert pagetruth.run().holds

    def test_the_quiet_walk_is_exact(self):
        numbers = pagetruth.run().numbers
        assert numbers["pages_walked"] == 3
        assert numbers["documents_walked"] == 5
        assert numbers["matches_one_shot"] == 1

    def test_the_stats_drift_limit_is_pinned(self):
        numbers = pagetruth.run().numbers
        assert numbers["mid_write_overlap"] == 1

    def test_the_sentence_states_the_limit(self):
        grade = pagetruth.run()
        assert "measured limit" in grade.sentence

    def test_the_eval_is_registered(self):
        assert "quarry.evals.pagetruth" in EVALS
