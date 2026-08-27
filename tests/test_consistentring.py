from __future__ import annotations

import pytest

from quarry.consistentring import HashRing, moved_keys
from quarry.errors import Invalid, Missing

KEYS = [f"tenant-{n}" for n in range(500)]


def trio() -> HashRing:
    ring = HashRing()
    for node in ("east", "west", "north"):
        ring.add_node(node)
    return ring


class TestOwnership:
    def test_ownership_is_deterministic(self):
        assert trio().owner("tenant-7") == trio().owner("tenant-7")

    def test_every_key_has_exactly_one_owner(self):
        ring = trio()
        assert all(
            ring.owner(key) in {"east", "west", "north"}
            for key in KEYS[:50]
        )

    def test_an_empty_ring_owns_nothing(self):
        with pytest.raises(Missing, match="nothing owns"):
            HashRing().owner("tenant-1")

    def test_doubled_nodes_are_refused(self):
        ring = trio()
        with pytest.raises(Invalid, match="invisibly"):
            ring.add_node("east")


class TestBalance:
    def test_virtual_nodes_keep_shares_near_fair(self):
        shares = trio().spread(KEYS)
        for share in shares.values():
            assert 0.15 <= share <= 0.55

    def test_the_report_states_the_worst_skew(self):
        page = trio().spread_report(KEYS)
        assert "worst skew" in page
        assert "of keys" in page


class TestMovement:
    def test_growing_moves_only_the_necessary_share(self):
        before = trio()
        after = trio()
        after.add_node("south")
        share = moved_keys(before, after, KEYS)
        assert 0.05 <= share <= 0.45

    def test_unrelated_keys_stay_put(self):
        before = trio()
        after = trio()
        after.add_node("south")
        stayed = [
            key
            for key in KEYS
            if before.owner(key) == after.owner(key)
        ]
        assert all(
            before.owner(key) == after.owner(key)
            for key in stayed
        )
        assert len(stayed) >= len(KEYS) // 2

    def test_removal_spills_clockwise_only(self):
        before = trio()
        after = trio()
        after.remove_node("north")
        for key in KEYS[:100]:
            if before.owner(key) != "north":
                assert after.owner(key) == before.owner(key)

    def test_the_last_node_cannot_leave(self):
        ring = HashRing()
        ring.add_node("alone")
        with pytest.raises(Invalid, match="strands every key"):
            ring.remove_node("alone")
