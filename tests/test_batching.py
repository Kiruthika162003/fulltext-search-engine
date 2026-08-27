from __future__ import annotations

import pytest

from quarry.batching import BulkLoader
from quarry.errors import Invalid
from quarry.schema import Schema
from quarry.writer import Index


def loader(budget: float = 0.5) -> BulkLoader:
    schema = Schema()
    schema.add_text("body")
    schema.add_numeric("year")
    schema.seal()
    return BulkLoader(
        index=Index(schema=schema), failure_budget=budget
    )


class TestPerRowVerdicts:
    def test_one_bad_row_does_not_sink_the_batch(self):
        receipt = loader().load(
            [
                {"body": "good one"},
                {"year": "not-a-number"},
                {"body": "good two"},
            ]
        )
        assert receipt.accepted == 2
        assert receipt.rejected == 1
        assert receipt.abandoned_after is None

    def test_verdicts_keep_their_positions(self):
        receipt = loader().load(
            [{"body": "ok"}, {"ghost_field": "x"}, {"body": "ok"}]
        )
        assert [v.position for v in receipt.verdicts] == [0, 1, 2]
        assert receipt.verdicts[1].accepted is False
        assert "ghost_field" in receipt.verdicts[1].refusal

    def test_accepted_rows_carry_their_new_ids(self):
        receipt = loader().load([{"body": "a"}, {"body": "b"}])
        assert [v.external for v in receipt.verdicts] == [0, 1]

    def test_the_good_rows_become_searchable(self):
        bulk = loader()
        bulk.load([{"body": "keep me"}, {"year": "bad"}])
        assert bulk.index.searchable_count() == 1


class TestTheBudget:
    def garbage_feed(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for number in range(30):
            if number % 10 == 0:
                rows.append({"body": f"good {number}"})
            else:
                rows.append({"year": f"bad {number}"})
        return rows

    def test_a_garbage_feed_is_abandoned_with_the_reason(self):
        receipt = loader(budget=0.5).load(self.garbage_feed())
        assert receipt.abandoned_after is not None
        tail = receipt.verdicts[-1]
        assert "fix the producer" in tail.refusal

    def test_the_abandonment_covers_every_remaining_row(self):
        receipt = loader(budget=0.5).load(self.garbage_feed())
        assert len(receipt.verdicts) == 30
        assert receipt.accepted + receipt.rejected == 30

    def test_a_healthy_batch_never_trips_the_budget(self):
        rows = [{"body": f"doc {n}"} for n in range(30)]
        receipt = loader(budget=0.1).load(rows)
        assert receipt.abandoned_after is None
        assert receipt.accepted == 30

    def test_the_budget_waits_for_a_minimum_sample(self):
        rows: list[dict[str, object]] = [
            {"year": "bad"},
            {"year": "bad"},
            {"body": "good"},
        ]
        receipt = loader(budget=0.5).load(rows)
        assert receipt.abandoned_after is None
        assert receipt.accepted == 1


class TestContracts:
    def test_an_empty_batch_is_a_heartbeat(self):
        with pytest.raises(Invalid, match="heartbeat"):
            loader().load([])

    def test_a_zero_budget_is_refused(self):
        with pytest.raises(Invalid):
            loader(budget=0.0)
