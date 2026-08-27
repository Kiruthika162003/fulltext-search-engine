from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.snapshotdiff import (
    Snapshot,
    changed_fields,
    diff_snapshots,
    fingerprint,
)


def monday() -> Snapshot:
    return Snapshot(
        label="monday",
        schema_identity="body,price",
        documents={
            0: {"body": "a red kettle", "price": 30},
            1: {"body": "a blue teapot", "price": 45},
            2: {"body": "a copper pan", "price": 80},
        },
    )


def friday() -> Snapshot:
    return Snapshot(
        label="friday",
        schema_identity="body,price",
        documents={
            0: {"body": "a red kettle", "price": 30},
            2: {"body": "a copper pan", "price": 75},
            3: {"body": "a cast iron pot", "price": 60},
        },
    )


class TestFingerprints:
    def test_key_order_cannot_invent_differences(self):
        left = fingerprint({"a": 1, "b": 2})
        right = fingerprint({"b": 2, "a": 1})
        assert left == right

    def test_value_changes_change_the_print(self):
        assert fingerprint({"a": 1}) != fingerprint({"a": 2})


class TestDiffing:
    def test_adds_removes_and_changes_are_named(self):
        diff = diff_snapshots(monday(), friday())
        assert diff.added == (3,)
        assert diff.removed == (1,)
        assert diff.changed == (2,)
        assert diff.unchanged == 1

    def test_the_summary_shows_its_arithmetic(self):
        diff = diff_snapshots(monday(), friday())
        assert diff.summary() == (
            "1 added, 1 removed, 1 changed of 4 (75% drift)"
        )

    def test_identical_snapshots_say_identical(self):
        twin = Snapshot(
            label="tuesday",
            schema_identity="body,price",
            documents=monday().documents,
        )
        diff = diff_snapshots(monday(), twin)
        assert diff.summary() == "identical: 3 documents match"

    def test_schema_drift_is_refused_with_a_recipe(self):
        widened = Snapshot(
            label="friday",
            schema_identity="body,price,stock",
            documents={},
        )
        with pytest.raises(Invalid, match="Migrate, snapshot"):
            diff_snapshots(monday(), widened)

    def test_self_comparison_measures_the_tool(self):
        with pytest.raises(Invalid, match="not the"):
            diff_snapshots(monday(), monday())


class TestFieldDiffs:
    def test_the_changed_field_is_pinpointed(self):
        changes = changed_fields(monday(), friday(), 2)
        assert changes == ["price: 80 -> 75"]

    def test_absent_documents_need_both_sides(self):
        with pytest.raises(Invalid, match="both sides"):
            changed_fields(monday(), friday(), 1)
