from __future__ import annotations

import pytest

from quarry.collapse import collapse_report, collapse_search
from quarry.errors import Invalid
from quarry.query import parse
from quarry.schema import Schema
from quarry.writer import Index


def feedroom() -> Index:
    schema = Schema()
    schema.add_text("body")
    schema.add_keyword("source")
    schema.seal()
    index = Index(schema=schema)
    index.add({"body": "cat news issue one", "source": "newsletter"})
    index.add({"body": "cat cat cat special", "source": "newsletter"})
    index.add({"body": "cat report from the lab", "source": "lab"})
    index.add({"body": "a lone cat letter"})
    index.add({"body": "cat digest weekly", "source": "newsletter"})
    index.flush()
    return index


class TestCollapsing:
    def test_one_representative_per_group(self):
        groups = collapse_search(feedroom(), parse("cat"), by="source")
        keys = [group.key for group in groups]
        assert keys.count("newsletter") == 1
        assert keys.count("lab") == 1

    def test_the_best_scorer_represents_its_group(self):
        groups = collapse_search(feedroom(), parse("cat"), by="source")
        newsletter = next(
            group for group in groups if group.key == "newsletter"
        )
        assert newsletter.representative == 1
        assert newsletter.folded_count() == 2

    def test_groups_hold_the_position_their_best_earned(self):
        groups = collapse_search(feedroom(), parse("cat"), by="source")
        assert groups[0].key == "newsletter"
        assert groups[0].representative_score >= groups[-1].representative_score

    def test_missing_keys_form_singletons_not_a_family(self):
        groups = collapse_search(feedroom(), parse("cat"), by="source")
        singles = [group for group in groups if group.key is None]
        assert len(singles) == 1
        assert singles[0].folded == ()

    def test_nothing_is_deleted_only_tucked(self):
        groups = collapse_search(feedroom(), parse("cat"), by="source")
        shown = {group.representative for group in groups}
        folded = {
            external
            for group in groups
            for external in group.folded
        }
        assert shown | folded == {0, 1, 2, 3, 4}

    def test_text_fields_refuse_collapsing(self):
        with pytest.raises(Invalid, match="by accident"):
            collapse_search(feedroom(), parse("cat"), by="body")

    def test_zero_limits_are_refused(self):
        with pytest.raises(Invalid):
            collapse_search(feedroom(), parse("cat"), by="source", limit=0)


class TestTheReport:
    def test_the_report_counts_what_it_folded(self):
        groups = collapse_search(feedroom(), parse("cat"), by="source")
        page = collapse_report(groups, "source")
        assert page.splitlines()[0] == "collapsed by source: 3 group(s)"
        assert "and 2 more" in page
        assert "(no key)" in page
