from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.synonyms import (
    SynonymRings,
    WeightedTerm,
    expand_terms,
    expansion_report,
)


def furniture() -> SynonymRings:
    rings = SynonymRings()
    rings.declare("sofa", "couch", "settee")
    rings.declare("lamp", "light")
    return rings


class TestRings:
    def test_a_ring_shares_its_members(self):
        rings = furniture()
        assert set(rings.expansions("sofa")) == {"couch", "settee"}
        assert rings.expansions("couch") == ("sofa", "settee")

    def test_words_outside_every_ring_expand_to_nothing(self):
        assert furniture().expansions("table") == ()

    def test_a_ring_of_one_is_refused(self):
        with pytest.raises(Invalid, match="talking to itself"):
            SynonymRings().declare("alone")

    def test_a_word_in_two_rings_is_refused(self):
        rings = furniture()
        with pytest.raises(Invalid, match="glues unrelated meanings"):
            rings.declare("couch", "recliner")

    def test_multi_word_entries_are_refused(self):
        with pytest.raises(Invalid, match="single terms"):
            SynonymRings().declare("sofa bed", "couch")

    def test_words_that_collapse_after_analysis_are_refused(self):
        with pytest.raises(Invalid, match="already contains itself"):
            SynonymRings().declare("cat", "cats")

    def test_rings_are_counted(self):
        assert furniture().ring_count() == 2


class TestExpansion:
    def test_typed_words_keep_full_weight(self):
        rows = expand_terms(furniture(), ["sofa"])
        assert rows[0] == WeightedTerm(term="sofa", weight=1.0, source="typed")

    def test_grown_words_carry_the_discount_and_their_source(self):
        rows = expand_terms(furniture(), ["sofa"])
        grown = {row.term: row for row in rows[1:]}
        assert grown["couch"].weight == 0.6
        assert grown["couch"].source == "ring of sofa"

    def test_a_typed_synonym_is_never_discounted(self):
        rows = expand_terms(furniture(), ["sofa", "couch"])
        weights = {row.term: row.weight for row in rows}
        assert weights["sofa"] == 1.0
        assert weights["couch"] == 1.0
        assert weights["settee"] == 0.6

    def test_an_absurd_discount_is_refused(self):
        with pytest.raises(Invalid, match="fraction"):
            expand_terms(furniture(), ["sofa"], discount=1.5)

    def test_the_report_reads_typed_then_grown(self):
        report = expansion_report(expand_terms(furniture(), ["sofa"]))
        lines = report.splitlines()
        assert lines[0] == "typed: sofa"
        assert "  + couch at 0.6 (ring of sofa)" in lines

    def test_no_expansion_says_so(self):
        report = expansion_report(expand_terms(furniture(), ["table"]))
        assert report.splitlines()[1] == "  no expansions"
