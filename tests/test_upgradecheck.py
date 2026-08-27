from __future__ import annotations

import pytest

from quarry.errors import Invalid
from quarry.upgradecheck import (
    check_deprecations,
    check_format,
    check_journal,
    check_segments,
    preflight,
)


class TestFormatChecks:
    def test_in_range_formats_pass(self):
        held = check_format(3, readable_min=2, readable_max=4)
        assert held.severity == "pass"

    def test_too_old_formats_name_the_intermediate_step(self):
        held = check_format(1, readable_min=2, readable_max=4)
        assert held.severity == "block"
        assert "intermediate upgrade" in held.evidence

    def test_too_new_formats_are_downgrades_in_disguise(self):
        held = check_format(9, readable_min=2, readable_max=4)
        assert held.severity == "block"
        assert "downgrade wearing" in held.evidence

    def test_inside_out_ranges_are_refused(self):
        with pytest.raises(Invalid, match="inside out"):
            check_format(3, readable_min=5, readable_max=2)


class TestOtherChecks:
    def test_deprecated_options_block_with_the_fix_window(self):
        held = check_deprecations(
            ["fold_v1", "stem"], deprecated={"fold_v1"}
        )
        assert held.severity == "block"
        assert "while the old one still runs" in held.evidence

    def test_clean_options_pass(self):
        held = check_deprecations(["stem"], deprecated={"fold_v1"})
        assert held.severity == "pass"

    def test_corrupt_segments_block(self):
        assert check_segments(False).severity == "block"
        assert check_segments(True).severity == "pass"

    def test_pending_journals_warn_with_the_reason(self):
        held = check_journal(5)
        assert held.severity == "warn"
        assert "corruption is\nborn" in held.evidence or "corruption is born" in held.evidence


class TestTheVerdict:
    def test_blocks_lead_and_decide(self):
        page = preflight(
            [
                check_journal(0),
                check_format(1, 2, 4),
                check_segments(True),
            ]
        )
        lines = page.splitlines()
        assert lines[0].startswith("[BLOCK] format")
        assert page.endswith(
            "DO NOT UPGRADE: proceeding past a block is an outage "
            "with a countdown"
        )

    def test_warnings_alone_are_choices(self):
        page = preflight([check_journal(3), check_segments(True)])
        assert page.endswith("PROCEED WITH CARE: warnings are choices")

    def test_a_clean_board_clears(self):
        page = preflight(
            [
                check_format(3, 2, 4),
                check_deprecations([], set()),
                check_segments(True),
                check_journal(0),
            ]
        )
        assert page.endswith("CLEAR TO UPGRADE")

    def test_zero_checks_clear_nothing(self):
        with pytest.raises(Invalid, match="clears nothing"):
            preflight([])
