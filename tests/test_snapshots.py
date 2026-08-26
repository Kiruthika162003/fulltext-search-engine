from __future__ import annotations

import pytest

from quarry.errors import Invalid, Missing
from quarry.multisearch import search_index
from quarry.query import parse
from quarry.schema import Schema
from quarry.snapshots import SnapshotCatalogue
from quarry.writer import Index


def sealed() -> Schema:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    return schema


def world() -> tuple[Index, SnapshotCatalogue]:
    schema = sealed()
    index = Index(schema=schema, flush_at=2)
    catalogue = SnapshotCatalogue(schema=schema)
    for number in range(4):
        index.add({"body": f"cat chapter {number}"})
    return index, catalogue


class TestTaking:
    def test_a_full_snapshot_carries_everything(self):
        index, catalogue = world()
        manifest = catalogue.take("nightly-1", index)
        assert manifest.carried_segments == manifest.segment_names
        assert manifest.doc_count == 4

    def test_an_increment_ships_only_the_new(self):
        index, catalogue = world()
        catalogue.take("nightly-1", index)
        for number in range(4, 6):
            index.add({"body": f"cat chapter {number}"})
        manifest = catalogue.take("nightly-2", index, base="nightly-1")
        assert len(manifest.carried_segments) == 1
        assert catalogue.shipping_saved("nightly-2") == 2

    def test_duplicate_names_and_ghost_bases_are_refused(self):
        index, catalogue = world()
        catalogue.take("nightly-1", index)
        with pytest.raises(Invalid):
            catalogue.take("nightly-1", index)
        with pytest.raises(Missing):
            catalogue.take("nightly-2", index, base="ghost")


class TestRestoring:
    def test_the_restore_walks_the_chain(self):
        index, catalogue = world()
        catalogue.take("nightly-1", index)
        for number in range(4, 6):
            index.add({"body": f"cat chapter {number}"})
        catalogue.take("nightly-2", index, base="nightly-1")
        restored = catalogue.restore("nightly-2")
        assert restored.searchable_count() == 6
        hits = search_index(restored, parse("cat"), limit=10).hits
        assert len(hits) == 6

    def test_a_restore_is_a_point_in_time(self):
        index, catalogue = world()
        catalogue.take("nightly-1", index)
        index.add({"body": "cat chapter late"})
        index.flush()
        restored = catalogue.restore("nightly-1")
        assert restored.searchable_count() == 4

    def test_tombstones_freeze_with_the_snapshot(self):
        index, catalogue = world()
        index.flush()
        index.delete(0)
        catalogue.take("after-delete", index)
        restored = catalogue.restore("after-delete")
        assert restored.searchable_count() == 3

    def test_a_broken_chain_names_the_lost_link(self):
        index, catalogue = world()
        catalogue.take("nightly-1", index)
        for number in range(4, 6):
            index.add({"body": f"cat chapter {number}"})
        catalogue.take("nightly-2", index, base="nightly-1")
        del catalogue.manifests["nightly-1"]
        with pytest.raises(Missing, match="nightly-1 is gone"):
            catalogue.restore("nightly-2")


class TestTheDrill:
    def test_the_drill_passes_and_says_so(self):
        index, catalogue = world()
        catalogue.take("nightly-1", index)
        report = catalogue.drill("nightly-1")
        assert report == (
            "drill passed: nightly-1 restored 4 document(s) through a "
            "chain of 1"
        )
        assert catalogue.restores_drilled == 1

    def test_the_drill_catches_a_lying_manifest(self):
        index, catalogue = world()
        manifest = catalogue.take("nightly-1", index)
        catalogue.manifests["nightly-1"] = type(manifest)(
            name=manifest.name,
            base=manifest.base,
            segment_names=manifest.segment_names,
            carried_segments=manifest.carried_segments,
            doc_count=99,
        )
        assert catalogue.drill("nightly-1").startswith("DRILL FAILED")
