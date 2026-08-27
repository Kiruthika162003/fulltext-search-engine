from __future__ import annotations

import pytest

from quarry.errors import Invalid, Missing
from quarry.readrepair import RepairingReader, Replica, Versioned


def divergent_pair() -> tuple[Replica, Replica]:
    left = Replica(name="left")
    right = Replica(name="right")
    left.put(Versioned(external=0, version=2, body="new text"))
    right.put(Versioned(external=0, version=1, body="old text"))
    left.put(Versioned(external=1, version=1, body="agreed"))
    right.put(Versioned(external=1, version=1, body="agreed"))
    return left, right


class TestReplicas:
    def test_versions_only_move_forward(self):
        replica = Replica(name="r")
        replica.put(Versioned(external=0, version=2, body="x"))
        with pytest.raises(Invalid, match="only move forward"):
            replica.put(Versioned(external=0, version=1, body="y"))


class TestReads:
    def test_the_newest_version_is_served(self):
        left, right = divergent_pair()
        reader = RepairingReader(replicas=[left, right])
        served, note = reader.read(0)
        assert served.body == "new text"
        assert "repairs queued for right" in note

    def test_agreement_reads_clean(self):
        left, right = divergent_pair()
        reader = RepairingReader(replicas=[left, right])
        _, note = reader.read(1)
        assert "all replicas agree" in note
        assert reader.clean_reads == 1

    def test_absent_documents_are_missing(self):
        left, right = divergent_pair()
        reader = RepairingReader(replicas=[left, right])
        with pytest.raises(Missing, match="no replica"):
            reader.read(99)

    def test_one_replica_is_just_a_read(self):
        with pytest.raises(Invalid, match="just a read"):
            RepairingReader(replicas=[Replica(name="alone")])


class TestTombstones:
    def test_a_missed_delete_pushes_the_tombstone(self):
        left, right = divergent_pair()
        left.put(Versioned(external=0, version=3, body=None))
        reader = RepairingReader(replicas=[left, right])
        served, note = reader.read(0)
        assert served is None
        assert "served v3" in note
        reader.drain_repairs()
        assert right.get(0).deleted()

    def test_the_stale_copy_cannot_resurrect_the_deleted(self):
        left, right = divergent_pair()
        left.put(Versioned(external=0, version=3, body=None))
        reader = RepairingReader(replicas=[left, right])
        reader.read(0)
        reader.drain_repairs()
        served, _ = reader.read(0)
        assert served is None
        assert reader.health().startswith("1 of 2 reads repaired")


class TestDraining:
    def test_repairs_heal_the_stale_copy(self):
        left, right = divergent_pair()
        reader = RepairingReader(replicas=[left, right])
        reader.read(0)
        message = reader.drain_repairs()
        assert message.startswith("drained 1 repair(s), applied 1")
        assert right.get(0).body == "new text"
        _, note = reader.read(0)
        assert "all replicas agree" in note

    def test_already_healed_repairs_are_skipped(self):
        left, right = divergent_pair()
        reader = RepairingReader(replicas=[left, right])
        reader.read(0)
        reader.read(0)
        message = reader.drain_repairs()
        assert "drained 2 repair(s), applied 1" in message
