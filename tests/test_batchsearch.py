from __future__ import annotations

import pytest

from quarry.batchsearch import run_batch
from quarry.errors import Invalid
from quarry.schema import Schema
from quarry.segment import Segment, SegmentBuilder


def town() -> Segment:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    builder = SegmentBuilder(schema=schema)
    builder.add({"body": "the market square hums"})
    builder.add({"body": "the market opens at dawn"})
    builder.add({"body": "rain over the square"})
    return builder.seal("town")


class TestBatching:
    def test_every_query_gets_its_answer(self):
        entries, _ = run_batch(
            town(), ["body:market", "body:square", "body:rain"]
        )
        assert entries[0].externals == (0, 1)
        assert entries[1].externals == (0, 2)
        assert entries[2].externals == (2,)

    def test_shared_terms_are_looked_up_once(self):
        _, summary = run_batch(
            town(),
            [
                "body:market body:square",
                "body:market body:rain",
            ],
        )
        assert "3 term lookups instead of 4 (1 avoided)" in summary

    def test_duplicates_are_mirrored_not_recomputed(self):
        entries, summary = run_batch(
            town(), ["body:market", "body:market"]
        )
        assert entries[0].externals == entries[1].externals
        assert "(1 distinct, 1 mirrored)" in summary

    def test_empty_batches_are_refused(self):
        with pytest.raises(Invalid, match="nothing"):
            run_batch(town(), [])


class TestPerQueryHonesty:
    def test_one_failure_is_its_own_entry(self):
        entries, summary = run_batch(
            town(), ["body:market", "ghost:field:extra:colons OR"]
        )
        assert entries[0].ok()
        assert not entries[1].ok()
        assert entries[1].error
        assert "1 failed alone" in summary

    def test_the_failed_entry_carries_the_refusal(self):
        entries, _ = run_batch(town(), ["body:market", "   "])
        assert "refused" in entries[1].error or entries[1].error

    def test_tombstones_stay_out_of_answers(self):
        segment = town()
        segment.delete(0)
        entries, _ = run_batch(segment, ["body:market"])
        assert entries[0].externals == (1,)
