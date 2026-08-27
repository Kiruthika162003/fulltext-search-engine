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

    def test_health_runs_the_canary(self, capsys):
        assert main(["health"]) == 0
        out = capsys.readouterr().out
        assert out.startswith("overall: healthy")
        assert "found one canary" in out

    def test_summary_is_one_honest_line(self, capsys):
        assert main(["summary"]) == 0
        assert "evals (0 broken)" in capsys.readouterr().out

    def test_modules_prints_the_self_catalog(self, capsys):
        assert main(["modules"]) == 0
        out = capsys.readouterr().out
        assert "inventory: The module inventory" in out
        assert "0 without a thesis" in out

    def test_repair_mends_and_narrates(self, capsys):
        assert main(["repair", "body:cat OR"]) == 0
        out = capsys.readouterr().out
        assert out.startswith("body:cat\n")
        assert "searched with repairs" in out

    def test_repair_admits_defeat_honestly(self, capsys):
        assert main(["repair", "OR OR OR OR"]) == 1
        assert "beyond repair" in capsys.readouterr().out
