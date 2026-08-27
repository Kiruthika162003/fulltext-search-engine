from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.fusion import agreement, fuse, fusion_explain


def three_rankers() -> dict[str, list[int]]:
    return {
        "lexical": [1, 2, 3],
        "links": [2, 1, 4],
        "freshness": [2, 5, 1],
    }


class TestFusing:
    def test_steady_seconds_beat_a_lone_first(self):
        fused = fuse(
            {
                "a": [7, 9],
                "b": [9, 7],
                "c": [9, 8],
            }
        )
        assert fused[0].external == 9

    def test_the_consensus_pick_leads(self):
        fused = fuse(three_rankers())
        assert fused[0].external == 2
        assert fused[0].lists_voting == 3

    def test_single_list_wonders_are_labeled(self):
        fused = fuse(three_rankers())
        wonder = next(h for h in fused if h.external == 4)
        assert wonder.lists_voting == 1
        assert "single-list wonder" in wonder.line()

    def test_duplicate_ballots_are_laundering(self):
        with pytest.raises(Invalid, match="laundering"):
            fuse({"a": [1, 1, 2]})

    def test_zero_k_restores_the_tyranny(self):
        with pytest.raises(Invalid, match="tyranny"):
            fuse(three_rankers(), k=0)

    def test_fusing_nothing_ranks_nothing(self):
        with pytest.raises(Invalid, match="ranks nothing"):
            fuse({})


class TestExplaining:
    def test_every_vote_and_abstention_is_shown(self):
        page = fusion_explain(three_rankers(), 4)
        assert "links: rank 3" in page
        assert "lexical: abstained (not a penalty)" in page
        assert "freshness: abstained" in page

    def test_the_total_closes(self):
        page = fusion_explain(three_rankers(), 2)
        assert page.endswith("total 0.048916")


class TestAgreement:
    def test_agreement_is_the_shared_share(self):
        assert agreement(three_rankers(), depth=3) == 0.6667

    def test_one_ranker_cannot_agree_with_itself(self):
        with pytest.raises(Invalid, match="two rankers"):
            agreement({"a": [1]})
