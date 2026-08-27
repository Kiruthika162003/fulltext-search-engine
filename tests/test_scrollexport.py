from __future__ import annotations

import pytest

from quarry.errors import Invalid, Stale
from quarry.scrollexport import Scroll, ScrollSource, full_export


def stocked() -> ScrollSource:
    source = ScrollSource()
    for external in range(7):
        source.add(external)
    return source


class TestScrolling:
    def test_pages_cover_everything_once(self):
        pages = full_export(stocked(), page_size=3, start_tick=0)
        assert pages == [[0, 1, 2], [3, 4, 5], [6]]

    def test_documents_added_after_the_anchor_wait(self):
        source = stocked()
        scroll = Scroll(source=source, page_size=10)
        source.add(99)
        assert scroll.next_page(1) == [0, 1, 2, 3, 4, 5, 6]

    def test_deletions_after_the_anchor_still_exclude(self):
        source = stocked()
        scroll = Scroll(source=source, page_size=3)
        first = scroll.next_page(1)
        assert first == [0, 1, 2]
        source.delete(4)
        assert scroll.next_page(2) == [3, 5, 6]

    def test_zero_page_sizes_export_nothing(self):
        with pytest.raises(Invalid, match="exports nothing"):
            Scroll(source=stocked(), page_size=0)


class TestTheLease:
    def test_a_lapsed_lease_names_the_fix(self):
        scroll = Scroll(source=stocked(), page_size=3)
        scroll.next_page(1)
        with pytest.raises(Stale, match="open a new scroll"):
            scroll.next_page(50)

    def test_steady_advancing_keeps_the_lease(self):
        scroll = Scroll(source=stocked(), page_size=2)
        assert scroll.next_page(5) == [0, 1]
        assert scroll.next_page(14) == [2, 3]
        assert scroll.next_page(23) == [4, 5]

    def test_an_exhausted_scroll_says_so(self):
        scroll = Scroll(source=stocked(), page_size=10)
        scroll.next_page(1)
        with pytest.raises(Stale, match="exhausted"):
            scroll.next_page(2)


class TestProgress:
    def test_progress_counts_the_eligible(self):
        source = stocked()
        scroll = Scroll(source=source, page_size=3)
        source.add(99)
        scroll.next_page(1)
        page = scroll.progress()
        assert "cursor at 2" in page
        assert "7 document(s) eligible" in page

    def test_the_exhausted_state_is_visible(self):
        scroll = Scroll(source=stocked(), page_size=10)
        scroll.next_page(1)
        assert scroll.progress().startswith("scroll exhausted")
