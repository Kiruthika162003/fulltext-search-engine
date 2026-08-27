from __future__ import annotations

from quarry.engine import Engine
from quarry.schema import Schema
from quarry.service import SearchService


def service() -> SearchService:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    engine = Engine(schema=schema)
    engine.add({"body": "the black cat"})
    engine.commit()
    return SearchService(engine=engine, node_name="node-7")


class TestTheHappyPath:
    def test_search_answers_in_the_envelope(self):
        reply = service().handle(
            {"operation": "search", "query": "cat"}
        )
        assert reply["status"] == 200
        assert reply["served_by"] == "node-7"
        assert reply["hits"][0]["id"] == 0

    def test_add_commit_search_round_trip(self):
        held = service()
        added = held.handle(
            {"operation": "add", "document": {"body": "a new cat"}}
        )
        assert added["status"] == 201
        held.handle({"operation": "commit"})
        found = held.handle({"operation": "search", "query": "cat"})
        assert len(found["hits"]) == 2

    def test_delete_echoes_the_outcome(self):
        held = service()
        reply = held.handle({"operation": "delete", "id": 0})
        assert reply["status"] == 200
        assert "tombstoned" in reply["outcome"]


class TestTheTaxonomy:
    def test_a_refusal_becomes_400_verbatim(self):
        reply = service().handle(
            {"operation": "search", "query": "   "}
        )
        assert reply["status"] == 400
        assert "refused" in reply["error"]

    def test_a_missing_thing_becomes_404_with_its_name(self):
        reply = service().handle({"operation": "delete", "id": 99})
        assert reply["status"] == 404
        assert "99" in reply["error"]

    def test_unknown_operations_list_the_choices(self):
        reply = service().handle({"operation": "explode"})
        assert reply["status"] == 400
        assert "the choices are" in reply["error"]

    def test_a_nameless_request_is_refused(self):
        reply = service().handle({})
        assert reply["status"] == 400
        assert "names its operation" in reply["error"]

    def test_an_add_without_a_document_is_400(self):
        reply = service().handle({"operation": "add"})
        assert reply["status"] == 400


class TestTheTrafficNote:
    def test_the_note_counts_served_and_failures(self):
        held = service()
        held.handle({"operation": "search", "query": "cat"})
        held.handle({"operation": "delete", "id": 99})
        note = held.traffic_note()
        assert note.startswith("2 request(s) served by node-7")
        assert "404: 1" in note
