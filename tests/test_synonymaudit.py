from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.synonymaudit import (
    ChainReport,
    PairEvidence,
    audit_chains,
    audit_pairs,
)


def living_pair() -> PairEvidence:
    return PairEvidence(
        left="couch",
        right="sofa",
        corpus_overlap=0.4,
        log_crossover=0.2,
    )


def dead_pair() -> PairEvidence:
    return PairEvidence(
        left="wireless",
        right="crystal-set",
        corpus_overlap=0.01,
        log_crossover=0.0,
    )


class TestPairs:
    def test_either_evidence_stream_keeps_a_pair(self):
        assert living_pair().healthy()
        log_only = PairEvidence(
            left="tv",
            right="telly",
            corpus_overlap=0.02,
            log_crossover=0.3,
        )
        assert log_only.healthy()

    def test_failing_both_flags_retirement(self):
        assert not dead_pair().healthy()
        assert "RETIRE" in dead_pair().verdict()
        assert "not an auto-delete" in dead_pair().verdict()

    def test_the_audit_counts_its_flags(self):
        retire, page = audit_pairs([living_pair(), dead_pair()])
        assert len(retire) == 1
        assert "2 pair(s) audited, 1 flagged" in page

    def test_shares_live_in_the_unit_interval(self):
        with pytest.raises(Invalid, match=r"\[0, 1\]"):
            PairEvidence(
                left="a",
                right="b",
                corpus_overlap=1.5,
                log_crossover=0.0,
            )

    def test_an_empty_book_audits_nothing(self):
        with pytest.raises(Invalid, match="audits nothing"):
            audit_pairs([])


class TestChains:
    def test_the_couch_sofa_bed_wreck_is_named(self):
        reports = audit_chains(
            rings={"sofa": {"couch", "bed"}},
            overlap={("bed", "couch"): 0.01},
        )
        assert len(reports) == 1
        assert reports[0].chain == ("bed", "sofa", "couch")
        assert reports[0].bridge_too_far()
        assert "joined two strangers" in reports[0].line()

    def test_honest_chains_hold(self):
        report = ChainReport(
            chain=("couch", "sofa", "settee"),
            end_to_end_overlap=0.3,
        )
        assert not report.bridge_too_far()
        assert report.line().endswith("ends overlap at 0.3")

    def test_unmeasured_overlaps_are_refused(self):
        with pytest.raises(Invalid, match="corpus in hand"):
            audit_chains(
                rings={"sofa": {"couch", "bed"}},
                overlap={},
            )
