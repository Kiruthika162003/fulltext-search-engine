from __future__ import annotations

import pytest

from quarry.antientropy import (
    BUCKET_COUNT,
    VersionedStore,
    converged,
    synchronize,
)
from quarry.errors import Invalid


def drifted_pair() -> tuple[VersionedStore, VersionedStore]:
    left = VersionedStore(name="left")
    right = VersionedStore(name="right")
    for external in range(40):
        left.put(external, 1)
        right.put(external, 1)
    left.put(3, 2)
    right.put(7, 3)
    return left, right


class TestStores:
    def test_versions_only_move_forward(self):
        store = VersionedStore(name="s")
        store.put(0, 2)
        with pytest.raises(Invalid, match="only move forward"):
            store.put(0, 2)

    def test_agreeing_buckets_share_digests(self):
        left, right = drifted_pair()
        agreements = sum(
            1
            for bucket in range(BUCKET_COUNT)
            if left.bucket_digest(bucket)
            == right.bucket_digest(bucket)
        )
        assert agreements == BUCKET_COUNT - 2


class TestSynchronize:
    def test_only_disagreeing_buckets_are_opened(self):
        left, right = drifted_pair()
        report = synchronize(left, right)
        assert report.buckets_checked == BUCKET_COUNT
        assert report.buckets_opened == 2

    def test_newest_wins_in_both_directions(self):
        left, right = drifted_pair()
        report = synchronize(left, right)
        assert "doc 3: right v1 -> v2" in report.repairs
        assert "doc 7: left v1 -> v3" in report.repairs
        assert left.versions[7] == 3
        assert right.versions[3] == 2

    def test_a_sync_converges_the_pair(self):
        left, right = drifted_pair()
        assert not converged(left, right)
        synchronize(left, right)
        assert converged(left, right)

    def test_a_second_sync_finds_nothing(self):
        left, right = drifted_pair()
        synchronize(left, right)
        report = synchronize(left, right)
        assert report.buckets_opened == 0
        assert report.repairs == ()

    def test_self_sync_is_a_slow_noop(self):
        left, _ = drifted_pair()
        with pytest.raises(Invalid, match="slow no-op"):
            synchronize(left, left)

    def test_missing_documents_are_copied_over(self):
        left = VersionedStore(name="left")
        right = VersionedStore(name="right")
        left.put(0, 1)
        report = synchronize(left, right)
        assert right.versions[0] == 1
        assert "doc 0: right v0 -> v1" in report.repairs

    def test_the_report_reads_as_one_line(self):
        left, right = drifted_pair()
        report = synchronize(left, right)
        assert report.line() == (
            "checked 16 bucket(s), opened 2, applied 2 repair(s)"
        )
