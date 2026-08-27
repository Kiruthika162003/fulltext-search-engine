from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.queryclassify import POLICY, classify


class TestNavigational:
    def test_short_rare_queries_lean_navigational(self):
        intent = classify(
            terms=["acme", "dashboard"],
            has_phrase=False,
            has_field_prefix=False,
            rarest_document_frequency=2,
        )
        assert intent.label == "navigational"

    def test_phrases_signal_precision(self):
        intent = classify(
            terms=[],
            has_phrase=True,
            has_field_prefix=False,
            rarest_document_frequency=10,
        )
        assert intent.label == "navigational"
        assert any(
            "quoted phrase" in signal.name
            for signal in intent.signals
        )


class TestLookup:
    def test_question_words_signal_lookup(self):
        intent = classify(
            terms=["how", "reset", "password"],
            has_phrase=False,
            has_field_prefix=False,
            rarest_document_frequency=20,
        )
        assert intent.label == "lookup"

    def test_no_signals_default_to_lookup(self):
        intent = classify(
            terms=["kettle", "copper", "review"],
            has_phrase=False,
            has_field_prefix=False,
            rarest_document_frequency=20,
        )
        assert intent.label == "lookup"
        assert intent.signals[0].name == "no strong signals"


class TestExploratory:
    def test_long_generic_queries_lean_exploratory(self):
        intent = classify(
            terms="ideas for small garden spring planting".split(),
            has_phrase=False,
            has_field_prefix=False,
            rarest_document_frequency=80,
        )
        assert intent.label == "exploratory"


class TestExplainability:
    def test_the_verdict_shows_its_signals(self):
        intent = classify(
            terms=["acme"],
            has_phrase=False,
            has_field_prefix=True,
            rarest_document_frequency=1,
        )
        page = intent.explain()
        assert "field prefix -> navigational" in page
        assert page.endswith(
            f"verdict: navigational ({POLICY['navigational']})"
        )

    def test_every_class_carries_a_policy(self):
        assert set(POLICY) == {
            "navigational",
            "lookup",
            "exploratory",
        }

    def test_empty_queries_have_no_intent(self):
        with pytest.raises(Invalid, match="no intent"):
            classify(
                terms=[],
                has_phrase=False,
                has_field_prefix=False,
                rarest_document_frequency=0,
            )
