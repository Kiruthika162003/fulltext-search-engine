from __future__ import annotations

import json

import pytest

from quarry.errors import Invalid, Stale
from quarry.multisearch import search_index
from quarry.persist import dump, load
from quarry.query import parse
from quarry.schema import Schema
from quarry.writer import Index


def article_schema() -> Schema:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    return schema


def stocked() -> Index:
    index = Index(schema=article_schema(), flush_at=2)
    index.add({"body": "the black cat sat"})
    index.add({"body": "a black dog ran"})
    index.add({"body": "cats everywhere"})
    index.flush()
    index.delete(1)
    return index


class TestRoundTrip:
    def test_the_trip_survives_json(self):
        index = stocked()
        payload = json.loads(json.dumps(dump(index)))
        loaded = load(payload, article_schema())
        assert loaded.searchable_count() == index.searchable_count()

    def test_search_answers_the_same_after_the_trip(self):
        index = stocked()
        loaded = load(dump(index), article_schema())
        query = parse("black cat")
        before = [
            (hit.external, hit.score)
            for hit in search_index(index, query).hits
        ]
        after = [
            (hit.external, hit.score)
            for hit in search_index(loaded, query).hits
        ]
        assert before == after

    def test_tombstones_survive_the_trip(self):
        loaded = load(dump(stocked()), article_schema())
        page = search_index(loaded, parse("dog"))
        assert page.hits == ()

    def test_new_writes_continue_after_the_trip(self):
        loaded = load(dump(stocked()), article_schema())
        external = loaded.add({"body": "a new arrival"})
        assert external == 3
        loaded.flush()
        assert loaded.searchable_count() == 3


class TestTheAudit:
    def test_a_different_schema_is_refused(self):
        other = Schema()
        other.add_text("title")
        other.seal()
        with pytest.raises(Invalid, match="different schema"):
            load(dump(stocked()), other)

    def test_a_future_format_is_refused(self):
        payload = dump(stocked())
        payload["format"] = 99
        with pytest.raises(Stale, match="migrate"):
            load(payload, article_schema())

    def test_a_dangling_location_is_named(self):
        payload = dump(stocked())
        payload["locations"]["0"] = ["ghost", 0]
        with pytest.raises(Invalid, match="does not exist"):
            load(payload, article_schema())

    def test_an_out_of_range_location_is_named(self):
        payload = dump(stocked())
        payload["locations"]["0"] = ["seg0", 99]
        with pytest.raises(Invalid, match="outside"):
            load(payload, article_schema())

    def test_a_phantom_tombstone_is_named(self):
        payload = dump(stocked())
        payload["segments"][0]["tombstones"] = [42]
        with pytest.raises(Invalid, match="never existed"):
            load(payload, article_schema())

    def test_hand_edited_postings_lose_the_audit(self):
        payload = dump(stocked())
        rows = payload["segments"][0]["postings"][0]["rows"]
        rows.append([rows[0][0], [0]])
        with pytest.raises(Invalid):
            load(payload, article_schema())
