from __future__ import annotations

import pytest

from quarry.errors import Frozen, Invalid
from quarry.indexfreeze import FreezeBoard, FreezeWindow


def peak_weekend() -> FreezeBoard:
    board = FreezeBoard()
    board.declare(
        FreezeWindow(
            start=100,
            end=200,
            reason="peak weekend",
            owner="search-lead",
        )
    )
    return board


class TestDeclaration:
    def test_backward_windows_never_happen(self):
        with pytest.raises(Invalid, match="never happens"):
            FreezeWindow(start=5, end=5, reason="r", owner="o")

    def test_ownerless_walls_may_not_be_questioned(self):
        with pytest.raises(Invalid, match="both are required"):
            FreezeWindow(start=1, end=2, reason="  ", owner="o")

    def test_overlapping_windows_are_two_authorities(self):
        board = peak_weekend()
        with pytest.raises(Invalid, match="one wall at a time"):
            board.declare(
                FreezeWindow(
                    start=150,
                    end=250,
                    reason="another",
                    owner="else",
                )
            )


class TestEnforcement:
    def test_mutations_freeze_inside_the_window(self):
        board = peak_weekend()
        with pytest.raises(Frozen, match="frozen until 200"):
            board.check("reindex", tick=150)

    def test_reads_are_never_blocked(self):
        board = peak_weekend()
        assert "never block reads" in board.check("search", 150)

    def test_outside_the_window_life_goes_on(self):
        board = peak_weekend()
        assert "no freeze covers 99" in board.check("add", 99)
        assert "no freeze covers 200" in board.check("add", 200)

    def test_unclassified_operations_are_refused(self):
        with pytest.raises(Invalid, match="classify it"):
            peak_weekend().check("mystery-job", 150)


class TestOverrides:
    def test_the_hole_is_loud_and_recorded(self):
        board = peak_weekend()
        message = board.punch_through(
            "delete", 150, who="kiru", why="dmca takedown 44"
        )
        assert "on the record" in message
        review = board.review()
        assert "1 override(s)" in review
        assert "[150] kiru: delete (dmca takedown 44)" in review

    def test_nameless_holes_are_owned_by_nobody(self):
        with pytest.raises(Invalid, match="nobody owns"):
            peak_weekend().punch_through("delete", 150, " ", "x")

    def test_practicing_overrides_is_refused(self):
        with pytest.raises(Invalid, match="practicing"):
            peak_weekend().punch_through(
                "delete", 50, who="kiru", why="drill"
            )

    def test_reads_need_no_hole(self):
        with pytest.raises(Invalid, match="reads need no"):
            peak_weekend().punch_through(
                "search", 150, who="kiru", why="checking"
            )


class TestReview:
    def test_the_review_reads_every_hole(self):
        board = peak_weekend()
        board.punch_through("delete", 150, "kiru", "takedown")
        board.punch_through("add", 160, "ben", "vip fix")
        page = board.review()
        assert "2 override(s)" in page
        assert page.count("[1") >= 3
