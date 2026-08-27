from __future__ import annotations

from quarry.invariants import audit_index, audit_report
from quarry.merge import maintain
from quarry.schema import Schema
from quarry.writer import Index


def healthy() -> Index:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    index = Index(schema=schema, flush_at=2)
    for number in range(6):
        index.add({"body": f"cat document {number}"})
    index.flush()
    index.delete(1)
    return index


class TestTheCleanBill:
    def test_a_healthy_index_keeps_its_promises(self):
        assert audit_index(healthy()) == []
        report = audit_report(healthy())
        assert report.endswith("the index keeps its promises")
        assert report.startswith("8 invariants verified")

    def test_the_audit_survives_merges(self):
        index = healthy()
        maintain(index)
        assert audit_index(index) == []

    def test_the_audit_is_read_only(self):
        index = healthy()
        before = index.searchable_count()
        audit_index(index)
        assert index.searchable_count() == before


class TestCaughtCorruption:
    def test_a_phantom_tombstone_is_caught_with_its_numbers(self):
        index = healthy()
        index.segments[0].tombstones.add(42)
        violations = audit_index(index)
        assert any(
            v.invariant == "tombstones-name-the-dead"
            and "42" in v.detail
            for v in violations
        )

    def test_a_shared_address_is_caught_by_both_ids(self):
        index = healthy()
        index.locations[5] = index.locations[0]
        violations = audit_index(index)
        assert any(
            v.invariant == "locations-bijective" for v in violations
        )

    def test_a_dangling_location_is_caught(self):
        index = healthy()
        index.locations[0] = ("ghost-segment", 0)
        violations = audit_index(index)
        assert any(
            v.invariant == "locations-resolve"
            and "ghost-segment" in v.detail
            for v in violations
        )

    def test_a_lagging_id_counter_is_caught(self):
        index = healthy()
        index.next_id = 2
        violations = audit_index(index)
        assert any(
            v.invariant == "id-counter-ahead"
            and "will reissue" in v.detail
            for v in violations
        )

    def test_shortened_lengths_are_caught(self):
        index = healthy()
        index.segments[0].lengths["body"].pop()
        violations = audit_index(index)
        assert any(
            v.invariant == "lengths-cover-documents"
            for v in violations
        )

    def test_the_report_names_each_finding(self):
        index = healthy()
        index.segments[0].tombstones.add(42)
        report = audit_report(index)
        assert report.startswith("1 violation(s) across 8 checks:")
        assert "[tombstones-name-the-dead]" in report
