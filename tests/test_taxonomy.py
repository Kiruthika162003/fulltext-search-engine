from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.taxonomy import Taxonomy


def catalog() -> Taxonomy:
    tree = Taxonomy()
    tree.file_document(0, "electronics/audio")
    tree.file_document(1, "electronics/audio")
    tree.file_document(2, "electronics/video")
    tree.file_document(3, "electronics")
    tree.file_document(4, "garden/tools")
    return tree


class TestFiling:
    def test_ancestors_spring_into_being(self):
        tree = catalog()
        assert tree.direct_count("electronics") == 1
        assert "garden" in tree.children()

    def test_double_filing_inflates_rollups_so_refuse(self):
        tree = catalog()
        with pytest.raises(Invalid, match="inflates"):
            tree.file_document(0, "electronics/audio")

    def test_a_document_may_file_under_two_paths(self):
        tree = catalog()
        tree.file_document(0, "garden/tools")
        assert tree.direct_count("garden/tools") == 2

    def test_empty_segments_are_not_paths(self):
        with pytest.raises(Invalid, match="no empties"):
            Taxonomy().file_document(0, "electronics//audio")


class TestCounts:
    def test_rollups_gather_the_subtree(self):
        tree = catalog()
        assert tree.rollup_count("electronics") == 4
        assert tree.direct_count("electronics") == 1

    def test_rollups_deduplicate_multi_filed_documents(self):
        tree = catalog()
        tree.file_document(0, "electronics/video")
        assert tree.rollup_count("electronics") == 4

    def test_unknown_paths_are_named(self):
        with pytest.raises(Invalid, match="ever filed"):
            catalog().direct_count("clothing")


class TestNavigation:
    def test_children_read_level_by_level(self):
        tree = catalog()
        assert tree.children() == ["electronics", "garden"]
        assert tree.children("electronics") == [
            "electronics/audio",
            "electronics/video",
        ]

    def test_pure_navigation_is_named(self):
        verdict = catalog().shelf_or_navigation("garden")
        assert "pure navigation" in verdict

    def test_a_shelf_is_a_shelf(self):
        verdict = catalog().shelf_or_navigation("electronics/audio")
        assert verdict.endswith("a shelf, 2 direct of 2 total")

    def test_navigation_heavy_pages_need_curating(self):
        verdict = catalog().shelf_or_navigation("electronics")
        assert "needs curating" in verdict


class TestThePage:
    def test_the_tree_indents_by_depth(self):
        page = catalog().tree_page()
        lines = page.splitlines()
        assert lines[0] == "electronics: 1 direct, 4 rolled up"
        assert lines[1] == "  audio: 2 direct, 2 rolled up"

    def test_an_empty_taxonomy_says_so(self):
        assert Taxonomy().tree_page() == (
            "an empty taxonomy files nothing"
        )
