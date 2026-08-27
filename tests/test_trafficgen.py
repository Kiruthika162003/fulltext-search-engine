from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.trafficgen import (
    GeneratedTraffic,
    TrafficMix,
    generate,
    zipf_pick,
)

VOCAB = ["kettle", "stove", "copper", "blanket", "harbor"]


def standard_mix() -> TrafficMix:
    return TrafficMix(
        single_share=0.6, pair_share=0.3, phrase_share=0.1
    )


class TestTheMix:
    def test_shares_must_sum_to_one(self):
        with pytest.raises(Invalid, match="invented silently"):
            TrafficMix(
                single_share=0.5, pair_share=0.3, phrase_share=0.1
            )


class TestZipf:
    def test_the_head_dominates(self):
        picks = [
            zipf_pick(VOCAB, roll / 200, 1.2)
            for roll in range(200)
        ]
        head = picks.count("kettle")
        tail = picks.count("harbor")
        assert head > 3 * tail
        assert tail >= 1

    def test_empty_vocabularies_generate_nothing(self):
        with pytest.raises(Invalid, match="generates nothing"):
            zipf_pick([], 0.5, 1.2)


class TestGeneration:
    def test_the_same_seed_replays_exactly(self):
        left = generate(VOCAB, 50, "seed-a", standard_mix())
        right = generate(VOCAB, 50, "seed-a", standard_mix())
        assert left.queries == right.queries

    def test_different_seeds_differ(self):
        left = generate(VOCAB, 50, "seed-a", standard_mix())
        right = generate(VOCAB, 50, "seed-b", standard_mix())
        assert left.queries != right.queries

    def test_the_mix_is_roughly_honored(self):
        held = generate(VOCAB, 300, "seed-a", standard_mix())
        assert 120 <= held.produced["single"] <= 240
        assert held.produced["pair"] >= 40
        assert held.produced["phrase"] >= 10

    def test_query_shapes_parse_as_intended(self):
        held = generate(VOCAB, 40, "seed-a", standard_mix())
        assert any(q.startswith("body:") for q in held.queries)
        assert any(q.startswith("+body:") for q in held.queries)
        assert any(q.startswith('"') for q in held.queries)

    def test_zero_counts_test_nothing(self):
        with pytest.raises(Invalid, match="tests nothing"):
            generate(VOCAB, 0, "s", standard_mix())


class TestTheReport:
    def test_the_report_confesses_drift(self):
        held = generate(VOCAB, 30, "seed-a", standard_mix())
        page = held.report()
        assert page.startswith("30 queries generated")
        assert "compare before quoting" in page

    def test_produced_counts_sum_to_the_run(self):
        held = generate(VOCAB, 77, "seed-a", standard_mix())
        assert sum(held.produced.values()) == 77
        assert isinstance(held, GeneratedTraffic)
