from __future__ import annotations

from quarry.ingestclean import CleanLedger
from quarry.intake import IntakePipeline
from quarry.journal import Journal
from quarry.quotas import Quota, TenantMeter


def pipeline(document_quota: int = 5) -> IntakePipeline:
    return IntakePipeline(
        cleaner=CleanLedger(),
        meter=TenantMeter(
            quota=Quota(
                documents=document_quota, searches_per_window=10
            )
        ),
        journal=Journal(),
    )


class TestAdmission:
    def test_the_receipt_lists_every_gate(self):
        held = pipeline()
        receipt, verdict = held.admit("<p>a copper kettle</p>")
        assert verdict == "admitted"
        assert receipt.gates_passed == (
            "clean",
            "validate",
            "quota",
            "journal",
            "index",
        )
        assert receipt.line().startswith("doc 0: clean -> validate")

    def test_cleaning_happens_before_anything_judges(self):
        held = pipeline()
        receipt, _ = held.admit("<b>kettle</b>")
        assert held.indexed[0]["body"] == "kettle"
        assert receipt is not None

    def test_journal_and_index_agree_on_the_external(self):
        held = pipeline()
        held.admit("first doc here")
        receipt, _ = held.admit("second doc here")
        assert receipt.external == 1
        assert held.journal.entries[1].payload == "second doc here"


class TestRefusals:
    def test_packaging_is_refused_at_validate(self):
        held = pipeline()
        receipt, verdict = held.admit("<p></p>")
        assert receipt is None
        assert verdict.startswith("refused at validate")
        assert "sent\npackaging" in verdict or "sent packaging" in verdict

    def test_the_quota_gate_holds_the_line(self):
        held = pipeline(document_quota=1)
        held.admit("the first fits")
        receipt, verdict = held.admit("the second does not")
        assert receipt is None
        assert verdict.startswith("refused at quota")

    def test_refused_documents_never_reach_the_journal(self):
        held = pipeline(document_quota=1)
        held.admit("the first fits")
        held.admit("the second does not")
        assert len(held.journal.entries) == 1


class TestTheReport:
    def test_refusals_count_per_gate(self):
        held = pipeline(document_quota=1)
        held.admit("fits fine")
        held.admit("over quota")
        held.admit("<p></p>")
        page = held.gate_report()
        assert page.startswith("1 admitted, 2 refused")
        assert "quota: 1 refusal(s)" in page
        assert "validate: 1 refusal(s)" in page

    def test_the_noisiest_gate_is_named(self):
        held = pipeline()
        held.admit("<p></p>")
        held.admit("<div></div>")
        assert "noisiest gate: validate" in held.gate_report()
