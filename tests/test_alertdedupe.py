from __future__ import annotations

import pytest

from quarry.alertdedupe import AlertDeduper
from quarry.errors import Invalid, Missing


class TestGrouping:
    def test_one_incident_one_page(self):
        deduper = AlertDeduper()
        first = deduper.signal("hot-shard-a", "latency p95 up", 1)
        second = deduper.signal("hot-shard-a", "queue depth up", 2)
        third = deduper.signal("hot-shard-a", "error rate up", 3)
        assert "page sent" in first
        assert "attached as evidence" in second
        assert "attached as evidence" in third
        assert len(deduper.pages_sent) == 1

    def test_different_causes_page_separately(self):
        deduper = AlertDeduper()
        deduper.signal("hot-shard-a", "latency", 1)
        deduper.signal("dead-replica-c", "no heartbeat", 2)
        assert len(deduper.pages_sent) == 2

    def test_keyless_alerts_cannot_group(self):
        with pytest.raises(Invalid, match="cannot be grouped"):
            AlertDeduper().signal("  ", "mystery", 1)


class TestFlapping:
    def test_a_flap_reuses_its_incident(self):
        deduper = AlertDeduper()
        deduper.signal("hot-shard-a", "latency", 1)
        deduper.clear("hot-shard-a", 5)
        message = deduper.signal("hot-shard-a", "latency again", 20)
        assert "flapped back open" in message
        assert len(deduper.pages_sent) == 1

    def test_a_return_after_the_cooldown_is_new(self):
        deduper = AlertDeduper()
        deduper.signal("hot-shard-a", "latency", 1)
        deduper.clear("hot-shard-a", 5)
        message = deduper.signal("hot-shard-a", "latency", 100)
        assert "incident opened" in message
        assert len(deduper.pages_sent) == 2

    def test_clearing_the_unopened_is_named(self):
        with pytest.raises(Missing, match="wrong key"):
            AlertDeduper().clear("ghost", 1)


class TestEscalation:
    def test_suppression_is_bounded(self):
        deduper = AlertDeduper()
        deduper.signal("hot-shard-a", "signal 0", 0)
        for n in range(1, 4):
            deduper.signal("hot-shard-a", f"signal {n}", n)
        message = deduper.signal("hot-shard-a", "signal 4", 4)
        assert "re-paged at higher urgency" in message
        assert any(
            page.startswith("ESCALATE") for page in deduper.pages_sent
        )

    def test_escalation_happens_once(self):
        deduper = AlertDeduper()
        for n in range(8):
            deduper.signal("hot-shard-a", f"signal {n}", n)
        escalations = [
            page
            for page in deduper.pages_sent
            if page.startswith("ESCALATE")
        ]
        assert len(escalations) == 1


class TestTheLedger:
    def test_closing_reports_the_absorption(self):
        deduper = AlertDeduper()
        deduper.signal("hot-shard-a", "latency", 1)
        deduper.signal("hot-shard-a", "queue", 2)
        message = deduper.clear("hot-shard-a", 9)
        assert message.endswith("absorbed 2 signal(s)")

    def test_the_noisiest_cause_is_named(self):
        deduper = AlertDeduper()
        for n in range(3):
            deduper.signal("hot-shard-a", f"s{n}", n)
        deduper.clear("hot-shard-a", 10)
        deduper.signal("dead-replica-c", "quiet", 20)
        deduper.clear("dead-replica-c", 21)
        page = deduper.noisiest()
        assert page.startswith("noisiest cause: hot-shard-a with 3")
