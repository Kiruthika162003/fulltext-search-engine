from __future__ import annotations

import pytest

from quarry.duplicates import (
    DuplicateFinder,
    jaccard,
    shingles,
)
from quarry.errors import Invalid
from quarry.tokenize import Analyzer

WIRE_STORY = (
    "the council approved the new bridge budget after a long debate "
    "over funding sources and the construction timeline"
)
SWAPPED_BYLINE = (
    "the council approved the new bridge budget after a long debate "
    "over funding sources and the construction schedule"
)
FRESH_STORY = "a bakery opened downtown selling sourdough and pastries"


class TestShingles:
    def test_windows_overlap_by_one(self):
        made = shingles("the black cat sat down", Analyzer(), width=2)
        assert ("black", "cat") in made
        assert ("cat", "sat") in made

    def test_short_texts_become_one_shingle(self):
        made = shingles("black cat", Analyzer(), width=5)
        assert made == {("black", "cat")}

    def test_empty_text_has_no_shingles(self):
        assert shingles("", Analyzer()) == set()

    def test_width_zero_is_refused(self):
        with pytest.raises(Invalid):
            shingles("text", Analyzer(), width=0)


class TestJaccard:
    def test_identical_sets_overlap_fully(self):
        assert jaccard({1, 2, 3}, {1, 2, 3}) == 1.0

    def test_disjoint_sets_overlap_not_at_all(self):
        assert jaccard({1}, {2}) == 0.0

    def test_two_empties_refuse_to_guess(self):
        with pytest.raises(Invalid, match="refuse to guess"):
            jaccard(set(), set())


class TestVerdicts:
    def loaded(self) -> DuplicateFinder:
        finder = DuplicateFinder()
        finder.admit(0, WIRE_STORY)
        finder.admit(1, SWAPPED_BYLINE)
        finder.admit(2, FRESH_STORY)
        return finder

    def test_the_wire_story_is_caught_wearing_its_new_headline(self):
        pairs = self.loaded().pairs()
        assert len(pairs) == 1
        assert (pairs[0].left, pairs[0].right) == (0, 1)
        assert pairs[0].overlap >= 0.6

    def test_the_fresh_story_stays_fresh(self):
        pairs = self.loaded().pairs()
        assert all(2 not in (p.left, p.right) for p in pairs)

    def test_double_admission_is_refused(self):
        finder = self.loaded()
        with pytest.raises(Invalid):
            finder.admit(0, "again")

    def test_a_paraphrase_survives_the_default_width(self):
        finder = DuplicateFinder()
        finder.admit(0, "the cat chased the dog through the park")
        finder.admit(1, "through the park the dog was chased by a cat")
        assert finder.pairs() == []


class TestClusters:
    def test_transitivity_glues_the_chain(self):
        finder = DuplicateFinder(line=0.5)
        finder.admit(0, "pine quartz river stone tower umber")
        finder.admit(1, "quartz river stone tower umber violet")
        finder.admit(2, "river stone tower umber violet walnut")
        pairs = {(p.left, p.right) for p in finder.pairs()}
        assert pairs == {(0, 1), (1, 2)}
        assert finder.clusters()[0] == [0, 1, 2]

    def test_the_representative_is_the_first_seen(self):
        finder = DuplicateFinder()
        finder.admit(0, WIRE_STORY)
        finder.admit(1, SWAPPED_BYLINE)
        finder.admit(2, FRESH_STORY)
        assert finder.representatives() == [0, 2]

    def test_the_report_names_who_speaks_for_whom(self):
        finder = DuplicateFinder()
        finder.admit(0, WIRE_STORY)
        finder.admit(1, SWAPPED_BYLINE)
        finder.admit(2, FRESH_STORY)
        report = finder.collapse_report()
        assert "3 documents, 2 stories, 1 hidden as variants" in report
        assert "doc 0 speaks for 1" in report
