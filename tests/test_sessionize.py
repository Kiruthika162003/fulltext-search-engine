from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.sessionize import (
    SearchEvent,
    Sessionizer,
    threshold_sensitivity,
)


def burst(user: str, start: int, queries: list[tuple[str, bool]]):
    return [
        SearchEvent(
            user=user, at=start + offset, query=text, clicked=clicked
        )
        for offset, (text, clicked) in enumerate(queries)
    ]


class TestSplitting:
    def test_silence_closes_the_session(self):
        splitter = Sessionizer(idle_gap=30)
        for event in burst("ada", 0, [("cat", False), ("cat food", True)]):
            splitter.observe(event)
        for event in burst("ada", 100, [("weather", True)]):
            splitter.observe(event)
        sessions = splitter.close_all()
        assert len(sessions) == 2
        assert sessions[0].queries == ("cat", "cat food")
        assert sessions[1].queries == ("weather",)

    def test_activity_inside_the_gap_stays_one_session(self):
        splitter = Sessionizer(idle_gap=30)
        for event in burst("ada", 0, [("a", False)]):
            splitter.observe(event)
        splitter.observe(
            SearchEvent(user="ada", at=25, query="b", clicked=True)
        )
        assert len(splitter.close_all()) == 1

    def test_users_never_share_sessions(self):
        splitter = Sessionizer()
        splitter.observe(
            SearchEvent(user="ada", at=0, query="cat", clicked=False)
        )
        splitter.observe(
            SearchEvent(user="grace", at=1, query="dog", clicked=True)
        )
        sessions = splitter.close_all()
        assert {session.user for session in sessions} == {"ada", "grace"}

    def test_disorder_names_the_two_device_suspicion(self):
        splitter = Sessionizer()
        splitter.observe(
            SearchEvent(user="ada", at=50, query="cat", clicked=False)
        )
        with pytest.raises(Invalid, match="two devices"):
            splitter.observe(
                SearchEvent(user="ada", at=10, query="dog", clicked=False)
            )

    def test_every_session_carries_its_gap(self):
        splitter = Sessionizer(idle_gap=45)
        splitter.observe(
            SearchEvent(user="ada", at=0, query="cat", clicked=True)
        )
        assert splitter.close_all()[0].gap_used == 45


class TestSuccess:
    def test_success_is_the_last_query_clicked(self):
        splitter = Sessionizer()
        for event in burst(
            "ada", 0, [("cat", True), ("cat gone wrong", False)]
        ):
            splitter.observe(event)
        assert splitter.close_all()[0].succeeded is False

    def test_the_rate_counts_closed_sessions(self):
        splitter = Sessionizer(idle_gap=10)
        for event in burst("ada", 0, [("cat", True)]):
            splitter.observe(event)
        for event in burst("grace", 0, [("dog", False)]):
            splitter.observe(event)
        splitter.close_all()
        assert splitter.success_rate() == 0.5

    def test_no_sessions_refuses_the_rate(self):
        with pytest.raises(Invalid):
            Sessionizer().success_rate()


class TestSensitivity:
    def test_the_report_shows_the_threshold_shaping_the_count(self):
        events = burst("ada", 0, [("a", False)]) + burst(
            "ada", 20, [("b", True)]
        )
        page = threshold_sensitivity(events, gaps=(10, 30))
        assert "gap 10: 2 session(s)" in page
        assert "gap 30: 1 session(s)" in page

    def test_no_candidates_informs_nothing(self):
        with pytest.raises(Invalid):
            threshold_sensitivity([], gaps=())
