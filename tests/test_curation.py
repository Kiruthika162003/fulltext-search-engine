from __future__ import annotations

import pytest

from quarry.curation import Curation, CurationDesk
from quarry.errors import Invalid, Missing

RANKED = [(3, 9.1), (7, 4.2), (5, 2.0), (9, 1.1)]


def launch_curation() -> Curation:
    return Curation(
        canonical="body:widget",
        pinned=(9,),
        blocked=(5,),
        author="merch-team",
        reason="spring launch week",
    )


class TestTheDoor:
    def test_a_reason_is_mandatory(self):
        with pytest.raises(Invalid, match="say why"):
            Curation(
                canonical="body:widget",
                pinned=(1,),
                blocked=(),
                author="merch-team",
                reason="   ",
            )

    def test_pinned_and_blocked_must_not_overlap(self):
        with pytest.raises(Invalid, match="pick a side"):
            Curation(
                canonical="body:widget",
                pinned=(1, 2),
                blocked=(2, 3),
                author="merch-team",
                reason="confused",
            )


class TestApplication:
    def test_uncurated_queries_pass_through_organic(self):
        desk = CurationDesk()
        hits = desk.apply("body:widget", RANKED)
        assert [hit.external for hit in hits] == [3, 7, 5, 9]
        assert not any(hit.curated for hit in hits)

    def test_pins_rise_and_blocks_vanish(self):
        desk = CurationDesk()
        desk.declare(launch_curation())
        hits = desk.apply("body:widget", RANKED)
        assert [hit.external for hit in hits] == [9, 3, 7]

    def test_moved_hits_are_marked_curated(self):
        desk = CurationDesk()
        desk.declare(launch_curation())
        hits = desk.apply("body:widget", RANKED)
        assert hits[0].curated
        assert not hits[1].curated

    def test_the_pin_borrows_the_top_score(self):
        desk = CurationDesk()
        desk.declare(launch_curation())
        hits = desk.apply("body:widget", RANKED)
        assert hits[0].score == 9.1

    def test_other_queries_are_untouched(self):
        desk = CurationDesk()
        desk.declare(launch_curation())
        hits = desk.apply("body:gadget", RANKED)
        assert [hit.external for hit in hits] == [3, 7, 5, 9]


class TestTheLedger:
    def test_withdrawing_the_absent_hints_at_drift(self):
        with pytest.raises(Missing, match="canonical form drifted"):
            CurationDesk().withdraw("body:widget")

    def test_withdraw_returns_the_curation(self):
        desk = CurationDesk()
        desk.declare(launch_curation())
        held = desk.withdraw("body:widget")
        assert held.author == "merch-team"
        assert desk.apply("body:widget", RANKED)[0].external == 3

    def test_the_ledger_reads_author_and_reason(self):
        desk = CurationDesk()
        desk.declare(launch_curation())
        desk.apply("body:widget", RANKED)
        page = desk.ledger()
        assert "merch-team: spring launch week" in page
        assert "1 standing, applied 1 time(s)" in page

    def test_an_empty_desk_says_so(self):
        assert CurationDesk().ledger() == "no curations standing"
