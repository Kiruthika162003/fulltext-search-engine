from __future__ import annotations

import pytest

from quarry.errors import Invalid, Missing
from quarry.multilang import (
    LanguagePack,
    LanguageRegistry,
    standard_registry,
)


class TestPacks:
    def test_each_language_drops_its_own_stopwords(self):
        registry = standard_registry()
        _, german = registry.analyze("de", "der Hund und die Katze")
        assert german == ["hund", "katze"]
        _, english = registry.analyze("en", "the dog and the cat")
        assert english == ["dog", "cat"]

    def test_german_is_not_stemmed_by_english_rules(self):
        registry = standard_registry()
        _, terms = registry.analyze("de", "Wolken ziehen")
        assert terms == ["wolken", "ziehen"]

    def test_the_tag_used_is_stamped_on_the_result(self):
        tag, _ = standard_registry().analyze("en-GB", "colour charts")
        assert tag == "en"


class TestTheRegistry:
    def test_unregistered_tags_never_fall_back(self):
        with pytest.raises(Missing, match="extra steps"):
            standard_registry().analyze("sv", "svenska ord")

    def test_the_refusal_lists_what_is_registered(self):
        with pytest.raises(Missing, match="de, en, fr"):
            standard_registry().pack_for("nl")

    def test_bad_tags_are_refused_at_registration(self):
        with pytest.raises(Invalid, match="primary subtag"):
            LanguageRegistry().register(
                LanguagePack(
                    tag="English",
                    stopwords=frozenset(),
                    stems=False,
                )
            )

    def test_languages_are_not_quietly_replaced(self):
        registry = standard_registry()
        with pytest.raises(Invalid, match="quietly replaced"):
            registry.register(
                LanguagePack(
                    tag="en", stopwords=frozenset(), stems=False
                )
            )

    def test_aliases_need_a_registered_target(self):
        with pytest.raises(Missing, match="before its variants"):
            LanguageRegistry().alias("pt-br", "pt")


class TestAgreement:
    def test_matching_sides_agree(self):
        verdict = standard_registry().agreement_check("en-US", "en")
        assert verdict == "both sides speak en"

    def test_mismatched_sides_are_refused(self):
        with pytest.raises(Invalid, match="must agree on language"):
            standard_registry().agreement_check("de", "fr")
