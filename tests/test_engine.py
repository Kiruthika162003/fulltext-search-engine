from __future__ import annotations

from quarry.engine import Engine
from quarry.schema import Schema


def built() -> Engine:
    schema = Schema()
    schema.add_text("title")
    schema.add_text("body")
    schema.seal()
    engine = Engine(schema=schema)
    engine.add(
        {
            "title": "The Black Cat",
            "body": "a story about a black cat and a cellar",
        }
    )
    engine.add(
        {
            "title": "Dogs of War",
            "body": "loyal dogs marching through history",
        }
    )
    engine.add(
        {
            "title": "Feline Care",
            "body": "keeping cats healthy and happy at home",
        }
    )
    engine.commit()
    return engine


class TestTheFrontDoor:
    def test_a_search_returns_rendered_hits(self):
        response = built().search("body:cat")
        assert {hit.external for hit in response.hits} == {0, 2}
        assert response.canonical == "body:cat"

    def test_snippets_ride_along_when_asked(self):
        response = built().search(
            "body:cat", snippet_fields=("body",)
        )
        top = response.hits[0]
        field_name, text = top.snippets[0]
        assert field_name == "body"
        assert "[cat" in text or "[Cat" in text

    def test_deletes_take_effect_at_commit(self):
        engine = built()
        engine.delete(0)
        response = engine.search("body:cat")
        assert {hit.external for hit in response.hits} == {2}

    def test_the_daybook_counts_the_day(self):
        engine = built()
        engine.search("body:cat")
        engine.search("body:dog")
        book = engine.daybook()
        assert book.startswith("2 queries served")
        assert "3 documents searchable" in book


class TestSuggestions:
    def test_a_typo_with_no_results_earns_a_correction(self):
        response = built().search("body:catz")
        assert response.hits == ()
        assert response.suggestion == "body:cat"

    def test_good_results_silence_the_doubt(self):
        engine = built()
        for number in range(4):
            engine.add({"title": f"extra {number}", "body": "cat cat cat"})
        engine.commit()
        response = engine.search("body:cat")
        assert response.suggestion is None

    def test_gibberish_earns_silence(self):
        response = built().search("body:qqqqqq")
        assert response.suggestion is None
