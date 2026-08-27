from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.zeroresults import DeadQuery, TriageDesk, diagnose


def dead(
    text: str = "q",
    in_index: int = 0,
    total: int = 2,
    matched_before: bool = False,
    one_slip: bool = False,
) -> DeadQuery:
    return DeadQuery(
        text=text,
        terms_in_index=in_index,
        terms_total=total,
        matched_before_filters=matched_before,
        one_slip_from_vocabulary=one_slip,
    )


class TestDiagnosis:
    def test_unknown_words_are_vocabulary_misses(self):
        assert diagnose(dead(in_index=0)) == "vocabulary-miss"

    def test_one_slip_upgrades_to_typo_candidate(self):
        assert (
            diagnose(dead(in_index=0, one_slip=True))
            == "typo-candidate"
        )

    def test_filters_that_killed_matches_are_named(self):
        assert (
            diagnose(dead(in_index=2, matched_before=True))
            == "over-filtered"
        )

    def test_terms_that_never_cooccur_are_near_misses(self):
        assert diagnose(dead(in_index=2)) == "near-miss"

    def test_the_first_diagnosis_wins(self):
        smells_of_both = dead(
            in_index=2, matched_before=True, one_slip=True
        )
        assert diagnose(smells_of_both) == "over-filtered"

    def test_impossible_arithmetic_is_refused(self):
        with pytest.raises(Invalid, match="cannot happen"):
            dead(in_index=3, total=2)

    def test_termless_queries_never_lived(self):
        with pytest.raises(Invalid, match="never lived"):
            dead(total=0)


class TestTheDesk:
    def test_submissions_answer_with_the_fix(self):
        desk = TriageDesk()
        message = desk.submit(dead(text="zzyx kettle", in_index=0))
        assert "vocabulary-miss" in message
        assert "synonym ring" in message

    def test_the_digest_ranks_by_body_count(self):
        desk = TriageDesk()
        for n in range(3):
            desk.submit(dead(text=f"miss-{n}", in_index=0))
        desk.submit(dead(text="close one", in_index=2))
        page = desk.digest()
        assert page.startswith("4 dead quer(ies) triaged:")
        assert "vocabulary-miss: 3 (75%)" in page
        assert page.endswith(
            "the week's engineering goes to vocabulary-miss"
        )

    def test_an_empty_desk_stays_honest(self):
        assert "either great or unread" in TriageDesk().digest()
