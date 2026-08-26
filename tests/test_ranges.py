from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.ranges import NumericRange, range_docs, range_report, sortable
from quarry.schema import Schema
from quarry.segment import Segment, SegmentBuilder


def years() -> Segment:
    schema = Schema()
    schema.add_text("body")
    schema.add_numeric("year")
    schema.seal()
    builder = SegmentBuilder(schema=schema)
    for offset, year in enumerate((1998, 2004, 2004, 2015, 2021)):
        builder.add({"body": f"book {offset}", "year": year})
    return builder.seal("shelf")


class TestSortable:
    def test_lexicographic_order_is_numeric_order(self):
        assert sortable(9) < sortable(10) < sortable(100)

    def test_negatives_are_refused_with_advice(self):
        with pytest.raises(Invalid, match="shifted"):
            sortable(-1)


class TestTheRange:
    def test_a_closed_range_takes_both_fences(self):
        docs = range_docs(
            years(), NumericRange(field="year", low=2004, high=2015)
        )
        assert docs == [1, 2, 3]

    def test_exclusive_fences_step_inside(self):
        docs = range_docs(
            years(),
            NumericRange(
                field="year",
                low=2004,
                high=2021,
                low_inclusive=False,
                high_inclusive=False,
            ),
        )
        assert docs == [3]

    def test_open_ends_reach_the_edge(self):
        docs = range_docs(years(), NumericRange(field="year", high=2004))
        assert docs == [0, 1, 2]
        docs = range_docs(years(), NumericRange(field="year", low=2015))
        assert docs == [3, 4]

    def test_a_backwards_range_is_refused(self):
        with pytest.raises(Invalid, match="backwards"):
            NumericRange(field="year", low=2020, high=2000)

    def test_a_doubly_open_range_is_not_a_question(self):
        with pytest.raises(Invalid, match="not a"):
            NumericRange(field="year")

    def test_ranges_walk_numerics_only(self):
        with pytest.raises(Invalid, match="walk numerics"):
            range_docs(years(), NumericRange(field="body", low=1))


class TestTheReport:
    def test_the_report_reads_interval_notation(self):
        report = range_report(
            years(),
            NumericRange(
                field="year", low=2004, high=2015, high_inclusive=False
            ),
        )
        assert report == "year [2004, 2015): 2 document(s)"

    def test_open_ends_say_so(self):
        report = range_report(years(), NumericRange(field="year", low=2015))
        assert report == "year [2015, open]: 2 document(s)"
