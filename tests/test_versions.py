from __future__ import annotations

import pytest

from quarry.errors import Invalid, Missing
from quarry.versions import VersionedStore


def two_editors() -> tuple[VersionedStore, int, int]:
    store = VersionedStore()
    external, version = store.create({"title": "Cat Care", "price": 10})
    return store, external, version


class TestTheHappyPath:
    def test_versions_bump_on_every_write(self):
        store, external, version = two_editors()
        second = store.update(
            external, {"title": "Cat Care", "price": 12}, version
        )
        assert second == 2
        fields, current = store.read(external)
        assert fields["price"] == 12
        assert current == 2

    def test_reads_hand_back_the_version_to_present(self):
        store, external, _ = two_editors()
        fields, version = store.read(external)
        assert store.update(external, fields, version) == 2


class TestTheConflict:
    def test_the_second_save_loses_politely(self):
        store, external, version = two_editors()
        store.update(external, {"title": "Cat Care", "price": 12}, version)
        with pytest.raises(Invalid, match="saved underneath"):
            store.update(
                external, {"title": "Cat Handbook"}, version
            )
        assert store.conflicts_refused == 1

    def test_the_winner_is_never_erased(self):
        store, external, version = two_editors()
        store.update(external, {"price": 12}, version)
        try:
            store.update(external, {"price": 99}, version)
        except Invalid:
            pass
        fields, _ = store.read(external)
        assert fields["price"] == 12

    def test_stale_deletes_are_the_same_erasure(self):
        store, external, version = two_editors()
        store.update(external, {"price": 12}, version)
        with pytest.raises(Invalid, match="pointed the other way"):
            store.delete(external, version)
        assert store.read(external)

    def test_a_fresh_delete_goes_through(self):
        store, external, _ = two_editors()
        _, version = store.read(external)
        store.delete(external, version)
        with pytest.raises(Missing):
            store.read(external)


class TestTheMergeHint:
    def test_the_hint_lists_exactly_what_moved(self):
        store, external, version = two_editors()
        store.update(
            external, {"title": "Cat Care", "price": 12}, version
        )
        hint = store.merge_hint(
            external, {"title": "Cat Handbook", "price": 10}, version
        )
        assert "version 1 -> 2" in hint
        assert "price: theirs 12, yours 10" in hint
        assert "title: theirs 'Cat Care', yours 'Cat Handbook'" in hint

    def test_nothing_moved_says_retry(self):
        store, external, version = two_editors()
        hint = store.merge_hint(external, {"title": "x"}, version)
        assert hint == "nothing moved; retry the update as read"

    def test_ghosts_are_named(self):
        store, _, _ = two_editors()
        with pytest.raises(Missing):
            store.read(99)
