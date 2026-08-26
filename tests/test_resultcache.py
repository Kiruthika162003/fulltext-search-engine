from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.resultcache import ResultCache


def warmed() -> ResultCache:
    cache = ResultCache(capacity=3)
    cache.put("body:cat", 10, None, hits=(1, 2), token=None)
    return cache


class TestServing:
    def test_a_warm_slot_serves(self):
        cache = warmed()
        held = cache.get("body:cat", 10, None)
        assert held is not None
        assert held.hits == (1, 2)
        assert cache.hit_ratio() == 1.0

    def test_a_cold_slot_misses(self):
        cache = warmed()
        assert cache.get("body:dog", 10, None) is None
        assert cache.hit_ratio() == 0.0

    def test_page_bounds_are_part_of_the_key(self):
        cache = warmed()
        assert cache.get("body:cat", 5, None) is None
        assert cache.get("body:cat", 10, (1.5, 2)) is None

    def test_no_lookups_refuses_the_ratio(self):
        with pytest.raises(Invalid, match="shrug"):
            ResultCache().hit_ratio()


class TestInvalidation:
    def test_an_index_change_kills_the_generation(self):
        cache = warmed()
        killed = cache.index_changed()
        assert killed == 1
        assert cache.get("body:cat", 10, None) is None

    def test_new_entries_live_in_the_new_generation(self):
        cache = warmed()
        cache.index_changed()
        cache.put("body:cat", 10, None, hits=(9,), token=None)
        held = cache.get("body:cat", 10, None)
        assert held.hits == (9,)

    def test_the_funeral_count_is_public(self):
        cache = warmed()
        cache.index_changed()
        cache.get("body:cat", 10, None)
        assert cache.killed_by_invalidation >= 1
        assert "killed by index changes" in cache.obituary()


class TestEviction:
    def test_the_oldest_slot_leaves_first(self):
        cache = ResultCache(capacity=2)
        cache.put("a", 10, None, hits=(), token=None)
        cache.put("b", 10, None, hits=(), token=None)
        cache.put("c", 10, None, hits=(), token=None)
        assert cache.get("a", 10, None) is None
        assert cache.get("b", 10, None) is not None

    def test_a_hit_refreshes_recency(self):
        cache = ResultCache(capacity=2)
        cache.put("a", 10, None, hits=(), token=None)
        cache.put("b", 10, None, hits=(), token=None)
        cache.get("a", 10, None)
        cache.put("c", 10, None, hits=(), token=None)
        assert cache.get("a", 10, None) is not None
        assert cache.get("b", 10, None) is None

    def test_a_slotless_cache_is_refused(self):
        with pytest.raises(Invalid, match="regret"):
            ResultCache(capacity=0)
