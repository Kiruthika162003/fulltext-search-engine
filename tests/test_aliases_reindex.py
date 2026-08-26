from __future__ import annotations

import pytest

from quarry.aliases import AliasTable
from quarry.errors import Invalid, Missing
from quarry.multisearch import search_index
from quarry.query import parse
from quarry.reindex import Reindex
from quarry.schema import Schema
from quarry.tokenize import Analyzer
from quarry.writer import Index


def make_index(stemming: bool = True) -> Index:
    schema = Schema()
    schema.add_text("body", analyzer=Analyzer(stemming=stemming))
    schema.seal()
    return Index(schema=schema, flush_at=4)


def wired() -> AliasTable:
    table = AliasTable()
    table.register("products-v1", make_index())
    table.point("products", "products-v1", who="meera", reason="launch")
    return table


class TestAliases:
    def test_callers_resolve_the_intention(self):
        table = wired()
        index = table.resolve("products")
        index.add({"body": "wool cat toy"})
        index.flush()
        assert table.indexes["products-v1"].searchable_count() == 1

    def test_a_dangling_alias_is_named_with_the_roster(self):
        with pytest.raises(Missing, match="registered aliases"):
            wired().resolve("ghosts")

    def test_pointing_at_the_unregistered_is_refused(self):
        with pytest.raises(Missing, match="no such index"):
            wired().point("products", "products-v9", "raj", "typo")

    def test_a_no_op_swap_pollutes_nothing(self):
        with pytest.raises(Invalid, match="pollutes the history"):
            wired().point("products", "products-v1", "raj", "again")

    def test_unreferenced_indexes_are_retirement_candidates(self):
        table = wired()
        table.register("products-v2", make_index())
        assert table.unreferenced() == ["products-v2"]

    def test_the_call_log_reads_who_and_why(self):
        log = wired().call_log()
        assert log == "products: (new) -> products-v1 (meera: launch)"


class TestReindex:
    def migration(self) -> tuple[AliasTable, Reindex]:
        table = wired()
        old = table.indexes["products-v1"]
        for number in range(6):
            old.add({"body": f"cats item number {number}"})
        old.flush()
        table.register("products-v2", make_index(stemming=True))
        job = Reindex(
            table=table,
            alias="products",
            old_name="products-v1",
            new_name="products-v2",
            batch=2,
        )
        return table, job

    def test_writes_before_dual_mode_are_refused(self):
        _, job = self.migration()
        with pytest.raises(Invalid, match="begin them first"):
            job.add({"body": "late arrival"})

    def test_dual_writes_land_in_both_worlds(self):
        table, job = self.migration()
        job.begin_dual_writes()
        job.add({"body": "fresh cats arrival"})
        table.indexes["products-v1"].flush()
        table.indexes["products-v2"].flush()
        assert table.indexes["products-v2"].searchable_count() == 1

    def test_the_backfill_copies_without_double_counting_duals(self):
        table, job = self.migration()
        job.begin_dual_writes()
        job.add({"body": "fresh cats arrival"})
        copied = job.backfill()
        assert copied == 6
        assert table.indexes["products-v2"].searchable_count() == 7

    def test_verification_gates_the_swap(self):
        _, job = self.migration()
        job.begin_dual_writes()
        job.backfill()
        with pytest.raises(Invalid, match="hope is not a gate"):
            job.swap(who="meera")
        assert job.verify(["cats"]) == []
        job.swap(who="meera")
        assert job.table.target_of("products") == "products-v2"

    def test_probeless_verification_is_a_costume(self):
        _, job = self.migration()
        with pytest.raises(Invalid, match="costume"):
            job.verify([])

    def test_a_diverging_probe_is_reported_and_blocks(self):
        table, job = self.migration()
        job.begin_dual_writes()
        job.backfill()
        table.indexes["products-v2"].add({"body": "stowaway cats"})
        table.indexes["products-v2"].flush()
        complaints = job.verify(["cats"])
        assert complaints
        assert any("counts diverge" in line for line in complaints)
        with pytest.raises(Invalid):
            job.swap(who="meera")

    def test_search_through_the_alias_after_the_swap(self):
        table, job = self.migration()
        job.begin_dual_writes()
        job.backfill()
        job.verify(["cats"])
        job.swap(who="meera")
        hits = search_index(
            table.resolve("products"), parse("cats"), limit=10
        ).hits
        assert len(hits) == 6

    def test_rollback_is_one_alias_move_with_a_reason(self):
        table, job = self.migration()
        job.begin_dual_writes()
        job.backfill()
        job.verify(["cats"])
        job.swap(who="meera")
        job.rollback(who="raj", reason="latency regression on v2")
        assert table.target_of("products") == "products-v1"
        assert "latency regression" in table.call_log()
