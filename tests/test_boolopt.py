from __future__ import annotations

import pytest

from quarry.boolopt import simplify
from quarry.errors import Invalid
from quarry.query import parse


class TestWithinGroups:
    def test_duplicate_clauses_collapse(self):
        held = simplify(parse("body:cat body:cat body:dog"))
        assert len(held.query.groups[0]) == 2
        assert any(
            "AND is idempotent" in line for line in held.rewrites
        )

    def test_unsatisfiable_groups_are_deleted_and_reported(self):
        held = simplify(
            parse("body:cat -body:cat OR body:dog")
        )
        assert len(held.query.groups) == 1
        assert held.query.canonical() == "body:dog"
        assert any(
            "unsatisfiable" in line for line in held.rewrites
        )

    def test_an_entirely_unsatisfiable_query_refuses(self):
        with pytest.raises(Invalid, match="can never match"):
            simplify(parse("body:cat -body:cat"))


class TestAcrossGroups:
    def test_duplicate_or_branches_collapse(self):
        held = simplify(parse("body:cat OR body:cat"))
        assert len(held.query.groups) == 1
        assert any(
            "OR is idempotent" in line for line in held.rewrites
        )

    def test_wider_branches_are_dropped(self):
        held = simplify(
            parse("body:cat body:dog OR body:cat")
        )
        assert held.query.canonical() == "body:cat"
        assert any(
            "narrower branch" in line for line in held.rewrites
        )

    def test_distinct_branches_all_survive(self):
        held = simplify(parse("body:cat OR body:dog"))
        assert len(held.query.groups) == 2


class TestTheReport:
    def test_a_minimal_query_says_so(self):
        held = simplify(parse("body:cat body:dog"))
        assert held.rewrites == ()
        assert held.report() == "already minimal; nothing rewritten"

    def test_every_rewrite_is_named(self):
        held = simplify(
            parse("body:cat body:cat OR body:cat")
        )
        page = held.report()
        assert "AND is idempotent" in page
        assert (
            "OR is idempotent" in page
            or "narrower branch" in page
        )
