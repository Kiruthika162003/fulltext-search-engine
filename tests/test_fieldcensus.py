from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.fieldcensus import census_field, census_page


def catalog() -> list[dict[str, object]]:
    docs: list[dict[str, object]] = []
    for n in range(10):
        doc: dict[str, object] = {
            "sku": f"sku-{n}",
            "brand": "acme" if n < 8 else "zephyr",
            "price": n * 10,
        }
        if n < 3:
            doc["color"] = "blue"
        docs.append(doc)
    docs[9]["price"] = "call us"
    return docs


class TestFieldReports:
    def test_fill_rates_are_arithmetic(self):
        report = census_field("color", catalog())
        assert report.fill_rate == 0.3
        assert "hides 70% of" in report.line()

    def test_skus_read_as_unbounded(self):
        report = census_field("sku", catalog())
        assert report.cardinality == "unbounded"
        assert "one-count buckets" in report.line()

    def test_brands_read_as_low_cardinality(self):
        report = census_field("brand", catalog())
        assert report.cardinality == "low"
        assert report.distinct == 2

    def test_constants_are_named(self):
        report = census_field("color", catalog())
        assert report.cardinality == "constant"

    def test_mixed_types_are_a_feed_bug(self):
        report = census_field("price", catalog())
        assert report.type_consistency == 0.9
        assert "feed bug wearing" in report.line()

    def test_no_documents_counts_nobody(self):
        with pytest.raises(Invalid, match="counts nobody"):
            census_field("sku", [])


class TestThePage:
    def test_every_field_appears_once(self):
        page = census_page(catalog())
        assert page.startswith("census over 10 document(s)")
        assert page.count("sku:") == 1
        assert page.count("price:") == 1

    def test_slices_never_pretend_to_be_the_corpus(self):
        page = census_page(
            catalog(), slice_note="the first feed batch"
        )
        assert page.endswith(
            "SLICE: this describes the first feed batch, not "
            "the corpus"
        )

    def test_the_whole_corpus_needs_no_disclaimer(self):
        assert "SLICE" not in census_page(catalog())
