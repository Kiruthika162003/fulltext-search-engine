from __future__ import annotations

import pytest

from quarry.bulkingest import BulkIngest
from quarry.errors import Invalid


class PriceValidator:
    def check(self, document: dict[str, object]) -> str | None:
        price = document.get("price")
        if price is not None and not isinstance(price, int):
            return f"price {price!r} is not an integer"
        return None


def ingester() -> BulkIngest:
    return BulkIngest(validator=PriceValidator())


class TestJudgingAlone:
    def test_one_bad_row_sinks_only_itself(self):
        outcomes, summary = ingester().ingest(
            [
                ("k1", {"body": "good", "price": 10}),
                ("k2", {"body": "bad", "price": "ten"}),
                ("k3", {"body": "also good"}),
            ]
        )
        assert summary == (
            "2 admitted, 1 refused, 0 duplicate(s) = 3 of 3"
        )
        assert outcomes[1].status == "refused"
        assert "not an integer" in outcomes[1].detail

    def test_empty_documents_index_nothing(self):
        outcomes, _ = ingester().ingest([("k1", {})])
        assert outcomes[0].status == "refused"

    def test_empty_batches_are_refused(self):
        with pytest.raises(Invalid, match="bulks nothing"):
            ingester().ingest([])


class TestIdempotency:
    def test_retried_keys_are_duplicates_not_errors(self):
        held = ingester()
        held.ingest([("k1", {"body": "first"})])
        outcomes, summary = held.ingest(
            [("k1", {"body": "first"}), ("k2", {"body": "new"})]
        )
        assert outcomes[0].status == "duplicate"
        assert "first admitted at position 0" in outcomes[0].detail
        assert "1 admitted, 0 refused, 1 duplicate(s)" in summary
        assert len(held.admitted_documents) == 2

    def test_empty_keys_deduplicate_nothing(self):
        outcomes, _ = ingester().ingest([("  ", {"body": "x"})])
        assert outcomes[0].status == "refused"
        assert "cannot" in outcomes[0].detail


class TestRetryLoop:
    def test_the_caller_can_retry_exactly_the_failures(self):
        held = ingester()
        outcomes, _ = held.ingest(
            [
                ("k1", {"body": "good"}),
                ("k2", {"price": "bad"}),
                ("k3", {}),
            ]
        )
        assert held.retry_positions(outcomes) == [1, 2]

    def test_the_arithmetic_always_sums_to_the_batch(self):
        held = ingester()
        held.ingest([("k1", {"body": "x"})])
        outcomes, summary = held.ingest(
            [
                ("k1", {"body": "x"}),
                ("k4", {"price": "bad"}),
                ("k5", {"body": "y"}),
                ("", {"body": "z"}),
            ]
        )
        assert summary.endswith("= 4 of 4")
        assert len(outcomes) == 4
