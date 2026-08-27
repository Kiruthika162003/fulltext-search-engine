from __future__ import annotations

import pytest

from quarry.coldstart import gate, may_speak, warming_report
from quarry.errors import Invalid, Missing


class TestGates:
    def test_search_is_ready_at_one_document(self):
        state = gate("search", 1)
        assert state.ready()
        assert state.line() == "search: ready (1/1)"

    def test_shortfalls_are_counted(self):
        state = gate("suggestions", 30)
        assert not state.ready()
        assert "20 more needed (30/50)" in state.line()

    def test_unknown_features_declare_no_floor(self):
        with pytest.raises(Missing, match="declares one"):
            gate("holograms", 5)

    def test_negative_counts_are_bugs(self):
        with pytest.raises(Invalid, match="counting bug"):
            gate("search", -1)


class TestSpeaking:
    def test_cold_suggestions_stay_silent(self):
        allowed, words = may_speak("suggestions", 3)
        assert not allowed
        assert "SILENT" in words
        assert "nothing beats a hedge" in words

    def test_cold_evals_warm_with_a_label(self):
        allowed, words = may_speak("relevance-evals", 40)
        assert not allowed
        assert "degraded output allowed, labeled" in words
        assert "160 short" in words

    def test_warm_features_speak_plainly(self):
        allowed, words = may_speak("trending", 800)
        assert allowed
        assert words == "trending speaks: past its floor"


class TestTheReport:
    def test_day_one_reads_as_arriving_not_broken(self):
        page = warming_report({"search": 3, "snippets": 3})
        assert "search: ready (3/1)" in page
        assert "suggestions: silent" in page
        assert "click-model: warming" in page
        assert page.endswith(
            "2 of 6 features ready; the rest are arriving, not "
            "broken"
        )

    def test_stray_features_are_refused(self):
        with pytest.raises(Invalid, match="the roster"):
            warming_report({"holograms": 9})
