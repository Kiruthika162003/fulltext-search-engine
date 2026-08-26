from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.indexstats import GrowthCurve, shape_of
from quarry.schema import Schema
from quarry.segment import Segment, SegmentBuilder


def prose_segment() -> Segment:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    builder = SegmentBuilder(schema=schema)
    builder.add({"body": "cat cat cat dog dog bird"})
    builder.add({"body": "cat dog fish heron owl"})
    return builder.seal("prose")


def id_segment() -> Segment:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    builder = SegmentBuilder(schema=schema)
    builder.add({"body": "sku10001 sku10002 sku10003 sku10004"})
    builder.add({"body": "sku10005 sku10006 sku10007 sku10008"})
    return builder.seal("ids")


class TestShape:
    def test_the_shape_counts_occurrences_not_documents(self):
        shape = shape_of(prose_segment(), "body")
        assert shape.total_occurrences == 11
        assert shape.vocabulary_size == 6

    def test_prose_is_top_heavy_and_thin_tailed(self):
        shape = shape_of(prose_segment(), "body")
        assert shape.top_heaviness == 1.0
        assert shape.hapax_share == pytest.approx(4 / 6, abs=1e-4)

    def test_the_serial_number_flood_raises_the_eyebrow(self):
        shape = shape_of(id_segment(), "body")
        assert shape.hapax_share == 1.0
        raised = shape.eyebrow_lines()
        assert any("serial numbers" in line for line in raised)

    def test_an_unindexed_field_is_refused(self):
        schema = Schema()
        schema.add_text("body")
        schema.add_text("title")
        schema.seal()
        builder = SegmentBuilder(schema=schema)
        builder.add({"body": "words here"})
        segment = builder.seal("s")
        with pytest.raises(Invalid, match="shape of nothing"):
            shape_of(segment, "title")


class TestGrowth:
    def grown(self) -> GrowthCurve:
        curve = GrowthCurve(sample_every=10)
        for number in range(30):
            common = ["cat", "dog", "the", "house"]
            fresh = [f"rare{number}"] if number % 3 == 0 else []
            curve.observe(common + fresh)
        return curve

    def test_sampling_lands_on_the_stride(self):
        curve = self.grown()
        assert [docs for docs, _ in curve.points] == [10, 20, 30]

    def test_healthy_growth_slows(self):
        assert self.grown().slowing() is True

    def test_a_flood_of_fresh_terms_does_not_slow(self):
        curve = GrowthCurve(sample_every=10)
        for number in range(30):
            curve.observe([f"id{number}a", f"id{number}b"])
        assert curve.slowing() is False

    def test_the_curve_needs_three_points(self):
        curve = GrowthCurve(sample_every=10)
        for _ in range(20):
            curve.observe(["cat"])
        with pytest.raises(Invalid, match="three points"):
            curve.slowing()

    def test_the_report_reads_docs_to_terms(self):
        report = self.grown().curve_report()
        assert report.startswith("vocabulary growth (docs:terms) 10:")
