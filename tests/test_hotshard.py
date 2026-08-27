from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.hotshard import ShardLoad, cooling_plan, find_hot, median


def fleet() -> list[ShardLoad]:
    return [
        ShardLoad(
            name="shard-a",
            tenant_loads={"viral": 800, "quiet": 50},
        ),
        ShardLoad(name="shard-b", tenant_loads={"steady": 100}),
        ShardLoad(name="shard-c", tenant_loads={"calm": 80}),
        ShardLoad(name="shard-d", tenant_loads={"mild": 120}),
    ]


class TestDetection:
    def test_the_median_resists_the_hot_shard(self):
        assert median([850, 100, 80, 120]) == 110.0

    def test_hot_shards_are_flagged_against_the_median(self):
        hot, fleet_median = find_hot(fleet())
        assert hot == ["shard-a"]
        assert fleet_median == 110.0

    def test_a_balanced_fleet_flags_nothing(self):
        balanced = [
            ShardLoad(name=f"s{n}", tenant_loads={"t": 100})
            for n in range(3)
        ]
        hot, _ = find_hot(balanced)
        assert hot == []

    def test_two_shards_cannot_name_a_hot_one(self):
        with pytest.raises(Invalid, match="means nothing"):
            find_hot(fleet()[:2])

    def test_medians_need_values(self):
        with pytest.raises(Invalid, match="nothing"):
            median([])


class TestCooling:
    def test_the_plan_moves_the_biggest_tenant_first(self):
        moves, _ = cooling_plan(fleet())
        assert moves[0].tenant == "viral"
        assert moves[0].source == "shard-a"

    def test_the_move_lands_on_the_coolest_shard(self):
        moves, _ = cooling_plan(fleet())
        assert moves[0].target == "shard-c"

    def test_the_projection_shows_its_arithmetic(self):
        _, page = cooling_plan(fleet())
        assert "projected loads after:" in page
        assert "shard-a: 50" in page
        assert "shard-c: 880" in page
        assert "threshold 220" in page

    def test_a_balanced_fleet_needs_no_plan(self):
        balanced = [
            ShardLoad(name=f"s{n}", tenant_loads={"t": 100})
            for n in range(3)
        ]
        moves, message = cooling_plan(balanced)
        assert moves == []
        assert "balanced" in message
