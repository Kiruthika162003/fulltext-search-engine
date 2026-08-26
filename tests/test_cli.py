from __future__ import annotations

from quarry.cli import main


class TestCli:
    def test_evals_prints_the_grades(self, capsys):
        assert main(["evals"]) == 0
        out = capsys.readouterr().out
        assert "rarewins" in out
        assert "0 broken" in out

    def test_check_passes_while_everything_holds(self, capsys):
        assert main(["check"]) == 0
        assert "all evals hold" in capsys.readouterr().out

    def test_search_answers_from_the_shell(self, capsys):
        assert main(["search", '"black cat"']) == 0
        out = capsys.readouterr().out
        assert 'query: body:"black cat"' in out
        assert "doc 0" in out

    def test_a_miss_offers_the_correction(self, capsys):
        assert main(["search", "catz"]) == 0
        out = capsys.readouterr().out
        assert "did you mean: cat" in out
