from __future__ import annotations

import pytest

from quarry.errors import Invalid, Missing
from quarry.schema import Schema
from quarry.tenancy import TenancyLayer, TenantQuota


def platform() -> TenancyLayer:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    layer = TenancyLayer(schema=schema)
    layer.onboard(
        "acme", TenantQuota(max_documents=3, max_queries_per_day=5)
    )
    layer.onboard(
        "globex", TenantQuota(max_documents=100, max_queries_per_day=100)
    )
    return layer


class TestIsolation:
    def test_tenants_share_no_machinery(self):
        layer = platform()
        assert layer.isolation_proof("acme", "globex")

    def test_one_tenants_corpus_never_answers_another(self):
        layer = platform()
        layer.add("acme", {"body": "acme secret formula"})
        layer.commit("acme")
        layer.commit("globex")
        acme_hits = layer.search("acme", "secret").hits
        globex_hits = layer.search("globex", "secret").hits
        assert len(acme_hits) == 1
        assert globex_hits == ()

    def test_vocabularies_do_not_leak_between_tenants(self):
        layer = platform()
        layer.add("acme", {"body": "zzyzx zzyzx zzyzx"})
        layer.commit("acme")
        assert (
            layer.tenants["globex"].engine.vocabulary.vocabulary_size()
            == 0
        )


class TestQuotas:
    def test_the_document_quota_names_the_tenant(self):
        layer = platform()
        for number in range(3):
            layer.add("acme", {"body": f"doc {number}"})
        with pytest.raises(Invalid, match="acme is at its document"):
            layer.add("acme", {"body": "one too many"})

    def test_the_query_quota_exhausts_and_resets(self):
        layer = platform()
        layer.commit("acme")
        for _ in range(5):
            layer.search("acme", "anything")
        with pytest.raises(Invalid, match="exhausted"):
            layer.search("acme", "anything")
        layer.new_day()
        assert layer.search("acme", "anything").hits == ()

    def test_zero_quotas_are_refused(self):
        with pytest.raises(Invalid, match="wearing a plan"):
            TenantQuota(max_documents=0, max_queries_per_day=5)

    def test_ghost_tenants_are_named(self):
        with pytest.raises(Missing):
            platform().add("ghost", {"body": "?"})


class TestTheDesk:
    def test_the_bill_reads_per_tenant(self):
        layer = platform()
        layer.add("acme", {"body": "one"})
        bill = layer.bill()
        assert "acme: 1 documents held, 0 queries today" in bill
        assert "globex: 0 documents held" in bill

    def test_noisy_neighbours_rank_by_share(self):
        layer = platform()
        layer.commit("acme")
        layer.commit("globex")
        for _ in range(4):
            layer.search("globex", "anything")
        layer.search("acme", "anything")
        noisy = layer.noisy_neighbours()
        assert noisy[0] == ("globex", 0.8)
        assert noisy[1] == ("acme", 0.2)

    def test_a_quiet_day_has_no_noise(self):
        with pytest.raises(Invalid, match="quiet day"):
            platform().noisy_neighbours()
