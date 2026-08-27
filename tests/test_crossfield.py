from __future__ import annotations

import pytest

from quarry.crossfield import CrossFieldScorer
from quarry.errors import Invalid


def scorer(tiebreak: float = 0.1) -> CrossFieldScorer:
    return CrossFieldScorer(
        boosts={"title": 2.0, "body": 1.0}, tiebreak=tiebreak
    )


class TestConstruction:
    def test_a_tiebreaker_of_one_is_the_summing_bug(self):
        with pytest.raises(Invalid, match="summing bug"):
            scorer(tiebreak=1.0)

    def test_zero_boosts_silence_fields(self):
        with pytest.raises(Invalid, match="silences the"):
            CrossFieldScorer(boosts={"title": 0.0})


class TestJudging:
    def test_the_best_field_wins_the_term(self):
        verdict = scorer().judge_term(
            "cat", {"title": 0.5, "body": 0.9}
        )
        assert verdict.winner.field_name == "title"
        assert verdict.winner.weighted() == 1.0

    def test_whispers_break_ties_but_never_beat_the_winner(self):
        wide = scorer().judge_term(
            "cat", {"title": 0.5, "body": 0.9}
        )
        narrow = scorer().judge_term("cat", {"title": 0.55})
        assert wide.score() == 1.09
        assert narrow.score() == 1.1
        assert narrow.score() > wide.score()

    def test_pure_winner_takes_all_at_zero(self):
        verdict = scorer(tiebreak=0.0).judge_term(
            "cat", {"title": 0.5, "body": 0.9}
        )
        assert verdict.score() == 1.0

    def test_unmatched_terms_are_none(self):
        assert (
            scorer().judge_term("cat", {"title": 0.0, "body": 0.0})
            is None
        )

    def test_stray_fields_are_refused(self):
        with pytest.raises(Invalid, match="unboosted"):
            scorer().judge_term("cat", {"footer": 0.4})


class TestDocuments:
    def test_the_document_score_sums_term_verdicts(self):
        total, lines = scorer().score_document(
            {
                "cat": {"title": 0.5, "body": 0.9},
                "nap": {"body": 0.4},
            }
        )
        assert total == 1.49
        assert lines[0].startswith("cat: title wins at 1.0")
        assert "whispers (body=0.9) x tiebreak 0.1" in lines[0]

    def test_unmatched_terms_are_narrated_not_dropped(self):
        _, lines = scorer().score_document(
            {"ghost": {"title": 0.0}}
        )
        assert lines == ["ghost: no field matched"]
