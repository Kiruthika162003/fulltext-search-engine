from __future__ import annotations

import pytest

from quarry.errors import Invalid, Missing
from quarry.morelikethis import more_like_this
from quarry.schema import Schema
from quarry.writer import Index


def shelf() -> Index:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    index = Index(schema=schema)
    index.add(
        {"body": "quantum computing with trapped ions and lasers"}
    )
    index.add(
        {"body": "quantum computing with superconducting qubits"}
    )
    index.add({"body": "classical computing on silicon chips"})
    index.add({"body": "a cookbook of hearty winter soups"})
    index.add({"body": "the sku99871 unit ships with lasers"})
    index.flush()
    return index


class TestTheDiet:
    def test_the_query_keeps_the_rare_and_drops_the_common(self):
        likeness = more_like_this(shelf(), 0, "body", top_terms=3)
        assert "quantum" in likeness.query_terms
        assert "with" not in likeness.query_terms

    def test_fingerprints_are_dropped_and_reported(self):
        likeness = more_like_this(shelf(), 4, "body")
        assert "sku99871" in likeness.fingerprints_dropped

    def test_the_seed_never_answers_itself(self):
        likeness = more_like_this(shelf(), 0, "body")
        assert all(hit.external != 0 for hit in likeness.similars)

    def test_the_nearest_neighbour_is_the_right_one(self):
        likeness = more_like_this(shelf(), 0, "body")
        assert likeness.similars[0].external == 1

    def test_the_cookbook_is_nobody_in_this_conversation(self):
        likeness = more_like_this(shelf(), 0, "body")
        assert all(hit.external != 3 for hit in likeness.similars)


class TestRefusals:
    def test_ghost_seeds_are_named(self):
        with pytest.raises(Missing):
            more_like_this(shelf(), 99, "body")

    def test_an_all_fingerprint_document_is_only_like_itself(self):
        schema = Schema()
        schema.add_text("body")
        schema.seal()
        index = Index(schema=schema)
        index.add({"body": "zzq88 yyx77"})
        index.add({"body": "completely different words"})
        index.flush()
        with pytest.raises(Invalid, match="only like itself"):
            more_like_this(index, 0, "body")

    def test_zero_knobs_are_refused(self):
        with pytest.raises(Invalid):
            more_like_this(shelf(), 0, "body", top_terms=0)
        with pytest.raises(Invalid):
            more_like_this(shelf(), 0, "body", limit=0)
