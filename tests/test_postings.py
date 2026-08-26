from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.postings import (
    Posting,
    PostingList,
    difference,
    intersect,
    phrase_docs,
    union,
)


def listing(term: str, rows: list[tuple[int, tuple[int, ...]]]) -> PostingList:
    held = PostingList(term=term)
    for doc, positions in rows:
        held.add(doc, positions)
    return held


class TestPostings:
    def test_a_positionless_posting_is_a_contradiction(self):
        with pytest.raises(Invalid, match="appears nowhere"):
            Posting(doc=1, positions=())

    def test_positions_must_climb(self):
        with pytest.raises(Invalid, match="strictly increasing"):
            Posting(doc=1, positions=(3, 3))

    def test_frequency_is_the_position_count(self):
        assert Posting(doc=1, positions=(0, 4, 9)).frequency == 3

    def test_docs_arrive_in_order_or_not_at_all(self):
        held = listing("cat", [(1, (0,)), (5, (2,))])
        with pytest.raises(Invalid, match="out of order"):
            held.add(3, (1,))

    def test_find_is_a_binary_search(self):
        held = listing("cat", [(1, (0,)), (5, (2,)), (9, (7,))])
        assert held.find(5).positions == (2,)
        assert held.find(4) is None
        assert held.find(10) is None


class TestTheAlgebra:
    def test_and_is_a_zipper(self):
        assert intersect([1, 3, 5, 7], [2, 3, 7, 9]) == [3, 7]

    def test_or_merges_without_duplicates(self):
        assert union([1, 3, 5], [3, 4, 5, 8]) == [1, 3, 4, 5, 8]

    def test_not_subtracts_from_the_universe(self):
        assert difference([1, 2, 3, 4, 5], [2, 4]) == [1, 3, 5]

    def test_empty_sides_behave(self):
        assert intersect([], [1, 2]) == []
        assert union([], [1, 2]) == [1, 2]
        assert difference([1, 2], []) == [1, 2]


class TestPhrases:
    def phrase_lists(self) -> list[PostingList]:
        black = listing("black", [(1, (0, 9)), (2, (4,)), (3, (2,))])
        cat = listing("cat", [(1, (1,)), (2, (7,)), (3, (3, 8))])
        return [black, cat]

    def test_the_shift_trick_finds_adjacency(self):
        assert phrase_docs(self.phrase_lists()) == [1, 3]

    def test_both_words_present_is_not_enough(self):
        assert 2 not in phrase_docs(self.phrase_lists())

    def test_a_three_word_phrase_aligns_all_three(self):
        big = listing("big", [(1, (0,))])
        black = listing("black", [(1, (1, 5))])
        cat = listing("cat", [(1, (2,))])
        assert phrase_docs([big, black, cat]) == [1]

    def test_an_empty_phrase_is_refused(self):
        with pytest.raises(Invalid):
            phrase_docs([])
