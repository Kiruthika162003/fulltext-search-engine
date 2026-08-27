from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.skips import build_skiplist, plain_find, probe_report

LONG = [n * 3 for n in range(400)]


class TestBuilding:
    def test_the_interval_is_the_root_of_the_length(self):
        assert build_skiplist(LONG).interval == 20
        assert build_skiplist([1, 2, 3, 4]).interval == 2

    def test_unsorted_ids_leap_into_garbage(self):
        with pytest.raises(Invalid, match="garbage"):
            build_skiplist([5, 3, 9])
        with pytest.raises(Invalid, match="garbage"):
            build_skiplist([3, 3, 9])

    def test_empty_lists_need_no_skips(self):
        with pytest.raises(Invalid, match="no skips"):
            build_skiplist([])


class TestFinding:
    def test_the_walks_agree_on_everything(self):
        skiplist = build_skiplist(LONG)
        for target in (0, 3, 599, 600, 1197, 1, 1000, 5000):
            skip_found, _ = skiplist.find(target)
            plain_found, _ = plain_find(skiplist.doc_ids, target)
            assert skip_found == plain_found

    def test_deep_members_cost_far_fewer_probes(self):
        skiplist = build_skiplist(LONG)
        found, skip_cost = skiplist.find(1140)
        plain_found, plain_cost = plain_find(
            skiplist.doc_ids, 1140
        )
        assert found and plain_found
        assert skip_cost < plain_cost / 4


class TestTheReport:
    def test_savings_come_from_counters(self):
        page = probe_report(LONG, [300, 600, 900, 1140])
        assert "from counters, not O-notation" in page
        assert "interval 20" in page

    def test_the_speedup_is_real_on_deep_lookups(self):
        page = probe_report(LONG, [1140, 1170, 1197])
        ratio = float(page.rsplit("(", 1)[1].split("x")[0])
        assert ratio > 4.0

    def test_no_lookups_report_nothing(self):
        with pytest.raises(Invalid, match="reports nothing"):
            probe_report(LONG, [])
