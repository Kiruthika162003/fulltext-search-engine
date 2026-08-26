from __future__ import annotations

from examples import librarian


class TestLibrarian:
    def test_the_desk_day_reads_end_to_end(self, capsys):
        assert librarian.main() == 0
        out = capsys.readouterr().out
        assert "The Black [Cat] Mysteries" in out
        assert "Cathedral" not in out
        assert "shelf: fiction (1), history (1), reference (1) and 1 more" in out
        assert "[2010, 2020): 2" in out
        assert "typo path: title:cat" in out
