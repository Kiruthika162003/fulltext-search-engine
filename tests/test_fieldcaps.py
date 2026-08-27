from __future__ import annotations

import pytest

from quarry.errors import Missing
from quarry.fieldcaps import (
    can,
    capabilities_of,
    capability_page,
    fields_with,
)
from quarry.schema import Schema


def shop_schema() -> Schema:
    schema = Schema()
    schema.add_text("description")
    schema.add_keyword("brand")
    schema.add_numeric("price")
    schema.add_stored("thumbnail")
    schema.seal()
    return schema


class TestTheMatrix:
    def test_each_kind_earns_its_abilities(self):
        schema = shop_schema()
        assert capabilities_of(schema, "description") == {
            "match",
            "phrase",
            "highlight",
        }
        assert "range" in capabilities_of(schema, "price")
        assert capabilities_of(schema, "thumbnail") == frozenset()

    def test_refusals_explain_the_design(self):
        allowed, reason = can(shop_schema(), "description", "sort")
        assert not allowed
        assert "alphabetizes sentences" in reason

    def test_stored_fields_are_freight(self):
        allowed, reason = can(shop_schema(), "thumbnail", "match")
        assert not allowed
        assert "never asked" in reason

    def test_permissions_come_with_their_kind(self):
        allowed, reason = can(shop_schema(), "brand", "facet")
        assert allowed
        assert reason == "brand (keyword) can facet"


class TestLookups:
    def test_the_ui_question_which_fields_sort(self):
        assert fields_with(shop_schema(), "sort") == [
            "brand",
            "price",
        ]

    def test_unknown_capabilities_show_the_vocabulary(self):
        with pytest.raises(Missing, match="vocabulary"):
            fields_with(shop_schema(), "teleport")

    def test_unknown_fields_list_the_declared(self):
        with pytest.raises(Missing, match="declared"):
            can(shop_schema(), "ghost", "sort")


class TestThePage:
    def test_the_page_reads_field_by_field(self):
        page = capability_page(shop_schema())
        lines = page.splitlines()
        assert lines[0] == "brand (keyword): facet, filter, sort"
        assert "thumbnail (stored): stored freight" in lines
