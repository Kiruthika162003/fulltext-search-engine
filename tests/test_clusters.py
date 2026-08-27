from __future__ import annotations

import pytest

from quarry.clusters import DupClusters
from quarry.errors import Invalid


def catalog_clusters() -> DupClusters:
    held = DupClusters()
    held.join(7, 3, 0.9)
    held.join(3, 12, 0.85)
    held.join(20, 21, 0.95)
    return held


class TestJoining:
    def test_pairs_become_families_transitively(self):
        held = catalog_clusters()
        assert held.canonical(7) == held.canonical(12) == 3
        assert held.families() == [[3, 7, 12], [20, 21]]

    def test_weak_pairs_are_refused_at_the_door(self):
        held = catalog_clusters()
        message = held.join(12, 20, 0.5)
        assert "chimera" in message
        assert held.families() == [[3, 7, 12], [20, 21]]
        assert held.refused == 1

    def test_self_duplication_is_not_similarity(self):
        with pytest.raises(Invalid, match="identity is"):
            DupClusters().join(4, 4, 0.9)

    def test_confidence_stays_in_the_unit_interval(self):
        with pytest.raises(Invalid, match=r"\[0, 1\]"):
            DupClusters().join(1, 2, 1.5)

    def test_rejoining_family_is_calm(self):
        held = catalog_clusters()
        assert held.join(7, 12, 0.9) == "already family"


class TestCanonicals:
    def test_the_smallest_id_survives(self):
        held = catalog_clusters()
        assert held.canonical(21) == 20
        assert held.suppressions() == [7, 12, 21]

    def test_loners_are_their_own_canonical(self):
        assert DupClusters().canonical(99) == 99

    def test_reruns_name_the_same_survivors(self):
        left = catalog_clusters()
        right = DupClusters()
        right.join(20, 21, 0.95)
        right.join(3, 12, 0.85)
        right.join(7, 3, 0.9)
        assert left.families() == right.families()
        assert left.suppressions() == right.suppressions()


class TestTheReport:
    def test_the_report_reads_family_by_family(self):
        page = catalog_clusters().report()
        assert "family of 3 under doc 3; suppress 7, 12" in page
        assert "family of 2 under doc 20; suppress 21" in page
        assert "3 join(s), 0 refused below 0.7" in page

    def test_a_clean_catalog_counts_its_refusals(self):
        held = DupClusters()
        held.join(1, 2, 0.2)
        assert held.report() == (
            "no families; 1 weak pair(s) refused at the door"
        )
