from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.privacy import ScrubbingLog, scrub


class TestScrubbing:
    def test_emails_become_typed_markers(self):
        cleaned = scrub("find mail from ada.lovelace+notes@example.org")
        assert cleaned.text == "find mail from [email]"
        assert cleaned.emails == 1

    def test_phone_shaped_runs_are_masked(self):
        cleaned = scrub("call me on +44 20 7946 0958 tomorrow")
        assert "[phone]" in cleaned.text
        assert "0958" not in cleaned.text

    def test_card_shaped_runs_are_masked_before_phones(self):
        cleaned = scrub("charge 4111 1111 1111 1111 please")
        assert cleaned.text == "charge [card] please"
        assert cleaned.cards == 1
        assert cleaned.phones == 0

    def test_ordinary_queries_pass_untouched(self):
        cleaned = scrub("black cat sightings 2024")
        assert cleaned.text == "black cat sightings 2024"
        assert not cleaned.touched()

    def test_the_shape_of_the_query_survives(self):
        cleaned = scrub("emails to a@b.co and c@d.co about rent")
        assert cleaned.text == "emails to [email] and [email] about rent"
        assert cleaned.emails == 2

    def test_scrubbing_nothing_is_refused(self):
        with pytest.raises(Invalid):
            scrub("")


class TestTheLog:
    def test_the_log_never_holds_a_raw_email(self):
        log = ScrubbingLog()
        log.log("mail for grace@navy.mil")
        log.log("weather tomorrow")
        assert not log.contains_raw_email()
        assert log.rows[0] == "mail for [email]"

    def test_the_drift_report_counts_what_arrived(self):
        log = ScrubbingLog()
        log.log("mail for grace@navy.mil")
        log.log("call +1 555 867 5309 now")
        log.log("plain query")
        report = log.drift_report()
        assert report.startswith("3 rows, 66.7% carried personal data")
        assert "email: 1" in report
        assert "phone: 1" in report

    def test_an_empty_log_refuses_the_report(self):
        with pytest.raises(Invalid):
            ScrubbingLog().drift_report()
