from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.normqueries import FoldLedger, normalize


class TestFolds:
    def test_case_space_and_order_fold_together(self):
        assert (
            normalize("Cat  Dog")
            == normalize("dog cat")
            == "cat dog"
        )

    def test_analyzer_folding_merges_plain_plurals(self):
        assert normalize("blankets") == normalize("blanket")

    def test_the_es_plural_diverges_like_the_index_does(self):
        assert normalize("kettles") != normalize("kettle")

    def test_stopwords_drop_out_of_the_key(self):
        assert normalize("the cat and the dog") == "cat dog"

    def test_all_stopword_queries_normalize_to_nothing(self):
        with pytest.raises(Invalid, match="normalized to nothing"):
            normalize("the of and")

    def test_emptiness_is_refused(self):
        with pytest.raises(Invalid, match="normalizes to nothing"):
            normalize("   ")


class TestDeliberateNonFolds:
    def test_phrases_keep_their_order(self):
        assert normalize('"deep work"') == '"deep work"'
        assert normalize('"work deep"') != normalize('"deep work"')

    def test_field_prefixes_survive(self):
        assert normalize("Title:Cat") == "title:cat"
        assert normalize("title:cat") != normalize("body:cat")


class TestTheLedger:
    def stocked(self) -> FoldLedger:
        ledger = FoldLedger()
        for raw in (
            "copper blanket",
            "Blanket Copper",
            "copper  blankets",
            "kettle",
        ):
            ledger.fold(raw)
        return ledger

    def test_spellings_share_their_bucket(self):
        ledger = self.stocked()
        assert len(ledger.buckets["blanket copper"]) == 3

    def test_demand_ranks_by_absorbed_spellings(self):
        demand = self.stocked().demand(top_n=1)
        assert demand[0] == "blanket copper: 3 spelling(s)"

    def test_the_absorption_report_counts_unmasked_intent(self):
        page = self.stocked().absorption_report()
        assert page == (
            "4 raw spelling(s) folded into 2 bucket(s); 2 "
            "duplicate intent(s) unmasked"
        )

    def test_an_empty_ledger_knows_nothing(self):
        with pytest.raises(Invalid, match="demand is unknown"):
            FoldLedger().demand()
