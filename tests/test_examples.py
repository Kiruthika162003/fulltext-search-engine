from __future__ import annotations

from examples import (
    codesearch,
    librarian,
    newsroom,
    relevancelab,
    searchops,
    storefront,
)


class TestLibrarian:
    def test_the_desk_day_reads_end_to_end(self, capsys):
        assert librarian.main() == 0
        out = capsys.readouterr().out
        assert "The Black [Cat] Mysteries" in out
        assert "Cathedral" not in out
        assert "shelf: fiction (1), history (1), reference (1) and 1 more" in out
        assert "[2010, 2020): 2" in out
        assert "typo path: title:cat" in out


class TestNewsroom:
    def test_the_wire_morning_reads_end_to_end(self, capsys):
        assert newsroom.main() == 0
        out = capsys.readouterr().out
        assert "story 0 fires: bridge-watch" in out
        assert "story 2 fires: storm-watch" in out
        assert "4 documents, 3 stories, 1 hidden as variants" in out
        assert (
            "synonym candidate: 'bridge collapse' -> 'bridge budget', "
            "3 sessions agree" in out
        )


class TestRelevanceLab:
    def test_the_lab_afternoon_reads_end_to_end(self, capsys):
        assert relevancelab.main() == 0
        out = capsys.readouterr().out
        assert "[holds] rarewins" in out
        assert "BROKEN" not in out
        assert "OR: 4 document(s)" in out
        assert "AND: 1 document(s)" in out
        assert "interleaving: right wins 5 to 0" in out


class TestSearchOps:
    def test_the_ops_afternoon_reads_end_to_end(self, capsys):
        assert searchops.main() == 0
        out = capsys.readouterr().out
        assert out.startswith("overall: degraded")
        assert "backlog 30/50, 10 admitted" in out
        assert "habitual: monday report slow 2 times, worst 800" in out
        assert "slowest seat multiplies latency by 10" in out
        assert "moved: queries_served: 0.0 -> 98.0 (+98 queries)" in out


class TestCodesearch:
    def test_the_code_hour_reads_end_to_end(self, capsys):
        assert codesearch.main() == 0
        out = capsys.readouterr().out
        assert "HTTPResponseCache -> HTTP + Response + Cache" in out
        assert "getUserName" in out
        assert "exact spelling ranks first: getUserName" in out

    def test_subword_queries_reach_camel_case(self):
        engine = codesearch.build_code_index()
        found = codesearch.search_symbols(engine, "user")
        assert "getUserName" in found
        assert "get_user_id" in found
        assert "renameUser" in found

    def test_cache_finds_both_spellings(self):
        engine = codesearch.build_code_index()
        found = codesearch.search_symbols(engine, "cache")
        assert set(found) == {"HTTPResponseCache", "purgeStaleCache"}


class TestStorefront:
    def test_the_storefront_hour_reads_end_to_end(self, capsys):
        assert storefront.main() == 0
        out = capsys.readouterr().out
        assert "+ fresh: 0.27991 (age 5, 0.1 half-lives)" in out
        assert "+ in-stock: 0.0 (stock='no', wanted 'yes')" in out
        assert "collapsed by brand: 3 group(s)" in out
        assert "acme: doc 0 (0.074108) and 2 more" in out
        assert "shopper-7 refused after 2 queries; retry in 1" in out
        assert "admissions: yyn" in out
