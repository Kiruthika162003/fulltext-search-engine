from __future__ import annotations

import pytest

from quarry.acl import (
    PUBLIC,
    Caller,
    SecureSearcher,
    stamp_grants,
)
from quarry.errors import Invalid
from quarry.query import parse
from quarry.schema import Schema
from quarry.writer import Index


def office() -> SecureSearcher:
    schema = Schema()
    schema.add_text("body")
    schema.add_stored("granted_to")
    schema.seal()
    index = Index(schema=schema)
    index.add(stamp_grants({"body": "cat blog post"}, [PUBLIC]))
    index.add(
        stamp_grants({"body": "cat salary review"}, ["hr", "finance"])
    )
    index.add(stamp_grants({"body": "cat merger memo"}, ["board"]))
    index.add({"body": "cat orphan note"})
    index.flush()
    return SecureSearcher(index=index)


def alice() -> Caller:
    return Caller(name="alice", principals=frozenset({PUBLIC, "hr"}))


class TestVisibility:
    def test_the_badge_gates_the_match(self):
        found = office().visible_docs(parse("cat"), alice())
        assert [hit.external for hit in found] == [0, 1]

    def test_the_board_reads_the_memo(self):
        chair = Caller(
            name="chair", principals=frozenset({PUBLIC, "board"})
        )
        found = office().visible_docs(parse("cat"), chair)
        assert [hit.external for hit in found] == [0, 2]

    def test_the_count_is_the_visible_count(self):
        searcher = office()
        assert searcher.visible_count(parse("cat"), alice()) == 2

    def test_ungranted_documents_are_invisible_to_everyone(self):
        omniscient = Caller(
            name="root",
            principals=frozenset({PUBLIC, "hr", "finance", "board"}),
        )
        found = office().visible_docs(parse("cat"), omniscient)
        assert all(hit.external != 3 for hit in found)


class TestContracts:
    def test_an_empty_badge_is_refused_early(self):
        with pytest.raises(Invalid, match="empty badge"):
            Caller(name="nobody", principals=frozenset())

    def test_grants_are_explicit_or_the_add_fails(self):
        with pytest.raises(Invalid, match="say"):
            stamp_grants({"body": "text"}, [])

    def test_duplicate_grants_are_refused(self):
        with pytest.raises(Invalid, match="one label"):
            stamp_grants({"body": "text"}, ["hr", "hr"])

    def test_public_is_a_grant_not_an_absence(self):
        stamped = stamp_grants({"body": "text"}, [PUBLIC])
        assert stamped["granted_to"] == [PUBLIC]


class TestTheAudit:
    def test_denials_are_counted_not_described(self):
        searcher = office()
        searcher.visible_docs(parse("cat"), alice())
        assert searcher.denials == 2
        assert "never counted, faceted, or paged" in searcher.audit_line()
