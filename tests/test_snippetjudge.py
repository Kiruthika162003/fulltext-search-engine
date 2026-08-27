from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.snippetjudge import judge_snippet, sweep

SOURCE = (
    "The copper kettle sat on the stove all winter. Nobody "
    "polished it, and the handle wore smooth with use."
)


class TestJudging:
    def test_a_good_snippet_scores_on_all_axes(self):
        grade = judge_snippet(
            "The copper kettle sat on the stove",
            SOURCE,
            ["copper", "kettle"],
        )
        assert grade.coverage == 1.0
        assert grade.anchored
        assert grade.density == 1.0
        assert not grade.below_par()

    def test_missing_terms_sink_coverage(self):
        grade = judge_snippet(
            "Nobody polished it",
            SOURCE,
            ["copper", "kettle"],
        )
        assert grade.coverage == 0.0
        assert grade.below_par()

    def test_mid_token_windows_are_named(self):
        grade = judge_snippet(
            "ettle sat on the stove",
            SOURCE,
            ["stove"],
        )
        assert not grade.anchored
        assert "MID-TOKEN" in grade.line()

    def test_the_grade_is_the_weakest_axis(self):
        grade = judge_snippet(
            "ettle sat on the stove",
            SOURCE,
            ["stove"],
        )
        assert grade.coverage == 1.0
        assert grade.weakest() == 0.0

    def test_paraphrases_grade_the_wrong_artifact(self):
        with pytest.raises(Invalid, match="paraphrase"):
            judge_snippet(
                "A copper pot sat around",
                SOURCE,
                ["copper"],
            )

    def test_empty_inputs_are_refused(self):
        with pytest.raises(Invalid, match="judges nothing"):
            judge_snippet("The copper", SOURCE, [])
        with pytest.raises(Invalid, match="previews nothing"):
            judge_snippet("   ", SOURCE, ["copper"])


class TestTheSweep:
    def test_a_bad_batch_points_at_the_highlighter(self):
        grades = [
            judge_snippet("Nobody polished it", SOURCE, ["kettle"]),
            judge_snippet(
                "The copper kettle sat", SOURCE, ["kettle"]
            ),
        ]
        page = sweep(grades)
        assert page.startswith("1 of 2 snippets below par (50%)")
        assert "highlighter needs work" in page

    def test_a_healthy_batch_stays_calm(self):
        grades = [
            judge_snippet(
                "The copper kettle sat", SOURCE, ["kettle"]
            )
            for _ in range(5)
        ]
        assert "pulling their weight" in sweep(grades)

    def test_sweeping_nothing_is_refused(self):
        with pytest.raises(Invalid, match="sweeps nothing"):
            sweep([])
