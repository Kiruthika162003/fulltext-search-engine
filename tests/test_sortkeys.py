from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.query import parse
from quarry.schema import Schema
from quarry.sortkeys import sort_report, sorted_search
from quarry.writer import Index


def newsdesk() -> Index:
    schema = Schema()
    schema.add_text("body")
    schema.add_numeric("published")
    schema.add_keyword("desk")
    schema.add_stored("thumbnail")
    schema.seal()
    index = Index(schema=schema, flush_at=2)
    index.add({"body": "cat rescued", "published": 300, "desk": "local"})
    index.add({"body": "cat show winners", "published": 100, "desk": "arts"})
    index.add({"body": "cat cafe opens", "published": 200, "desk": "local"})
    index.add({"body": "a cat with no date on it"})
    index.flush()
    return index


class TestOrdering:
    def test_ascending_by_number(self):
        hits = sorted_search(newsdesk(), parse("cat"), by="published")
        assert [hit.external for hit in hits] == [1, 2, 0, 3]

    def test_descending_flips_the_present_only(self):
        hits = sorted_search(
            newsdesk(), parse("cat"), by="published", descending=True
        )
        assert [hit.external for hit in hits] == [0, 2, 1, 3]

    def test_absence_never_outranks_presence(self):
        ascending = sorted_search(newsdesk(), parse("cat"), by="published")
        descending = sorted_search(
            newsdesk(), parse("cat"), by="published", descending=True
        )
        assert ascending[-1].external == 3
        assert descending[-1].external == 3
        assert ascending[-1].key is None

    def test_ties_keep_the_score_order_in_both_directions(self):
        index = newsdesk()
        ascending = sorted_search(index, parse("cat"), by="desk")
        descending = sorted_search(
            index, parse("cat"), by="desk", descending=True
        )
        local_up = [hit.external for hit in ascending if hit.key == "local"]
        local_down = [
            hit.external for hit in descending if hit.key == "local"
        ]
        assert local_up == local_down

    def test_keyword_sorting_is_alphabetical(self):
        hits = sorted_search(newsdesk(), parse("cat"), by="desk")
        assert [hit.key for hit in hits[:3]] == ["arts", "local", "local"]

    def test_the_sort_runs_before_the_page_cut(self):
        hits = sorted_search(
            newsdesk(), parse("cat"), by="published", limit=1
        )
        assert hits[0].external == 1


class TestRefusals:
    def test_text_fields_refuse_with_the_reason(self):
        with pytest.raises(Invalid, match="ORDER BY"):
            sorted_search(newsdesk(), parse("cat"), by="body")

    def test_stored_fields_were_never_indexed(self):
        with pytest.raises(Invalid, match="never indexed"):
            sorted_search(newsdesk(), parse("cat"), by="thumbnail")

    def test_zero_limits_are_refused(self):
        with pytest.raises(Invalid):
            sorted_search(newsdesk(), parse("cat"), by="published", limit=0)


class TestReport:
    def test_the_report_shows_keys_and_absences(self):
        hits = sorted_search(newsdesk(), parse("cat"), by="published")
        page = sort_report(hits, "published")
        assert page.splitlines()[0] == "sorted by published"
        assert "doc 1: 100" in page
        assert "doc 3: (absent)" in page
