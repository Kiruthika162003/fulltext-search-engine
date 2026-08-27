from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.langsniff import LanguageSniffer


class TestSniffing:
    def test_english_announces_itself(self):
        sniff = LanguageSniffer().sniff(
            "the cat sat on the mat and it was warm"
        )
        assert sniff.language == "english"
        assert sniff.confident()

    def test_german_announces_itself(self):
        sniff = LanguageSniffer().sniff(
            "der Hund ist ein guter Freund und er wird geliebt"
        )
        assert sniff.language == "german"

    def test_french_announces_itself(self):
        sniff = LanguageSniffer().sniff(
            "le chat est dans la maison et il ne sort pas"
        )
        assert sniff.language == "french"


class TestRefusalsToGuess:
    def test_short_texts_are_too_short_to_call(self):
        sniff = LanguageSniffer().sniff("black cat")
        assert not sniff.confident()
        assert "too short" in sniff.reason

    def test_product_codes_are_not_estonian(self):
        sniff = LanguageSniffer().sniff(
            "SKU-2231 SKU-9987 REF-1002 LOT-777A BATCH-99"
        )
        assert not sniff.confident()
        assert "nobody registered" in sniff.reason

    def test_a_thin_margin_declines_the_call(self):
        sniff = LanguageSniffer().sniff(
            "le la des und der die it was"
        )
        assert not sniff.confident()
        assert "too thin" in sniff.reason


class TestRegistration:
    def test_new_languages_join_the_lineup(self):
        sniffer = LanguageSniffer()
        sniffer.register(
            "dutch",
            frozenset(
                "de het een en van is dat op te zijn met voor".split()
            ),
        )
        sniff = sniffer.sniff("de kat is op het dak en het is warm")
        assert sniff.language == "dutch"

    def test_tiny_word_lists_are_refused(self):
        with pytest.raises(Invalid, match="cannot carry"):
            LanguageSniffer().register(
                "klingon", frozenset({"qapla"})
            )

    def test_double_registration_is_refused(self):
        with pytest.raises(Invalid):
            LanguageSniffer().register(
                "english", frozenset("a b c d e f g h i j k".split())
            )
