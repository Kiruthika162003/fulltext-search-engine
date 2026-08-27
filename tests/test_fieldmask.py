from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.fieldmask import MaskBook

ORDER = {
    "item": "copper kettle",
    "buyer": "j. finch",
    "card_tail": "4242",
    "total": 68,
}


def office() -> MaskBook:
    book = MaskBook()
    book.declare("support", {"card_tail"})
    book.declare("analytics", {"buyer", "card_tail"})
    book.declare("billing", set())
    return book


class TestMasks:
    def test_removal_builds_a_new_document(self):
        masked = office().apply(ORDER, ["support"])
        assert "card_tail" not in masked
        assert masked["buyer"] == "j. finch"

    def test_absence_beats_blanking(self):
        masked = office().apply(ORDER, ["analytics"])
        assert set(masked) == {"item", "total"}

    def test_unknown_roles_get_the_strictest_mask(self):
        masked = office().apply(ORDER, ["intern"])
        assert set(masked) == {"item", "total"}

    def test_no_roles_gets_the_strictest_mask(self):
        masked = office().apply(ORDER, [])
        assert set(masked) == {"item", "total"}


class TestComposition:
    def test_privileges_do_not_add_fields_back(self):
        masked = office().apply(ORDER, ["billing", "analytics"])
        assert "buyer" not in masked
        assert "card_tail" not in masked

    def test_a_single_generous_role_sees_everything(self):
        masked = office().apply(ORDER, ["billing"])
        assert masked == ORDER


class TestTheBook:
    def test_masks_do_not_edit_in_place(self):
        book = office()
        with pytest.raises(Invalid, match="not by editing"):
            book.declare("support", {"buyer"})

    def test_an_empty_book_cannot_default_open(self):
        with pytest.raises(Invalid, match="showing everything"):
            MaskBook().apply(ORDER, ["anyone"])

    def test_who_sees_answers_the_privacy_review(self):
        book = office()
        assert book.who_sees("card_tail") == ["billing"]
        assert book.who_sees("item") == [
            "analytics",
            "billing",
            "support",
        ]

    def test_the_audit_page_reads_field_by_field(self):
        page = office().audit_page(["card_tail", "buyer"])
        assert "buyer: visible to billing, support" in page
        assert "card_tail: visible to billing" in page
