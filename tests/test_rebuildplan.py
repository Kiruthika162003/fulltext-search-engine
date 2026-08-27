from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.rebuildplan import (
    SegmentStatus,
    bridge_page,
    plan_rebuild,
)


def bad_morning() -> list[SegmentStatus]:
    return [
        SegmentStatus(name="alpha", verified=True, live_docs=500),
        SegmentStatus(name="beta", verified=False, live_docs=2000),
        SegmentStatus(name="gamma", verified=False, live_docs=100),
        SegmentStatus(name="delta", verified=True, live_docs=400),
    ]


class TestThePlan:
    def test_healthy_segments_mount_first(self):
        steps = plan_rebuild(bad_morning(), journal_pending=0)
        assert steps[0].action == "mount"
        assert steps[1].action == "mount"
        assert {steps[0].target, steps[1].target} == {
            "alpha",
            "delta",
        }

    def test_rebuilds_go_smallest_first_for_early_wins(self):
        steps = plan_rebuild(bad_morning(), journal_pending=0)
        rebuilds = [
            step for step in steps if step.action == "rebuild"
        ]
        assert [step.target for step in rebuilds] == [
            "gamma",
            "beta",
        ]

    def test_the_journal_replays_after_the_rebuilds(self):
        steps = plan_rebuild(bad_morning(), journal_pending=7)
        actions = [step.action for step in steps]
        assert actions.index("replay") > actions.index("rebuild")
        assert "7 pending entrie(s)" in steps[-2].reason

    def test_every_plan_ends_in_a_verify(self):
        steps = plan_rebuild(bad_morning(), journal_pending=0)
        assert steps[-1].action == "verify"
        assert "rumor of a recovery" in steps[-1].reason

    def test_service_share_is_projected_per_step(self):
        steps = plan_rebuild(bad_morning(), journal_pending=0)
        assert "30% of corpus serving" in steps[1].reason
        assert "(33% serving after)" in steps[2].reason
        assert "(100% serving after)" in steps[3].reason

    def test_no_segments_is_a_different_outage(self):
        with pytest.raises(Invalid, match="different"):
            plan_rebuild([], journal_pending=0)


class TestTheBridge:
    def test_the_page_numbers_the_briefing(self):
        page = bridge_page(
            plan_rebuild(bad_morning(), journal_pending=3)
        )
        assert page.startswith("1. mount alpha")
        assert "2 rebuild(s)" in page
        assert page.endswith("the plan is the briefing")
