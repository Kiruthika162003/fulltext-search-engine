from __future__ import annotations

import pytest

from quarry.errors import Invalid, Missing
from quarry.schema import Schema
from quarry.writer import Index


def opened(flush_at: int = 3) -> Index:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    return Index(schema=schema, flush_at=flush_at)


class TestBuffering:
    def test_adds_buffer_until_the_flush_line(self):
        index = opened(flush_at=3)
        index.add({"body": "one"})
        index.add({"body": "two"})
        assert index.segments == []
        assert index.doc_count() == 2

    def test_the_flush_line_seals_a_segment(self):
        index = opened(flush_at=2)
        index.add({"body": "one"})
        index.add({"body": "two"})
        assert len(index.segments) == 1
        assert index.searchable_count() == 2

    def test_manual_flush_works_between_lines(self):
        index = opened(flush_at=100)
        index.add({"body": "one"})
        segment = index.flush()
        assert segment is not None
        assert index.searchable_count() == 1

    def test_flushing_nothing_is_a_quiet_no(self):
        assert opened().flush() is None

    def test_an_unsealed_schema_is_refused(self):
        with pytest.raises(Invalid):
            Index(schema=Schema())


class TestIdentity:
    def test_external_ids_are_stable_across_flushes(self):
        index = opened(flush_at=2)
        first = index.add({"body": "one"})
        second = index.add({"body": "two"})
        third = index.add({"body": "three"})
        assert (first, second, third) == (0, 1, 2)
        assert index.document(0) == {"body": "one"}
        assert index.document(2) == {"body": "three"}

    def test_addresses_resolve_back_to_ids(self):
        index = opened(flush_at=2)
        index.add({"body": "one"})
        index.add({"body": "two"})
        assert index.external_id("seg0", 1) == 1

    def test_unknown_ids_are_named(self):
        with pytest.raises(Missing):
            opened().document(99)


class TestDeletes:
    def test_a_flushed_delete_plants_a_tombstone(self):
        index = opened(flush_at=2)
        index.add({"body": "one"})
        index.add({"body": "two"})
        outcome = index.delete(0)
        assert outcome == "tombstoned in seg0"
        assert index.searchable_count() == 1
        with pytest.raises(Missing):
            index.document(0)

    def test_a_buffered_delete_never_becomes_real(self):
        index = opened(flush_at=100)
        index.add({"body": "one"})
        outcome = index.delete(0)
        assert outcome == "removed before it ever became real"
        index.flush()
        assert index.searchable_count() == 0

    def test_deleting_the_unknown_is_named(self):
        with pytest.raises(Missing):
            opened().delete(7)


class TestShape:
    def test_the_shape_reads_per_segment(self):
        index = opened(flush_at=2)
        for number in range(5):
            index.add({"body": f"doc {number}"})
        index.delete(0)
        assert index.shape().splitlines() == [
            "seg0: 1/2 live",
            "seg1: 2/2 live",
            "buffer: 1 pending",
        ]
