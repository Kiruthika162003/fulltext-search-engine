from __future__ import annotations

import pytest

from quarry.cascadesearch import cascade, cascade_trace
from quarry.errors import Invalid


def tiers(exact, loosened, fuzzy):
    return {
        "exact": lambda: exact,
        "loosened": lambda: loosened,
        "fuzzy": lambda: fuzzy,
    }


class TestDescent:
    def test_a_fed_exact_tier_never_descends(self):
        page = cascade(tiers([1, 2, 3], [9, 9, 9], [8]), floor=3)
        assert page.tier == "exact"
        assert page.externals == (1, 2, 3)
        assert page.starved_tiers == ()
        assert page.banner() == ""

    def test_starvation_descends_one_tier(self):
        page = cascade(tiers([1], [4, 5, 6], [8]), floor=3)
        assert page.tier == "loosened"
        assert page.starved_tiers == ("exact",)
        assert "broader matches" in page.banner()

    def test_the_last_tier_serves_whatever_it_has(self):
        page = cascade(tiers([], [], [7]), floor=3)
        assert page.tier == "fuzzy"
        assert page.externals == (7,)
        assert page.starved_tiers == ("exact", "loosened")
        assert "did you mean" in page.banner()

    def test_tiers_never_mix(self):
        page = cascade(tiers([1], [4, 5, 6], [8]), floor=3)
        assert 1 not in page.externals

    def test_duplicate_hits_within_a_tier_collapse(self):
        page = cascade(tiers([1, 1, 2], [], []), floor=2)
        assert page.externals == (1, 2)


class TestContracts:
    def test_a_zero_floor_is_a_plain_search(self):
        with pytest.raises(Invalid, match="never starves"):
            cascade(tiers([1], [], []), floor=0)

    def test_all_tiers_are_mandatory(self):
        with pytest.raises(Invalid, match="missing fuzzy"):
            cascade(
                {"exact": lambda: [], "loosened": lambda: []},
                floor=1,
            )


class TestTheTrace:
    def test_the_descent_is_narrated(self):
        page = cascade_trace(tiers([1], [4, 5, 6], [8]), floor=3)
        lines = page.splitlines()
        assert lines[0] == "floor 3:"
        assert lines[1] == "  exact: 1 hit(s), starves (1 under 3)"
        assert lines[2] == "  loosened: 3 hit(s), SERVES"
        assert len(lines) == 3
