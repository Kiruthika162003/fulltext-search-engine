from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.indexdiff import diff_indexes
from quarry.schema import Schema
from quarry.writer import Index


def sealed() -> Schema:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    return schema


def twin_indexes() -> tuple[Index, Index]:
    left = Index(schema=sealed())
    right = Index(schema=sealed())
    for held in (left, right):
        held.add({"body": "the black cat"})
        held.add({"body": "a friendly dog"})
        held.flush()
    return left, right


class TestAgreement:
    def test_twins_agree_and_the_report_says_so_warmly(self):
        left, right = twin_indexes()
        diff = diff_indexes(left, right)
        assert diff.clean()
        assert diff.agreeing == 2
        assert "document for document, field for field" in diff.report()

    def test_tombstones_count_as_absence(self):
        left, right = twin_indexes()
        right.delete(1)
        diff = diff_indexes(left, right)
        assert diff.only_left == (1,)
        assert not diff.clean()


class TestDifferences:
    def test_extra_documents_are_listed_by_side(self):
        left, right = twin_indexes()
        left.add({"body": "a third thing"})
        left.flush()
        diff = diff_indexes(left, right)
        assert diff.only_left == (2,)
        assert diff.only_right == ()
        assert "only left: 2" in diff.report()

    def test_field_disagreements_name_field_and_both_values(self):
        left = Index(schema=sealed())
        right = Index(schema=sealed())
        left.add({"body": "version one"})
        right.add({"body": "version two"})
        left.flush()
        right.flush()
        diff = diff_indexes(left, right)
        assert len(diff.disagreements) == 1
        row = diff.disagreements[0]
        assert row.field_name == "body"
        assert "version one" in row.left_value
        assert "'version one'" in diff.report()

    def test_the_agreeing_count_rides_with_the_trouble(self):
        left, right = twin_indexes()
        left.add({"body": "extra"})
        left.flush()
        diff = diff_indexes(left, right)
        assert diff.agreeing == 2
        assert diff.report().startswith("2 documents agree")


class TestContracts:
    def test_different_schemas_diff_schemas_first(self):
        other = Schema()
        other.add_text("title")
        other.seal()
        left = Index(schema=sealed())
        right = Index(schema=other)
        with pytest.raises(Invalid, match="schemas first"):
            diff_indexes(left, right)
