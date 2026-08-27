from __future__ import annotations

import pytest

from quarry.decay import DecayBook
from quarry.errors import Invalid


class TestDecaying:
    def test_a_weight_halves_over_its_half_life(self):
        book = DecayBook(half_life=100)
        book.bump("cats", now=0, by=8.0)
        assert book.read("cats", now=100) == 4.0
        assert book.read("cats", now=300) == 1.0

    def test_bumping_compounds_on_the_decayed_value(self):
        book = DecayBook(half_life=100)
        book.bump("cats", now=0, by=8.0)
        book.bump("cats", now=100, by=1.0)
        assert book.read("cats", now=100) == 5.0

    def test_the_unknown_reads_zero(self):
        assert DecayBook().read("ghost", now=50) == 0.0

    def test_backwards_clocks_are_refused(self):
        book = DecayBook()
        book.bump("cats", now=100)
        with pytest.raises(Invalid, match="clock went"):
            book.read("cats", now=50)


class TestTheStampTrap:
    def test_plain_reads_never_preserve(self):
        book = DecayBook(half_life=100)
        book.bump("cats", now=0, by=8.0)
        for tick in range(0, 100, 10):
            book.read("cats", now=tick)
        assert book.read("cats", now=100) == 4.0

    def test_a_refreshing_read_restarts_the_clock(self):
        book = DecayBook(half_life=100)
        book.bump("cats", now=0, by=8.0)
        book.read("cats", now=100, refresh_stamp=True)
        assert book.read("cats", now=200) == 2.0


class TestPruning:
    def test_the_floor_prunes_the_ghosts_and_counts_the_mass(self):
        book = DecayBook(half_life=10, noise_floor=0.01)
        book.bump("old", now=0, by=1.0)
        book.bump("fresh", now=100, by=5.0)
        pruned = book.prune(now=100)
        assert pruned == 1
        assert "old" not in book.weights
        assert book.pruned_mass > 0
        assert "decayed mass pruned" in book.ledger_line(now=100)

    def test_live_weights_survive_the_prune(self):
        book = DecayBook(half_life=100)
        book.bump("fresh", now=90, by=5.0)
        assert book.prune(now=100) == 0
        assert book.read("fresh", now=100) > 4.0


class TestTheTop:
    def test_the_top_ranks_by_decayed_value_not_raw(self):
        book = DecayBook(half_life=10)
        book.bump("has-been", now=0, by=100.0)
        book.bump("rising", now=95, by=5.0)
        top = book.top(now=100)
        assert top[0][0] == "rising"

    def test_zero_rows_are_refused(self):
        with pytest.raises(Invalid):
            DecayBook().top(now=0, limit=0)

    def test_bad_knobs_are_refused(self):
        with pytest.raises(Invalid):
            DecayBook(half_life=0)
        with pytest.raises(Invalid):
            DecayBook(noise_floor=0.0)
        with pytest.raises(Invalid):
            DecayBook().bump("x", now=0, by=0.0)
