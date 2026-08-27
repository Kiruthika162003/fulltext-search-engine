from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.rerankhook import WINDOW, RerankSeam

RANKED = [(doc, 10.0 - doc) for doc in range(12)]


class TestReordering:
    def test_the_hook_reorders_inside_the_window(self):
        seam = RerankSeam(hook=lambda window: {9: 1.5})
        out = seam.rerank(RANKED)
        assert out[0].external == 0
        boosted = next(h for h in out if h.external == 9)
        assert boosted.final_score() == 2.5
        assert out.index(boosted) < 9

    def test_below_the_window_nothing_moves(self):
        seam = RerankSeam(hook=lambda window: {0: -2.0})
        out = seam.rerank(RANKED)
        assert [h.external for h in out[WINDOW:]] == [10, 11]
        assert all(h.adjustment == 0.0 for h in out[WINDOW:])

    def test_an_empty_page_is_refused(self):
        with pytest.raises(Invalid, match="reranks nothing"):
            RerankSeam(hook=lambda window: {}).rerank([])


class TestBounds:
    def test_huge_adjustments_are_clipped_and_counted(self):
        seam = RerankSeam(hook=lambda window: {5: 1000.0})
        out = seam.rerank(RANKED)
        adjusted = next(h for h in out if h.external == 5)
        assert adjusted.adjustment == 2.0
        assert seam.clips == 1
        assert "1 adjustment(s) clipped" in seam.status()

    def test_adjusting_outside_the_window_blows_the_fuse(self):
        seam = RerankSeam(hook=lambda window: {11: 1.0})
        out = seam.rerank(RANKED)
        assert seam.fused
        assert "outside its window" in seam.fuse_reason
        assert [h.external for h in out] == list(range(12))


class TestTheFuse:
    def test_a_crashing_hook_degrades_to_lexical(self):
        def dies(window):
            raise RuntimeError("model server gone")

        seam = RerankSeam(hook=dies)
        out = seam.rerank(RANKED)
        assert [h.external for h in out] == list(range(12))
        assert seam.fused
        assert "model server gone" in seam.fuse_reason

    def test_a_fused_seam_stops_calling_the_hook(self):
        calls = []

        def counting(window):
            calls.append(1)
            raise RuntimeError("still broken")

        seam = RerankSeam(hook=counting)
        seam.rerank(RANKED)
        seam.rerank(RANKED)
        assert len(calls) == 1
        assert seam.status().startswith("FUSED after 1 call(s)")

    def test_a_healthy_seam_reports_live(self):
        seam = RerankSeam(hook=lambda window: {})
        seam.rerank(RANKED)
        assert seam.status().startswith("live: 1 call(s)")
