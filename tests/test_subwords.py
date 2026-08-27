from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.subwords import expand_token, split_identifier, split_report


class TestSplitting:
    def test_camel_case_splits_at_the_case_seam(self):
        assert split_identifier("getUserName") == ["get", "User", "Name"]

    def test_snake_and_kebab_split_at_separators(self):
        assert split_identifier("snake_case_config") == [
            "snake",
            "case",
            "config",
        ]
        assert split_identifier("kebab-case-name") == [
            "kebab",
            "case",
            "name",
        ]

    def test_the_acronym_run_keeps_its_shape(self):
        assert split_identifier("HTTPResponse2") == [
            "HTTP",
            "Response",
            "2",
        ]
        assert split_identifier("XMLHttpRequest") == [
            "XML",
            "Http",
            "Request",
        ]

    def test_digit_seams_split_both_ways(self):
        assert split_identifier("v2Migration") == ["v", "2", "Migration"]
        assert split_identifier("area51zone") == ["area", "51", "zone"]

    def test_plain_words_stay_whole(self):
        assert split_identifier("plain") == ["plain"]

    def test_emptiness_is_philosophy(self):
        with pytest.raises(Invalid, match="philosophy"):
            split_identifier("")


class TestExpansion:
    def test_the_whole_token_leads_the_parts(self):
        assert expand_token("getUserName") == [
            "getusername",
            "get",
            "user",
            "name",
        ]

    def test_duplicates_collapse_after_lowering(self):
        assert expand_token("plain") == ["plain"]
        assert expand_token("NameName") == ["namename", "name"]


class TestTheReport:
    def test_the_report_reads_arrow_by_arrow(self):
        report = split_report(["getUserName", "HTTPResponse2"])
        assert report.splitlines() == [
            "getUserName -> get + User + Name",
            "HTTPResponse2 -> HTTP + Response + 2",
        ]

    def test_no_identifiers_is_refused(self):
        with pytest.raises(Invalid):
            split_report([])
