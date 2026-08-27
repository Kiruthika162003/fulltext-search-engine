from __future__ import annotations

import pytest

from quarry.errors import Invalid, Missing
from quarry.watchdog import Watchdog


def kennel() -> Watchdog:
    dog = Watchdog()
    dog.register("indexer", cadence_ticks=10, now=0)
    dog.register("merger", cadence_ticks=100, now=0)
    return dog


class TestRegistration:
    def test_duplicate_registration_is_the_half_beat_bug(self):
        dog = kennel()
        with pytest.raises(Invalid, match="one healthy whole"):
            dog.register("indexer", cadence_ticks=10, now=5)

    def test_zero_cadences_beat_never(self):
        with pytest.raises(Invalid, match="beats never"):
            Watchdog().register("mute", cadence_ticks=0, now=0)

    def test_strangers_cannot_beat(self):
        with pytest.raises(Missing, match="stranger"):
            kennel().beat("ghost", now=5)


class TestPatrol:
    def test_healthy_components_stay_off_the_report(self):
        dog = kennel()
        dog.beat("indexer", now=9)
        assert dog.patrol(now=12) == []

    def test_one_quiet_beat_is_a_hiccup(self):
        dog = kennel()
        findings = dog.patrol(now=15)
        assert findings == [
            "indexer: 1 beat(s) quiet; networks hiccup, watching"
        ]

    def test_three_silent_beats_alarm(self):
        dog = kennel()
        findings = dog.patrol(now=35)
        assert any("ALARM" in line for line in findings)

    def test_cadences_are_judged_per_component(self):
        dog = kennel()
        findings = dog.patrol(now=35)
        assert not any("merger" in line for line in findings)

    def test_a_standing_alarm_does_not_repeat_itself(self):
        dog = kennel()
        dog.patrol(now=35)
        findings = dog.patrol(now=45)
        assert any("still silent" in line for line in findings)


class TestReturns:
    def test_the_returned_carry_their_outage(self):
        dog = kennel()
        dog.patrol(now=35)
        message = dog.beat("indexer", now=40)
        assert "outage is on the record" in message
        record = dog.record("indexer")
        assert "returned at tick 40 after 4 silent beat(s)" in record

    def test_a_clean_record_says_so(self):
        assert kennel().record("merger") == (
            "merger: no outages on record"
        )

    def test_health_resumes_after_the_return(self):
        dog = kennel()
        dog.patrol(now=35)
        dog.beat("indexer", now=40)
        assert dog.patrol(now=45) == []
        assert dog.beat("indexer", now=48) == "indexer healthy"
