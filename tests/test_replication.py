from __future__ import annotations

import pytest

from quarry.errors import Invalid, Missing
from quarry.merge import MergePlan, merge
from quarry.query import parse
from quarry.replication import (
    Primary,
    Replica,
    replication_report,
    route_read,
)
from quarry.schema import Schema
from quarry.writer import Index


def sealed() -> Schema:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    return schema


def pair() -> tuple[Primary, Replica]:
    schema = sealed()
    primary = Primary(index=Index(schema=schema, flush_at=2))
    replica = Replica(schema=schema)
    return primary, replica


class TestShipping:
    def test_a_sync_pulls_only_the_missing(self):
        primary, replica = pair()
        for number in range(4):
            primary.add({"body": f"cat note {number}"})
        haul = replica.sync(primary)
        assert haul == "pulled 2 segment(s), refreshed 0 tombstone set(s)"
        second = replica.sync(primary)
        assert second == "pulled 0 segment(s), refreshed 0 tombstone set(s)"

    def test_tombstones_travel_separately(self):
        primary, replica = pair()
        for number in range(4):
            primary.add({"body": f"cat note {number}"})
        replica.sync(primary)
        primary.delete(0)
        haul = replica.sync(primary)
        assert "refreshed 1 tombstone set(s)" in haul
        answer = replica.search(primary, parse("cat"), limit=10)
        assert 0 not in answer.externals

    def test_merged_away_segments_leave_the_replica(self):
        primary, replica = pair()
        for number in range(4):
            primary.add({"body": f"cat note {number}"})
        replica.sync(primary)
        merge(
            primary.index,
            MergePlan(segment_names=("seg0", "seg1"), reason="test"),
        )
        replica.sync(primary)
        names = {segment.name for segment in replica.index.segments}
        assert names == {"seg2"}


class TestLag:
    def test_lag_is_measured_in_operations(self):
        primary, replica = pair()
        primary.add({"body": "one"})
        primary.add({"body": "two"})
        assert replica.lag(primary) == 2
        replica.sync(primary)
        assert replica.lag(primary) == 0

    def test_answers_carry_their_age(self):
        primary, replica = pair()
        primary.add({"body": "cat one"})
        primary.add({"body": "cat two"})
        replica.sync(primary)
        primary.add({"body": "cat three"})
        answer = replica.search(primary, parse("cat"), limit=10)
        assert answer.lag_operations == 1
        assert not answer.current
        assert len(answer.externals) == 2

    def test_a_replica_ahead_of_its_primary_is_a_lie(self):
        primary, replica = pair()
        replica.applied_operations = 5
        with pytest.raises(Invalid, match="lying"):
            replica.lag(primary)


class TestRouting:
    def test_read_your_writes_goes_home(self):
        primary, replica = pair()
        replica.sync(primary)
        assert route_read(primary, [replica], needs_own_writes=True) == (
            "primary"
        )

    def test_everything_else_takes_the_freshest(self):
        primary, replica_a = pair()
        replica_b = Replica(schema=primary.index.schema)
        primary.add({"body": "cat"})
        replica_b.sync(primary)
        chosen = route_read(
            primary, [replica_a, replica_b], needs_own_writes=False
        )
        assert chosen == "replica-1"

    def test_no_replicas_means_primary(self):
        primary, _ = pair()
        assert route_read(primary, [], needs_own_writes=False) == "primary"

    def test_the_report_names_each_lag(self):
        primary, replica = pair()
        primary.add({"body": "cat"})
        page = replication_report(primary, [replica])
        assert "primary at operation 1" in page
        assert "replica-0: 1 operation(s) behind" in page
        with pytest.raises(Missing):
            replication_report(primary, [])
