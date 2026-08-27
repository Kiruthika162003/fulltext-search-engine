from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.phonetic import PhoneticIndex, code, sound_alike


class TestCoding:
    def test_the_classic_smith_case(self):
        assert code("Smith") == code("Smyth") == "S530"

    def test_keys_are_fixed_width(self):
        assert code("Lee") == "L000"
        assert code("Kettleworth") == "K346"

    def test_doubled_consonants_are_one_sound(self):
        assert code("Jansen") == code("Janssen")

    def test_vowels_survive_only_as_the_first_letter(self):
        assert code("Adams")[0] == "A"
        assert sound_alike("Adams", "Addams")

    def test_different_sounds_stay_apart(self):
        assert not sound_alike("Smith", "Baker")

    def test_silence_has_no_sound(self):
        with pytest.raises(Invalid, match="no sound"):
            code("...")


class TestTheIndex:
    def stocked(self) -> PhoneticIndex:
        held = PhoneticIndex()
        for name in ("Smith", "Smyth", "Baker", "Jansen", "Janssen"):
            held.admit(name)
        return held

    def test_candidates_are_offered_never_merged(self):
        held = self.stocked()
        assert held.candidates("Smith") == ["Smyth"]
        assert held.candidates("Baker") == []

    def test_readmission_is_calm(self):
        held = self.stocked()
        held.admit("Smith")
        assert held.candidates("Smyth") == ["Smith"]

    def test_the_report_names_the_crowded_keys(self):
        page = self.stocked().collision_report()
        assert "S530: Smith, Smyth" in page
        assert "anglophone" in page

    def test_a_quiet_index_stays_suspicious(self):
        held = PhoneticIndex()
        held.admit("Baker")
        assert "suspiciously careful" in held.collision_report()
