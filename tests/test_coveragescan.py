from __future__ import annotations

import pytest

from quarry.coveragescan import (
    coverage_report,
    orphan_share,
    scan_segment,
)
from quarry.errors import Invalid
from quarry.schema import Schema
from quarry.segment import Segment, SegmentBuilder


def mixed_bag() -> Segment:
    schema = Schema()
    schema.add_text("body")
    schema.add_stored("blob")
    schema.seal()
    builder = SegmentBuilder(schema=schema)
    builder.add({"body": "a rich document about copper kettles"})
    builder.add({"body": "the of and", "blob": "freight"})
    builder.add({"body": "kettle"})
    builder.add({"body": "warm evenings and copper light again"})
    return builder.seal("mixed")


class TestScanning:
    def test_every_live_document_is_graded(self):
        graded = scan_segment(mixed_bag())
        assert [held.grade for held in graded] == [
            "rich",
            "ORPHAN",
            "thin",
            "rich",
        ]

    def test_orphans_name_their_condition(self):
        graded = scan_segment(mixed_bag())
        assert "analyzed to nothing" in graded[1].reason

    def test_thin_documents_hang_by_a_term(self):
        graded = scan_segment(mixed_bag())
        assert graded[2].searchable_terms == 1
        assert "one edit away" in graded[2].reason

    def test_tombstones_are_not_scanned(self):
        segment = mixed_bag()
        segment.delete(1)
        graded = scan_segment(segment)
        assert [held.doc for held in graded] == [0, 2, 3]


class TestReporting:
    def test_the_report_leads_with_the_share(self):
        page = coverage_report(mixed_bag())
        assert page.startswith(
            "mixed: 4 live, 1 orphan(s) (25%), 1 thin"
        )
        assert "pay rent in bytes" in page

    def test_the_share_is_the_alarm_number(self):
        assert orphan_share(mixed_bag()) == 0.25

    def test_an_empty_segment_is_refused(self):
        schema = Schema()
        schema.add_text("body")
        schema.seal()
        builder = SegmentBuilder(schema=schema)
        builder.add({"body": "only one"})
        segment = builder.seal("empty")
        segment.delete(0)
        with pytest.raises(Invalid, match="nothing is nothing"):
            coverage_report(segment)

    def test_a_clean_segment_stays_calm(self):
        schema = Schema()
        schema.add_text("body")
        schema.seal()
        builder = SegmentBuilder(schema=schema)
        builder.add({"body": "copper kettle warm evening light"})
        page = coverage_report(builder.seal("clean"))
        assert "0 orphan(s) (0%)" in page
        assert "pay rent" not in page
