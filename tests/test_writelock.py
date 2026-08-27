from __future__ import annotations

import pytest

from quarry.errors import Frozen, Invalid, Stale
from quarry.writelock import FencedStore, WriteLock


class TestLeases:
    def test_the_lease_is_exclusive_while_live(self):
        lock = WriteLock()
        lock.acquire("writer-a", now=0, duration=100)
        with pytest.raises(Frozen, match="do\\s?not break the lock"):
            lock.acquire("writer-b", now=50, duration=100)

    def test_expiry_frees_the_lock_without_a_human(self):
        lock = WriteLock()
        lock.acquire("writer-a", now=0, duration=100)
        token = lock.acquire("writer-b", now=150, duration=100)
        assert token == 2

    def test_renewal_keeps_the_token(self):
        lock = WriteLock()
        token = lock.acquire("writer-a", now=0, duration=100)
        message = lock.renew("writer-a", now=80, duration=100)
        assert f"same token {token}" in message

    def test_renewal_after_expiry_is_an_acquisition_in_disguise(self):
        lock = WriteLock()
        lock.acquire("writer-a", now=0, duration=100)
        with pytest.raises(Stale, match="acquire honestly"):
            lock.renew("writer-a", now=150, duration=100)

    def test_only_the_holder_renews(self):
        lock = WriteLock()
        lock.acquire("writer-a", now=0, duration=100)
        with pytest.raises(Invalid, match="for\\s?the holder"):
            lock.renew("writer-b", now=50, duration=100)


class TestFencing:
    def test_tokens_only_grow(self):
        lock = WriteLock()
        first = lock.acquire("writer-a", now=0, duration=10)
        second = lock.acquire("writer-b", now=20, duration=10)
        assert second > first

    def test_the_zombie_bounces_off_the_fence(self):
        lock = WriteLock()
        store = FencedStore()
        zombie_token = lock.acquire("writer-a", now=0, duration=10)
        store.write("first write", zombie_token)
        fresh_token = lock.acquire("writer-b", now=20, duration=10)
        store.write("successor writes", fresh_token)
        with pytest.raises(Stale, match="bounces\\s?off the fence"):
            store.write("zombie wakes up", zombie_token)
        assert store.bounced == 1

    def test_the_ledger_counts_the_bounces(self):
        store = FencedStore()
        store.write("one", 5)
        with pytest.raises(Stale):
            store.write("stale", 3)
        assert store.ledger() == (
            "1 write(s), 1 bounced, fence at 5"
        )
