from __future__ import annotations

import pytest

from quarry.backfill import Backfill
from quarry.errors import Frozen, Invalid, Missing


def marathon() -> Backfill:
    return Backfill(total_documents=95, batch_size=10)


class TestPartitioning:
    def test_the_last_batch_is_short_and_honest(self):
        run = marathon()
        assert run.batch_count() == 10
        assert run.batch_bounds(9) == (90, 95)

    def test_nonexistent_batches_are_named(self):
        with pytest.raises(Missing, match="0 to 9"):
            marathon().batch_bounds(10)

    def test_empty_backfills_are_already_done(self):
        with pytest.raises(Invalid, match="already done"):
            Backfill(total_documents=0, batch_size=10)


class TestProgress:
    def test_the_frontier_skips_done_and_parked(self):
        run = marathon()
        run.complete_batch(0)
        run.park_batch(1, "timeout on shard-b")
        assert run.frontier() == 2
        assert "resume at batch 2 (documents 20-29)" in run.resume_point()

    def test_doubling_a_batch_is_refused(self):
        run = marathon()
        run.complete_batch(0)
        with pytest.raises(Invalid, match="doubles its documents"):
            run.complete_batch(0)

    def test_progress_names_the_parked(self):
        run = marathon()
        run.complete_batch(0)
        run.park_batch(3, "bad row 34")
        page = run.progress()
        assert page.startswith("1/10 batches, 10/95 documents")
        assert "3: bad row 34" in page

    def test_parking_without_the_error_loses_the_clue(self):
        with pytest.raises(Invalid, match="only clue"):
            marathon().park_batch(0, "  ")


class TestTheFuse:
    def test_systematic_failure_blows_the_fuse(self):
        run = marathon()
        run.complete_batch(0)
        run.park_batch(1, "schema mismatch")
        message = run.park_batch(2, "schema mismatch")
        assert "FUSE BLOWN" in message
        with pytest.raises(Frozen, match="systematic"):
            run.complete_batch(3)

    def test_scattered_failures_do_not(self):
        run = marathon()
        for batch in range(8):
            run.complete_batch(batch)
        message = run.park_batch(8, "one bad row")
        assert "marathon continues" in message

    def test_retry_clears_the_abort(self):
        run = marathon()
        run.complete_batch(0)
        run.park_batch(1, "schema mismatch")
        run.park_batch(2, "schema mismatch")
        message = run.retry_parked(1)
        assert "back in play" in message
        assert run.complete_batch(1) == "batch 1 done"


class TestCompletion:
    def test_a_finished_marathon_says_complete(self):
        run = Backfill(total_documents=20, batch_size=10)
        run.complete_batch(0)
        run.complete_batch(1)
        assert run.resume_point() == "complete"

    def test_an_exhausted_frontier_points_at_the_parked(self):
        run = Backfill(total_documents=20, batch_size=10)
        run.complete_batch(0)
        run.park_batch(1, "stuck")
        assert "1 parked batch(es) remain" in run.resume_point()
