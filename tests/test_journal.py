from __future__ import annotations

import dataclasses

import pytest

from quarry.errors import Invalid, Stale
from quarry.journal import Journal


def busy_journal() -> Journal:
    journal = Journal()
    journal.append("add", "doc:0 the first")
    journal.append("add", "doc:1 the second")
    journal.append("delete", "doc:0")
    journal.append("add", "doc:2 the third")
    return journal


class TestAppending:
    def test_sequences_are_dense_and_checksummed(self):
        journal = busy_journal()
        assert [e.sequence for e in journal.entries] == [0, 1, 2, 3]
        assert all(e.intact() for e in journal.entries)

    def test_unknown_verbs_are_refused(self):
        with pytest.raises(Invalid, match="is neither"):
            Journal().append("mutate", "doc:1")

    def test_empty_payloads_journal_nothing(self):
        with pytest.raises(Invalid, match="journals nothing"):
            Journal().append("add", "   ")


class TestCheckpoints:
    def test_replay_starts_after_the_checkpoint(self):
        journal = busy_journal()
        journal.mark_checkpoint(1)
        kept, verdict = journal.replay()
        assert [e.sequence for e in kept] == [2, 3]
        assert verdict == (
            "recovered cleanly: 2 entrie(s) after checkpoint 1"
        )

    def test_checkpoints_only_advance(self):
        journal = busy_journal()
        journal.mark_checkpoint(2)
        with pytest.raises(Stale, match="only\\s+advance"):
            journal.mark_checkpoint(1)

    def test_checkpoints_cannot_cover_the_future(self):
        with pytest.raises(Invalid, match="do not\\s+exist"):
            busy_journal().mark_checkpoint(9)


class TestReplay:
    def test_a_corrupt_entry_stops_the_replay_loudly(self):
        journal = busy_journal()
        journal.entries[2] = dataclasses.replace(
            journal.entries[2], payload="doc:99"
        )
        kept, verdict = journal.replay()
        assert [e.sequence for e in kept] == [0, 1]
        assert verdict.startswith("REPLAY STOPPED at #2")
        assert "tail from #2 is lost" in verdict

    def test_an_untouched_journal_replays_everything(self):
        kept, verdict = busy_journal().replay()
        assert len(kept) == 4
        assert verdict.startswith("recovered cleanly")


class TestTruncation:
    def test_truncation_requires_the_checkpoint_repeated(self):
        journal = busy_journal()
        journal.mark_checkpoint(2)
        with pytest.raises(Invalid, match="repeating the checkpoint"):
            journal.truncate_to_checkpoint(1)

    def test_truncation_drops_only_the_flushed(self):
        journal = busy_journal()
        journal.mark_checkpoint(2)
        message = journal.truncate_to_checkpoint(2)
        assert message == "dropped 3 flushed entrie(s); 1 remain"
        assert [e.sequence for e in journal.entries] == [3]

    def test_truncation_without_a_checkpoint_eats_history(self):
        with pytest.raises(Invalid, match="eat"):
            busy_journal().truncate_to_checkpoint(0)

    def test_the_status_counts_pending(self):
        journal = busy_journal()
        journal.mark_checkpoint(1)
        assert journal.status() == (
            "4 entrie(s), checkpoint at 1, 2 pending replay"
        )
