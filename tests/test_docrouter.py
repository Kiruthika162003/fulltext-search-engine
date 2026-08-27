from __future__ import annotations

import pytest

from quarry.docrouter import DocRouter
from quarry.errors import Invalid, Missing


def grown_router() -> DocRouter:
    router = DocRouter()
    router.declare_epoch(1, shards=2)
    return router


class TestEpochs:
    def test_epochs_are_immutable_history(self):
        router = grown_router()
        with pytest.raises(Invalid, match="immutable"):
            router.declare_epoch(1, shards=4)
        with pytest.raises(Invalid, match="history only grows"):
            router.declare_epoch(0, shards=4)

    def test_zero_shards_route_nowhere(self):
        with pytest.raises(Invalid, match="routes nowhere"):
            DocRouter().declare_epoch(1, shards=0)

    def test_a_blank_router_is_missing(self):
        with pytest.raises(Missing, match="blank"):
            DocRouter().newest_epoch()


class TestPlacement:
    def test_placement_is_deterministic(self):
        left = grown_router()
        right = grown_router()
        assert left.place("tenant-9") == right.place("tenant-9")

    def test_locate_answers_for_residents_only(self):
        router = grown_router()
        with pytest.raises(Missing, match="not visitors"):
            router.locate("stranger")

    def test_empty_keys_route_by_accident(self):
        with pytest.raises(Invalid, match="by accident"):
            grown_router().place("  ")


class TestResharding:
    def test_growth_strands_nobody(self):
        router = grown_router()
        epoch, shard = router.place("tenant-9")
        router.declare_epoch(2, shards=8)
        assert router.locate("tenant-9") == (epoch, shard)

    def test_migration_is_explicit_and_narrated(self):
        router = grown_router()
        router.place("tenant-9")
        router.declare_epoch(2, shards=8)
        message = router.migrate("tenant-9")
        assert message.startswith("'tenant-9' moved epoch 1")
        assert "epoch 2" in message
        assert router.locate("tenant-9")[0] == 2

    def test_migrating_the_settled_is_a_noop(self):
        router = grown_router()
        router.place("tenant-9")
        assert "nothing to move" in router.migrate("tenant-9")

    def test_the_census_counts_stragglers(self):
        router = grown_router()
        router.place("a")
        router.place("b")
        router.declare_epoch(2, shards=4)
        router.place("c")
        router.migrate("a")
        assert router.stragglers() == ["b"]
        assert router.census() == (
            "3 document(s): 2 in epoch 2, 1 straggling in older "
            "epochs"
        )
