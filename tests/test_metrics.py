from __future__ import annotations

import pytest

from quarry.errors import Invalid, Missing
from quarry.metrics import Registry, engine_registry


class TestRegistration:
    def test_units_are_mandatory(self):
        with pytest.raises(Invalid, match="no exceptions"):
            Registry().counter("queries", unit="")

    def test_double_registration_is_refused(self):
        registry = Registry()
        registry.counter("q", unit="queries")
        with pytest.raises(Invalid):
            registry.gauge("q", unit="queries")

    def test_typos_do_not_mint_metrics(self):
        registry = Registry()
        registry.counter("queries_served", unit="queries")
        with pytest.raises(Missing, match="splits the graph"):
            registry.increment("querys_served")


class TestKinds:
    def test_counters_only_go_up(self):
        registry = Registry()
        registry.counter("q", unit="queries")
        registry.increment("q", by=3)
        assert registry.read("q") == 3
        with pytest.raises(Invalid, match="wrong hat"):
            registry.increment("q", by=-1)

    def test_gauges_go_anywhere(self):
        registry = Registry()
        registry.gauge("depth", unit="documents")
        registry.set_gauge("depth", 10)
        registry.set_gauge("depth", 4)
        assert registry.read("depth") == 4

    def test_kinds_refuse_each_others_verbs(self):
        registry = Registry()
        registry.counter("c", unit="x")
        registry.gauge("g", unit="x")
        with pytest.raises(Invalid):
            registry.set_gauge("c", 5)
        with pytest.raises(Invalid):
            registry.increment("g")


class TestScrapes:
    def test_the_scrape_is_sorted_and_united(self):
        registry = Registry()
        registry.counter("beta", unit="items")
        registry.counter("alpha", unit="items")
        registry.increment("beta")
        lines = registry.scrape().splitlines()
        assert lines[0] == "alpha 0.0 items (counter)"
        assert lines[1] == "beta 1.0 items (counter)"

    def test_the_delta_answers_what_moved(self):
        registry = Registry()
        registry.counter("q", unit="queries")
        before = registry.snapshot()
        registry.increment("q", by=5)
        registry.counter("late", unit="items")
        moved = registry.delta(before)
        assert "q: 0.0 -> 5.0 (+5 queries)" in moved
        assert "late: new since the snapshot" in moved

    def test_nothing_moved_reads_empty(self):
        registry = Registry()
        registry.counter("q", unit="queries")
        assert registry.delta(registry.snapshot()) == []


class TestTheRoster:
    def test_the_standard_roster_covers_the_vital_signs(self):
        registry = engine_registry()
        assert registry.read("queries_served") == 0
        registry.increment("cache_hits")
        registry.set_gauge("tombstone_share", 0.12)
        scrape = registry.scrape()
        assert "tombstone_share 0.12 fraction (gauge)" in scrape
        assert "cache_hits 1.0 lookups (counter)" in scrape
