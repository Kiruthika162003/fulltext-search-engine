from __future__ import annotations

import pytest

from quarry.checkdigit import stamp, verify
from quarry.errors import Invalid


class TestStamping:
    def test_the_round_trip_holds_for_many_ids(self):
        for external in (0, 7, 42, 12345, 999_999):
            assert verify(stamp(external)) == external

    def test_the_classic_luhn_example_checks_out(self):
        assert verify("79927398713") == 7992739871

    def test_negative_ids_are_nobody(self):
        with pytest.raises(Invalid, match="nobody"):
            stamp(-1)


class TestTheTripwire:
    def test_a_single_slip_is_caught(self):
        stamped = stamp(12345)
        slipped = "9" + stamped[1:]
        with pytest.raises(Invalid, match="slip or a"):
            verify(slipped)

    def test_an_adjacent_transposition_is_caught(self):
        stamped = stamp(12345)
        swapped = stamped[1] + stamped[0] + stamped[2:]
        with pytest.raises(Invalid, match="transposition"):
            verify(swapped)

    def test_unstamped_ids_are_refused_not_guessed(self):
        with pytest.raises(Invalid, match="not a stamped id"):
            verify("x123")
        with pytest.raises(Invalid, match="not a stamped id"):
            verify("7")
