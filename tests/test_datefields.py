from __future__ import annotations

import pytest

from quarry.datefields import DateParser, from_epoch_days, to_epoch_days
from quarry.errors import Invalid


class TestEpochDays:
    def test_the_epoch_is_day_zero(self):
        assert to_epoch_days(1970, 1, 1) == 0
        assert to_epoch_days(1970, 1, 2) == 1

    def test_the_round_trip_holds(self):
        days = to_epoch_days(2024, 3, 4)
        assert from_epoch_days(days) == "2024-03-04"

    def test_impossible_dates_are_named(self):
        with pytest.raises(Invalid, match="not a date"):
            to_epoch_days(2023, 2, 29)


class TestParsing:
    def test_the_three_shapes_all_land_on_one_day(self):
        parser = DateParser()
        expected = to_epoch_days(2024, 3, 4)
        assert parser.parse("2024-03-04") == expected
        assert parser.parse("20240304") == expected
        assert parser.parse("2024/03/04") == expected

    def test_the_tally_shows_format_drift(self):
        parser = DateParser()
        parser.parse("2024-03-04")
        parser.parse("2024-03-05")
        parser.parse("20240304")
        assert parser.drift_tally() == "formats seen: compact: 1, iso: 2"

    def test_unknown_shapes_list_what_was_tried(self):
        with pytest.raises(Invalid, match="formats tried"):
            DateParser().parse("4th of March, 2024")

    def test_emptiness_is_not_a_date(self):
        with pytest.raises(Invalid):
            DateParser().parse("   ")


class TestAmbiguity:
    def test_the_two_faced_slash_is_refused_by_name(self):
        with pytest.raises(Invalid, match="birthdays move"):
            DateParser().parse("04/03/2024")

    def test_an_unambiguous_slash_parses(self):
        parser = DateParser()
        assert parser.parse("25/03/2024") == to_epoch_days(2024, 3, 25)

    def test_the_same_number_twice_is_not_ambiguous(self):
        parser = DateParser()
        assert parser.parse("03/03/2024") == to_epoch_days(2024, 3, 3)

    def test_year_first_slashes_never_ambiguate(self):
        parser = DateParser()
        assert parser.parse("2024/04/03") == to_epoch_days(2024, 4, 3)
