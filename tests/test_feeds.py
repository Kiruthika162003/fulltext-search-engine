from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.feeds import FeedAdapter, FieldRule


def press_adapter() -> FeedAdapter:
    return FeedAdapter(
        rules=[
            FieldRule(
                target="body",
                sources=("headline", "standfirst"),
                required=True,
            ),
            FieldRule(target="author", sources=("byline",)),
            FieldRule(target="source", sources=(), constant="wire"),
        ],
        dead_letter_limit=2,
    )


class TestAdapting:
    def test_renames_joins_and_constants(self):
        shaped = press_adapter().adapt(
            {
                "headline": "Cat rescued",
                "standfirst": "from tall tree",
                "byline": "M. Iyer",
                "wordcount": 340,
            }
        )
        assert shaped == {
            "body": "Cat rescued from tall tree",
            "author": "M. Iyer",
            "source": "wire",
        }

    def test_unmapped_fields_are_dropped_and_counted(self):
        adapter = press_adapter()
        adapter.adapt(
            {"headline": "News", "wordcount": 340, "priority": "high"}
        )
        assert adapter.fields_dropped == 2

    def test_optional_gaps_are_left_out_not_padded(self):
        shaped = press_adapter().adapt({"headline": "Solo headline"})
        assert "author" not in shaped
        assert shaped["body"] == "Solo headline"


class TestTheDeadLetterQueue:
    def test_a_missing_required_field_dies_with_its_body(self):
        adapter = press_adapter()
        assert adapter.adapt({"byline": "Nobody"}) is None
        assert len(adapter.dead_letters) == 1
        letter = adapter.dead_letters[0]
        assert letter.row == {"byline": "Nobody"}
        assert "required field body" in letter.complaint

    def test_the_queue_is_bounded_and_overflow_counted(self):
        adapter = press_adapter()
        for number in range(4):
            adapter.adapt({"note": f"empty {number}"})
        assert len(adapter.dead_letters) == 2
        assert adapter.dead_letter_overflow == 2

    def test_the_intake_report_counts_all_three_fates(self):
        adapter = press_adapter()
        adapter.adapt({"headline": "Good"})
        for _ in range(3):
            adapter.adapt({})
        report = adapter.intake_report()
        assert report.startswith("1 rows adapted, 3 dead (1 past the queue)")

    def test_first_complaints_read_in_arrival_order(self):
        adapter = press_adapter()
        adapter.adapt({})
        complaints = adapter.first_complaints(limit=1)
        assert complaints == [
            "required field body has no source among headline, "
            "standfirst"
        ]


class TestContracts:
    def test_a_constant_with_sources_is_two_rules(self):
        with pytest.raises(Invalid, match="two rules"):
            FieldRule(
                target="x", sources=("a",), constant="fixed"
            )

    def test_an_empty_rule_maps_nothing(self):
        with pytest.raises(Invalid, match="maps nothing"):
            FieldRule(target="x", sources=())

    def test_duplicate_targets_are_refused(self):
        with pytest.raises(Invalid, match="one field, one rule"):
            FeedAdapter(
                rules=[
                    FieldRule(target="x", sources=("a",)),
                    FieldRule(target="x", sources=("b",)),
                ]
            )
