from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.runbook import Execution, Runbook, Step


def hot_shard_book() -> Runbook:
    return Runbook(
        name="hot-shard",
        trigger="one shard past twice the fleet median",
        steps=(
            Step(
                instruction="confirm heat with the shard census",
                verify_by="census shows the named shard hot",
                escalate_to="search-oncall-secondary",
            ),
            Step(
                instruction="apply the cooling plan's first move",
                verify_by="projected load under threshold",
                escalate_to="search-lead",
            ),
        ),
    )


class TestDeclaration:
    def test_unverifiable_steps_are_prayers(self):
        with pytest.raises(Invalid, match="prayer"):
            Step(
                instruction="restart something",
                verify_by="  ",
                escalate_to="anyone",
            )

    def test_steplessness_is_a_sympathy_card(self):
        with pytest.raises(Invalid, match="sympathy card"):
            Runbook(name="empty", trigger="anything", steps=())

    def test_triggers_are_mandatory(self):
        with pytest.raises(Invalid, match="when to open"):
            Runbook(
                name="lost",
                trigger=" ",
                steps=hot_shard_book().steps,
            )


class TestExecution:
    def test_the_happy_path_walks_to_completion(self):
        run = Execution(runbook=hot_shard_book(), operator="kiru")
        message = run.report_outcome("worked")
        assert message.startswith("next: apply the cooling plan")
        message = run.report_outcome("worked")
        assert "runbook complete" in message
        assert run.closed

    def test_failure_names_who_to_wake(self):
        run = Execution(runbook=hot_shard_book(), operator="kiru")
        message = run.report_outcome("failed")
        assert "wake search-oncall-secondary" in message
        assert run.closed

    def test_skips_demand_reasons(self):
        run = Execution(runbook=hot_shard_book(), operator="kiru")
        with pytest.raises(Invalid, match="say why"):
            run.report_outcome("skipped")
        message = run.report_outcome(
            "skipped", note="census already confirmed by alert"
        )
        assert message.startswith("next:")

    def test_closed_executions_stay_closed(self):
        run = Execution(runbook=hot_shard_book(), operator="kiru")
        run.report_outcome("failed")
        with pytest.raises(Invalid, match="open another"):
            run.current_step()

    def test_unknown_outcomes_list_the_choices(self):
        run = Execution(runbook=hot_shard_book(), operator="kiru")
        with pytest.raises(Invalid, match="worked, failed, skipped"):
            run.report_outcome("shrugged")


class TestTheTranscript:
    def test_the_journal_survives_for_the_review(self):
        run = Execution(runbook=hot_shard_book(), operator="kiru")
        run.report_outcome("worked")
        run.report_outcome("failed", note="load stayed high")
        page = run.transcript()
        assert page.startswith("hot-shard run by kiru")
        assert "step 1 worked" in page
        assert "step 2 failed (load stayed high)" in page
        assert "escalate to search-lead" in page
