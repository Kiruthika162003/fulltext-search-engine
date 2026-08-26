from __future__ import annotations

import pytest

from quarry.errors import Invalid, Missing
from quarry.query import parse
from quarry.schema import Schema
from quarry.shards import ShardedIndex, route


def sealed() -> Schema:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    return schema


def fleet() -> ShardedIndex:
    sharded = ShardedIndex(schema=sealed(), shard_count=3)
    for number in range(30):
        sharded.add(f"user-{number}", {"body": f"cat note number {number}"})
    sharded.add("whale", {"body": "the rare xylophone document"})
    sharded.flush()
    return sharded


class TestRouting:
    def test_the_same_key_always_lands_together(self):
        assert route("user-7", 3) == route("user-7", 3)

    def test_a_new_shard_count_moves_somebody(self):
        assert any(
            route(f"user-{number}", 3) != route(f"user-{number}", 5)
            for number in range(20)
        )

    def test_empty_keys_and_zero_shards_are_refused(self):
        with pytest.raises(Invalid):
            route("", 3)
        with pytest.raises(Invalid):
            route("key", 0)

    def test_the_spread_is_roughly_fair(self):
        sharded = fleet()
        assert sharded.imbalance() < 2.0


class TestScatterGather:
    def test_a_full_gather_is_complete(self):
        page = fleet().search(parse("cat"), limit=10)
        assert page.complete
        assert page.missing_shards == ()
        assert page.corpus_share_reached == 1.0
        assert len(page.hits) == 10

    def test_scores_merge_without_renormalising(self):
        page = fleet().search(parse("xylophone"), limit=5)
        assert len(page.hits) == 1
        assert page.hits[0].score > 0

    def test_hits_carry_their_shard(self):
        page = fleet().search(parse("cat"), limit=30)
        shards_seen = {hit.shard for hit in page.hits}
        assert len(shards_seen) > 1

    def test_a_zero_limit_is_refused(self):
        with pytest.raises(Invalid):
            fleet().search(parse("cat"), limit=0)


class TestPartialFailure:
    def test_a_down_shard_makes_the_answer_partial(self):
        sharded = fleet()
        sharded.mark_down(1)
        page = sharded.search(parse("cat"), limit=30)
        assert not page.complete
        assert page.missing_shards == (1,)
        assert 0 < page.corpus_share_reached < 1.0

    def test_the_share_is_docs_not_shards(self):
        sharded = fleet()
        counts = sharded.doc_counts()
        sharded.mark_down(0)
        page = sharded.search(parse("cat"), limit=5)
        expected = (sum(counts) - counts[0]) / sum(counts)
        assert page.corpus_share_reached == pytest.approx(
            expected, abs=1e-4
        )

    def test_recovery_restores_completeness(self):
        sharded = fleet()
        sharded.mark_down(2)
        sharded.mark_up(2)
        assert sharded.search(parse("cat")).complete

    def test_marking_down_a_ghost_shard_is_named(self):
        with pytest.raises(Missing):
            fleet().mark_down(9)
