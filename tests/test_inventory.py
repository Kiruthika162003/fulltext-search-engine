from __future__ import annotations

import pathlib

import pytest

from quarry.errors import Invalid
from quarry.inventory import catalog, gate, read_theses

QUARRY_DIR = str(
    pathlib.Path(__file__).resolve().parent.parent / "quarry"
)


class TestAgainstTheRealPackage:
    def test_every_quarry_module_states_its_thesis(self):
        message = gate(QUARRY_DIR)
        assert message.startswith("all ")
        assert message.endswith("modules state their thesis")

    def test_known_theses_read_back(self):
        theses = read_theses(QUARRY_DIR)
        assert theses["inventory"].startswith(
            "The module inventory"
        )
        assert "epoch days" in theses["datefields"]

    def test_the_catalog_counts_honestly(self):
        page = catalog(QUARRY_DIR)
        last = page.splitlines()[-1]
        assert last.endswith("0 without a thesis")


class TestAgainstFixtures:
    def test_missing_theses_are_listed_not_skipped(self, tmp_path):
        (tmp_path / "described.py").write_text(
            '"""A described module."""\n', encoding="utf-8"
        )
        (tmp_path / "mute.py").write_text(
            "x = 1\n", encoding="utf-8"
        )
        page = catalog(str(tmp_path))
        assert "described: A described module." in page
        assert "MISSING THESIS:" in page
        assert "  mute" in page
        assert page.endswith("2 module(s), 1 without a thesis")

    def test_the_gate_names_the_undescribed(self, tmp_path):
        (tmp_path / "mute.py").write_text("x = 1\n", encoding="utf-8")
        with pytest.raises(Invalid, match="does not know it yet"):
            gate(str(tmp_path))

    def test_dunder_files_are_not_modules_here(self, tmp_path):
        (tmp_path / "__init__.py").write_text("", encoding="utf-8")
        (tmp_path / "real.py").write_text(
            '"""Real."""\n', encoding="utf-8"
        )
        theses = read_theses(str(tmp_path))
        assert list(theses) == ["real"]

    def test_empty_directories_are_refused(self, tmp_path):
        with pytest.raises(Invalid, match="nothing is nothing"):
            read_theses(str(tmp_path))

    def test_missing_directories_are_refused(self):
        with pytest.raises(Invalid, match="not a directory"):
            read_theses("no/such/place")
