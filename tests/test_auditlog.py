from __future__ import annotations

import dataclasses

import pytest

from quarry.auditlog import SEED, AuditLog
from quarry.errors import Invalid


def busy_log() -> AuditLog:
    log = AuditLog()
    log.record("ana", "add", "doc:12", "new product page")
    log.record("ben", "delete", "doc:7", "dmca takedown 44-2026")
    log.record("ana", "curation", "body:widget", "spring launch")
    return log


class TestRecording:
    def test_entries_chain_from_the_seed(self):
        log = busy_log()
        assert log.entries[0].previous == SEED
        assert log.entries[1].previous == log.entries[0].digest

    def test_sequences_are_dense(self):
        log = busy_log()
        assert [entry.sequence for entry in log.entries] == [0, 1, 2]

    def test_vague_verbs_audit_nothing(self):
        with pytest.raises(Invalid, match="audits nothing"):
            AuditLog().record("ana", "changed", "doc:1", "stuff")

    def test_actorless_entries_are_diaries(self):
        with pytest.raises(Invalid, match="diary"):
            AuditLog().record("  ", "add", "doc:1", "reason")
        with pytest.raises(Invalid, match="diary"):
            AuditLog().record("ana", "add", "doc:1", "   ")


class TestVerification:
    def test_an_honest_chain_verifies(self):
        assert busy_log().verify() == "chain intact: 3 entries"

    def test_an_edited_entry_breaks_at_its_line(self):
        log = busy_log()
        log.entries[1] = dataclasses.replace(
            log.entries[1], reason="routine cleanup"
        )
        verdict = log.verify()
        assert verdict.startswith("BROKEN at #1")
        assert "content was" in verdict

    def test_a_deleted_entry_breaks_the_next_link(self):
        log = busy_log()
        del log.entries[1]
        verdict = log.verify()
        assert verdict.startswith("BROKEN at #2")
        assert "chain was edited" in verdict

    def test_reading_a_broken_chain_refuses(self):
        log = busy_log()
        del log.entries[0]
        with pytest.raises(Invalid, match="BROKEN"):
            log.read()


class TestReading:
    def test_reads_filter_by_actor_and_verb(self):
        log = busy_log()
        assert len(log.read(actor="ana")) == 2
        assert len(log.read(verb="delete")) == 1

    def test_lines_carry_the_digest(self):
        line = busy_log().read(verb="delete")[0]
        assert line.startswith("#1 ben delete doc:7: dmca")
        assert line.endswith("]")

    def test_an_empty_log_is_intact_and_empty(self):
        log = AuditLog()
        assert log.verify() == "chain intact: 0 entries"
        assert log.read() == []
