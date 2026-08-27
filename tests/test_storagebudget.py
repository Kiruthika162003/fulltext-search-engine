from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.storagebudget import (
    estimate_storage,
    project_growth,
)


def phrase_heavy():
    return estimate_storage(
        posting_entries=1000,
        position_entries=9000,
        stored_chars=2000,
        tombstones=50,
    )


class TestEstimation:
    def test_each_category_prices_by_its_constant(self):
        held = phrase_heavy()
        assert held.postings_bytes == 8000
        assert held.positions_bytes == 36000
        assert held.stored_bytes == 2016
        assert held.tombstone_bytes == 200
        assert held.total() == 46216

    def test_fewer_positions_than_postings_is_impossible(self):
        with pytest.raises(Invalid, match="impossible"):
            estimate_storage(
                posting_entries=100,
                position_entries=50,
                stored_chars=0,
                tombstones=0,
            )

    def test_negative_counts_are_counting_bugs(self):
        with pytest.raises(Invalid, match="counting bug"):
            estimate_storage(-1, 0, 0, 0)


class TestTheReport:
    def test_shares_sum_and_the_total_closes(self):
        page = phrase_heavy().report()
        assert "positions: 36000 bytes (78%)" in page
        assert "total: 46216 bytes" in page

    def test_position_domination_names_the_cheap_win(self):
        page = phrase_heavy().report()
        assert "disabling positions" in page

    def test_other_leaders_stay_quiet_about_positions(self):
        held = estimate_storage(
            posting_entries=1000,
            position_entries=1000,
            stored_chars=90000,
            tombstones=0,
        )
        assert held.dominant() == "stored fields"
        assert "disabling positions" not in held.report()


class TestProjection:
    def test_fitting_growth_is_a_subtraction(self):
        page = project_growth(
            phrase_heavy(),
            current_docs=100,
            future_docs=200,
            budget_bytes=100_000,
        )
        assert "project to 92432 bytes" in page
        assert "fits with 7568 to spare" in page

    def test_overruns_name_the_dominant_category(self):
        page = project_growth(
            phrase_heavy(),
            current_docs=100,
            future_docs=300,
            budget_bytes=100_000,
        )
        assert "OVER BUDGET by 38648" in page
        assert "dominated by positions" in page

    def test_shrinkage_inverts_the_tool(self):
        with pytest.raises(Invalid, match="inverts"):
            project_growth(
                phrase_heavy(),
                current_docs=100,
                future_docs=50,
                budget_bytes=100_000,
            )
