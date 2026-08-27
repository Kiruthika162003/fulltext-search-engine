from __future__ import annotations

import pytest

from quarry.deletebyquery import delete_by_query, preview
from quarry.errors import Invalid
from quarry.query import parse
from quarry.schema import Schema
from quarry.writer import Index


def inbox() -> Index:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    index = Index(schema=schema)
    for number in range(6):
        index.add({"body": f"newsletter issue {number}"})
    for number in range(4):
        index.add({"body": f"personal letter {number}"})
    index.flush()
    return index


class TestTheViewfinder:
    def test_the_preview_counts_and_samples(self):
        seen = preview(inbox(), parse("newsletter"))
        assert seen.would_die == 6
        assert seen.corpus == 10
        assert seen.sample == (0, 1, 2, 3, 4)
        assert seen.share() == 0.6

    def test_the_preview_never_deletes(self):
        index = inbox()
        preview(index, parse("newsletter"))
        assert index.searchable_count() == 10


class TestTheTrigger:
    def test_the_confirmed_count_pulls_the_trigger(self):
        index = inbox()
        seen = preview(index, parse("personal"))
        dead = delete_by_query(
            index, parse("personal"), confirmed_count=seen.would_die
        )
        assert dead == [6, 7, 8, 9]
        assert index.searchable_count() == 6

    def test_a_moved_corpus_refuses_the_stale_confirmation(self):
        index = inbox()
        seen = preview(index, parse("personal"))
        index.add({"body": "personal letter late"})
        index.flush()
        with pytest.raises(Invalid, match="look again"):
            delete_by_query(
                index,
                parse("personal"),
                confirmed_count=seen.would_die,
            )

    def test_the_guard_refuses_the_reindex_in_disguise(self):
        index = inbox()
        seen = preview(index, parse("newsletter"))
        with pytest.raises(Invalid, match="wearing a delete"):
            delete_by_query(
                index,
                parse("newsletter"),
                confirmed_count=seen.would_die,
            )
        assert index.searchable_count() == 10

    def test_a_raised_guard_lets_the_big_one_through(self):
        index = inbox()
        seen = preview(index, parse("newsletter"))
        dead = delete_by_query(
            index,
            parse("newsletter"),
            confirmed_count=seen.would_die,
            guard_share=0.9,
        )
        assert len(dead) == 6

    def test_bad_guards_are_refused(self):
        with pytest.raises(Invalid):
            delete_by_query(
                inbox(), parse("x"), confirmed_count=0, guard_share=0.0
            )
