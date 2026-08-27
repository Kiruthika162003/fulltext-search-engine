from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.graphexpand import CooccurrenceGraph


def coffee_graph() -> CooccurrenceGraph:
    graph = CooccurrenceGraph()
    docs = [
        {"espresso", "crema", "grinder"},
        {"espresso", "crema", "portafilter"},
        {"espresso", "crema"},
        {"crema", "portafilter"},
        {"grinder", "burr"},
        {"grinder", "burr", "espresso"},
        {"kettle", "teapot"},
    ]
    for doc, terms in enumerate(docs):
        graph.learn(doc, terms)
    return graph


class TestEdges:
    def test_overlap_is_jaccard_not_popularity(self):
        graph = coffee_graph()
        assert graph.edge("espresso", "crema") == 0.6
        assert graph.edge("kettle", "teapot") == 1.0

    def test_unrelated_terms_have_no_edge(self):
        assert coffee_graph().edge("espresso", "teapot") == 0.0

    def test_neighbors_rank_by_strength(self):
        neighbors = coffee_graph().neighbors("espresso")
        assert neighbors[0][0] == "crema"


class TestExpansion:
    def test_direct_neighbors_arrive_first(self):
        held = coffee_graph().expand("espresso")
        assert held[0].term == "crema"
        assert held[0].path == ("espresso", "crema")

    def test_two_hops_arrive_discounted(self):
        held = coffee_graph().expand("espresso", limit=10)
        by_term = {one.term: one for one in held}
        assert "portafilter" in by_term
        two_hop = by_term["portafilter"]
        assert len(two_hop.path) == 3
        assert two_hop.weight < by_term["crema"].weight

    def test_islands_never_connect(self):
        terms = [one.term for one in coffee_graph().expand("espresso", limit=20)]
        assert "kettle" not in terms
        assert "teapot" not in terms

    def test_unknown_terms_expand_to_nothing(self):
        assert coffee_graph().expand("zeppelin") == []

    def test_zero_limits_are_refused(self):
        with pytest.raises(Invalid, match="expands nothing"):
            coffee_graph().expand("espresso", limit=0)


class TestWhy:
    def test_every_expansion_can_say_its_route(self):
        page = coffee_graph().why("espresso", "portafilter")
        assert "via espresso -> crema -> portafilter" in page

    def test_the_unreachable_are_named_as_such(self):
        page = coffee_graph().why("espresso", "teapot")
        assert "not reachable" in page
