from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.topk import TopK, merge


class TestAccumulation:
    def test_memory_stays_bounded_at_k(self):
        held = TopK(k=3)
        for doc in range(1000):
            held.offer(doc, float(doc % 97))
        assert len(held.heap) == 3
        assert held.offered == 1000

    def test_the_best_k_survive(self):
        held = TopK(k=3)
        for doc, score in enumerate([5.0, 9.0, 1.0, 7.0, 3.0]):
            held.offer(doc, score)
        assert held.ranked() == [(1, 9.0), (3, 7.0), (0, 5.0)]

    def test_the_floor_is_the_next_to_die(self):
        held = TopK(k=2)
        held.offer(0, 5.0)
        assert held.floor() is None
        held.offer(1, 9.0)
        assert held.floor() == (0, 5.0)

    def test_keeping_zero_keeps_nothing(self):
        with pytest.raises(Invalid, match="keeps nothing"):
            TopK(k=0)


class TestTies:
    def test_tied_scores_rank_by_ascending_id(self):
        held = TopK(k=3)
        for doc in (9, 2, 5):
            held.offer(doc, 4.0)
        assert held.ranked() == [(2, 4.0), (5, 4.0), (9, 4.0)]

    def test_eviction_agrees_with_the_output_order(self):
        held = TopK(k=2)
        held.offer(9, 4.0)
        held.offer(2, 4.0)
        assert held.offer(5, 4.0)
        assert held.ranked() == [(2, 4.0), (5, 4.0)]

    def test_a_tie_with_a_larger_id_bounces(self):
        held = TopK(k=2)
        held.offer(2, 4.0)
        held.offer(5, 4.0)
        assert not held.offer(9, 4.0)


class TestMerging:
    def test_the_merge_equals_the_single_scan(self):
        single = TopK(k=4)
        left = TopK(k=4)
        right = TopK(k=4)
        scores = [(doc, float((doc * 7) % 23)) for doc in range(40)]
        for doc, score in scores:
            single.offer(doc, score)
            (left if doc % 2 == 0 else right).offer(doc, score)
        assert merge([left, right]).ranked() == single.ranked()

    def test_mismatched_widths_answer_different_questions(self):
        with pytest.raises(Invalid, match="different questions"):
            merge([TopK(k=3), TopK(k=5)])

    def test_offered_counts_survive_the_merge(self):
        left = TopK(k=2)
        right = TopK(k=2)
        left.offer(1, 1.0)
        right.offer(2, 2.0)
        right.offer(3, 3.0)
        assert merge([left, right]).offered == 3

    def test_merging_nothing_keeps_nothing(self):
        with pytest.raises(Invalid, match="keeps nothing"):
            merge([])
