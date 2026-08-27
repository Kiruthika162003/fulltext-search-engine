from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.unitparse import (
    parse_bytes,
    parse_count,
    parse_duration_ms,
)


class TestCounts:
    def test_decimal_thousands_mean_what_they_say(self):
        assert parse_count("10k") == 10_000
        assert parse_count("2.5m") == 2_500_000
        assert parse_count("1B") == 1_000_000_000
        assert parse_count("42") == 42

    def test_half_a_document_does_not_exist(self):
        with pytest.raises(Invalid, match="does not exist"):
            parse_count("2.5")

    def test_binary_suffixes_are_taught_away(self):
        with pytest.raises(Invalid, match="powers of two"):
            parse_count("10kib")


class TestBytes:
    def test_disks_are_bought_in_the_units_disks_lie_in(self):
        assert parse_bytes("512b") == 512
        assert parse_bytes("4KiB") == 4096
        assert parse_bytes("1.5MiB") == 1_572_864

    def test_the_i_must_be_spelled_out(self):
        with pytest.raises(Invalid, match="spelled out"):
            parse_bytes("4kb")

    def test_fractional_bytes_are_refused(self):
        with pytest.raises(Invalid, match="between bytes"):
            parse_bytes("0.3b")


class TestDurations:
    def test_every_unit_lands_in_milliseconds(self):
        assert parse_duration_ms("300ms") == 300
        assert parse_duration_ms("2s") == 2000
        assert parse_duration_ms("1.5m") == 90_000
        assert parse_duration_ms("1h") == 3_600_000

    def test_bare_timeouts_are_thirty_of_what(self):
        with pytest.raises(Invalid, match="thirty of what"):
            parse_duration_ms("30")

    def test_half_milliseconds_do_not_tick(self):
        with pytest.raises(Invalid, match="does not tick"):
            parse_duration_ms("0.5ms")


class TestForgivingShapes:
    def test_case_and_padding_are_shrugged_off(self):
        assert parse_count(" 10K ") == 10_000
        assert parse_bytes(" 4kib") == 4096
        assert parse_duration_ms("2S ") == 2000

    def test_inner_spaces_before_the_suffix_survive(self):
        assert parse_count("10 k") == 10_000
        assert parse_duration_ms("300 ms") == 300

    def test_clean_fractions_of_big_units_divide_out(self):
        assert parse_count("0.5k") == 500
        assert parse_bytes("0.5kib") == 512
        assert parse_duration_ms("0.25s") == 250


class TestTheDoor:
    def test_emptiness_is_not_a_quantity(self):
        with pytest.raises(Invalid, match="not a quantity"):
            parse_count("   ")

    def test_numberless_strings_are_named(self):
        with pytest.raises(Invalid, match="no number"):
            parse_count("many")

    def test_broken_decimals_are_not_numbers(self):
        with pytest.raises(Invalid, match="not a number"):
            parse_count("1.2.3k")
