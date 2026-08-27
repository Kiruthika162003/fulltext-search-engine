from __future__ import annotations

import pytest

from quarry.compounds import CompoundSplitter, Split, splitter_report
from quarry.errors import Invalid

VOCAB = frozenset(
    {
        "book",
        "shelf",
        "steam",
        "ship",
        "motor",
        "way",
        "car",
        "pet",
        "carpet",
        "fire",
        "place",
    }
)


def splitter() -> CompoundSplitter:
    return CompoundSplitter(vocabulary=VOCAB)


class TestSplitting:
    def test_a_welded_word_splits_into_its_halves(self):
        assert splitter().split("bookshelf").parts == ("book", "shelf")
        assert splitter().split("steamship").parts == ("steam", "ship")

    def test_a_known_whole_word_is_never_split(self):
        assert splitter().split("carpet").parts == ("carpet",)

    def test_an_unsplittable_word_is_kept_whole(self):
        assert splitter().split("zeppelin").parts == ("zeppelin",)

    def test_case_and_padding_are_normalized(self):
        assert splitter().split("  BookShelf ").parts == (
            "book",
            "shelf",
        )

    def test_emptiness_has_no_parts(self):
        with pytest.raises(Invalid, match="no parts"):
            splitter().split("   ")

    def test_three_part_welds_still_resolve(self):
        assert splitter().split("fireplaceway").parts == (
            "fire",
            "place",
            "way",
        )


class TestTheVocabularyDoor:
    def test_short_vocabulary_words_are_refused(self):
        with pytest.raises(Invalid, match="confetti"):
            CompoundSplitter(vocabulary=frozenset({"ox", "book"}))

    def test_the_refusal_names_the_offenders(self):
        with pytest.raises(Invalid, match="an, ox"):
            CompoundSplitter(
                vocabulary=frozenset({"ox", "an", "book"})
            )


class TestIndexAndQuerySides:
    def test_index_terms_keep_the_whole_word_first(self):
        assert splitter().index_terms("bookshelf") == [
            "bookshelf",
            "book",
            "shelf",
        ]

    def test_unsplit_words_index_alone(self):
        assert splitter().index_terms("zeppelin") == ["zeppelin"]

    def test_the_query_side_stays_whole(self):
        assert splitter().expand_query_term("Bookshelf") == [
            "bookshelf"
        ]


class TestTheReport:
    def test_the_report_counts_and_explains(self):
        report = splitter_report(
            splitter(), ["bookshelf", "carpet", "zeppelin"]
        )
        assert "bookshelf: split as book + shelf" in report
        assert "carpet: kept whole" in report
        assert "outcome: 1 of 3 words split" in report

    def test_explain_reads_as_a_sentence(self):
        held = Split(word="motorway", parts=("motor", "way"))
        assert held.explain() == "motorway: split as motor + way"
