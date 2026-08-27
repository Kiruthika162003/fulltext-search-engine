from __future__ import annotations

import pytest

from quarry.doclinks import LinkGraph
from quarry.errors import Invalid


def wiki() -> LinkGraph:
    graph = LinkGraph()
    for doc in range(4):
        graph.add_document(doc)
    graph.cite(1, 0)
    graph.cite(2, 0)
    graph.cite(3, 0)
    graph.cite(0, 1)
    return graph


class TestTheDoor:
    def test_self_citation_is_not_a_vote(self):
        graph = wiki()
        with pytest.raises(Invalid, match="free votes"):
            graph.cite(1, 1)

    def test_duplicate_edges_are_ballot_stuffing(self):
        graph = wiki()
        with pytest.raises(Invalid, match="ballot box"):
            graph.cite(1, 0)

    def test_strangers_cannot_link(self):
        graph = wiki()
        with pytest.raises(Invalid, match="before their links"):
            graph.cite(1, 9)

    def test_an_empty_graph_has_no_authority(self):
        with pytest.raises(Invalid, match="no authority"):
            LinkGraph().authority()


class TestAuthority:
    def test_the_cited_page_carries_the_room(self):
        scores, _ = wiki().authority()
        assert scores[0] == max(scores.values())
        assert scores[0] > 2 * scores[2]

    def test_scores_form_a_distribution(self):
        scores, _ = wiki().authority()
        assert abs(sum(scores.values()) - 1.0) < 0.01

    def test_equal_graphs_share_equally(self):
        graph = LinkGraph()
        for doc in range(3):
            graph.add_document(doc)
        graph.cite(0, 1)
        graph.cite(1, 2)
        graph.cite(2, 0)
        scores, movement = graph.authority()
        assert len(set(scores.values())) == 1
        assert movement < 0.001

    def test_dangling_documents_spread_their_score(self):
        graph = LinkGraph()
        for doc in range(2):
            graph.add_document(doc)
        graph.cite(0, 1)
        scores, _ = graph.authority()
        assert scores[1] > scores[0] > 0.0


class TestTheReport:
    def test_the_report_ranks_and_states_convergence(self):
        page = wiki().report()
        lines = page.splitlines()
        assert lines[0].startswith("doc 0:")
        assert "after 20 rounds:" in lines[-1]
        assert (
            "converged" in lines[-1] or "stopped" in lines[-1]
        )
