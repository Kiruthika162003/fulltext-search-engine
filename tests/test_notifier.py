from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.notifier import Notifier


class TestRouting:
    def test_severities_route_by_the_table(self):
        held = Notifier()
        assert held.send("critical", "index down") == (
            "delivered to page"
        )
        assert held.send("warning", "p95 rising") == (
            "delivered to chat"
        )
        assert held.send("info", "backfill done") == (
            "delivered to digest"
        )

    def test_invented_severities_route_nowhere_so_refuse(self):
        with pytest.raises(Invalid, match="nowhere"):
            Notifier().send("mega-urgent", "help")

    def test_empty_messages_notify_nothing(self):
        with pytest.raises(Invalid, match="notifies nothing"):
            Notifier().send("info", "  ")


class TestQuietHours:
    def test_chat_demotes_to_digest_on_purpose(self):
        held = Notifier(quiet=True)
        assert held.send("warning", "p95 rising") == (
            "delivered to digest"
        )
        page = held.channel_page("digest")
        assert "demoted by quiet hours, on purpose" in page

    def test_pages_never_demote(self):
        held = Notifier(quiet=True)
        assert held.send("critical", "index down") == (
            "delivered to page"
        )
        assert "1 page(s) woke a human" in held.wake_audit()


class TestFloodCaps:
    def test_storms_fold_into_one_sentence(self):
        held = Notifier()
        for n in range(9):
            held.send("warning", f"shard {n} slow")
        page = held.channel_page("chat")
        assert page.count("shard") == 5
        assert "4 more message(s) folded" in page
        assert "less information than this" in page

    def test_pages_have_no_cap(self):
        held = Notifier()
        for n in range(9):
            held.send("critical", f"replica {n} gone")
        assert "9 page(s) woke a human" in held.wake_audit()


class TestQuietChannels:
    def test_a_quiet_channel_says_quiet(self):
        assert Notifier().channel_page("digest") == "digest: quiet"

    def test_nobody_woken_reads_calm(self):
        assert Notifier().wake_audit() == "nobody was woken"
