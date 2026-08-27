from __future__ import annotations

import pytest

from quarry.errors import Invalid, Missing
from quarry.exports import export_all, export_batch
from quarry.schema import Schema
from quarry.writer import Index


def archive(count: int = 7) -> Index:
    schema = Schema()
    schema.add_text("body")
    schema.add_keyword("kind")
    schema.seal()
    index = Index(schema=schema)
    for number in range(count):
        index.add({"body": f"note {number}", "kind": "note"})
    index.flush()
    return index


class TestBatches:
    def test_rows_carry_only_the_asked_fields(self):
        page = export_batch(archive(), fields=("body",), batch=3)
        assert page.rows[0].fields == {"body": "note 0"}
        assert "kind" not in page.rows[0].fields

    def test_the_cursor_resumes_where_the_consumer_died(self):
        index = archive()
        first = export_batch(index, fields=("body",), batch=3)
        assert first.cursor == 2
        second = export_batch(
            index, fields=("body",), after=first.cursor, batch=3
        )
        assert [row.external for row in second.rows] == [3, 4, 5]

    def test_the_final_batch_carries_the_manifest(self):
        index = archive(count=2)
        page = export_batch(index, fields=("body",), batch=5)
        assert page.finished()
        assert page.manifest == (
            "export complete: 2 row(s) this batch, ids 0..1"
        )

    def test_a_mid_stream_batch_carries_no_manifest(self):
        page = export_batch(archive(), fields=("body",), batch=3)
        assert not page.finished()
        assert page.manifest is None

    def test_tombstones_never_export(self):
        index = archive()
        index.delete(1)
        rows, _ = export_all(index, fields=("body",))
        assert all(row.external != 1 for row in rows)


class TestContracts:
    def test_unknown_fields_fail_at_the_start(self):
        with pytest.raises(Missing):
            export_batch(archive(), fields=("ghost",))

    def test_no_fields_is_a_count_with_extra_steps(self):
        with pytest.raises(Invalid, match="extra steps"):
            export_batch(archive(), fields=())

    def test_zero_batches_export_forever(self):
        with pytest.raises(Invalid):
            export_batch(archive(), fields=("body",), batch=0)


class TestTheFullDrive:
    def test_export_all_walks_every_batch(self):
        rows, batches = export_all(
            archive(count=7), fields=("body",), batch=3
        )
        assert [row.external for row in rows] == list(range(7))
        assert batches == 3

    def test_an_empty_archive_finishes_honestly(self):
        schema = Schema()
        schema.add_text("body")
        schema.seal()
        index = Index(schema=schema)
        rows, batches = export_all(index, fields=("body",))
        assert rows == []
        assert batches == 1
