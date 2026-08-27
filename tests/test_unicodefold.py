from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.unicodefold import fold, folding_report, folds_to_same


class TestFolding:
    def test_accents_strip_to_their_letters(self):
        assert fold("café") == "cafe"
        assert fold("naïve") == "naive"
        assert fold("Ångström") == "Angstrom"

    def test_ligatures_expand_where_decomposition_cannot(self):
        assert fold("encyclopædia") == "encyclopaedia"
        assert fold("straße") == "strasse"
        assert fold("Łódź") == "Lodz"

    def test_plain_ascii_passes_untouched(self):
        assert fold("plain words here") == "plain words here"

    def test_cyrillic_stays_cyrillic(self):
        assert fold("москва") == "москва"


class TestSameness:
    def test_the_keyboard_gap_closes(self):
        assert folds_to_same("café", "CAFE")
        assert folds_to_same("naïve", "naive")

    def test_different_words_stay_different(self):
        assert not folds_to_same("cafe", "cave")

    def test_emptiness_folds_nothing(self):
        with pytest.raises(Invalid):
            folds_to_same("", "cafe")


class TestTheReport:
    def test_families_collapse_visibly(self):
        report = folding_report(
            ["café", "cafe", "CAFE", "naive", "naïve", "table"]
        )
        assert "2 famil(ies) collapse" in report
        assert "cafe: CAFE, cafe, café" in report
        assert "naive: naive, naïve" in report

    def test_an_ascii_corpus_changes_nothing(self):
        report = folding_report(["plain", "words"])
        assert report == (
            "no spellings collapse; the fold changes nothing here"
        )

    def test_no_terms_is_refused(self):
        with pytest.raises(Invalid):
            folding_report([])
