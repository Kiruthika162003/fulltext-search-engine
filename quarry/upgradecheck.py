"""Upgrade preflight: incompatibilities surface before the restart.

Upgrading an engine over live data fails at the worst moment
unless the incompatibilities are hunted first, so the preflight
walks a checklist derived from what actually breaks upgrades:
the persisted format version must be within the new binary's
readable range, deprecated analyzer options must be absent
because the new binary will refuse them at boot, on-disk
segments must verify against their manifest before anything
touches them, and the journal must be empty or checkpointed
since replaying an old journal with new code is where subtle
corruption is born. Each check returns pass, warn, or block
with its evidence, the report orders blocks first, and the
overall verdict is the strictest finding, because an upgrade
that proceeds on warnings is a choice but an upgrade that
proceeds past a block is an outage with a countdown.
"""

from __future__ import annotations

from dataclasses import dataclass

from quarry.errors import Invalid

SEVERITIES = ("pass", "warn", "block")


@dataclass(frozen=True)
class CheckResult:
    name: str
    severity: str
    evidence: str

    def __post_init__(self) -> None:
        if self.severity not in SEVERITIES:
            raise Invalid(
                f"{self.name}: severity {self.severity!r} is not "
                f"on the scale {', '.join(SEVERITIES)}"
            )

    def line(self) -> str:
        return f"[{self.severity.upper()}] {self.name}: {self.evidence}"


def check_format(
    on_disk_version: int, readable_min: int, readable_max: int
) -> CheckResult:
    if readable_min > readable_max:
        raise Invalid("the readable range is inside out")
    if on_disk_version < readable_min:
        return CheckResult(
            name="format",
            severity="block",
            evidence=(
                f"on-disk format {on_disk_version} is older than "
                f"the new binary reads ({readable_min}); run the "
                f"intermediate upgrade first"
            ),
        )
    if on_disk_version > readable_max:
        return CheckResult(
            name="format",
            severity="block",
            evidence=(
                f"on-disk format {on_disk_version} is newer than "
                f"the new binary ({readable_max}); this is a "
                f"downgrade wearing an upgrade's name"
            ),
        )
    return CheckResult(
        name="format",
        severity="pass",
        evidence=(
            f"format {on_disk_version} within "
            f"[{readable_min}, {readable_max}]"
        ),
    )


def check_deprecations(
    analyzer_options: list[str], deprecated: set[str]
) -> CheckResult:
    found = sorted(set(analyzer_options) & deprecated)
    if found:
        return CheckResult(
            name="deprecations",
            severity="block",
            evidence=(
                f"option(s) {', '.join(found)} are gone in the new "
                f"binary; it will refuse them at boot, so fix them "
                f"while the old one still runs"
            ),
        )
    return CheckResult(
        name="deprecations",
        severity="pass",
        evidence="no deprecated analyzer options in use",
    )


def check_segments(manifest_clean: bool) -> CheckResult:
    if not manifest_clean:
        return CheckResult(
            name="segments",
            severity="block",
            evidence=(
                "segments fail manifest verification; upgrading "
                "over corruption bakes it in"
            ),
        )
    return CheckResult(
        name="segments",
        severity="pass",
        evidence="all segments verify against the manifest",
    )


def check_journal(pending_entries: int) -> CheckResult:
    if pending_entries > 0:
        return CheckResult(
            name="journal",
            severity="warn",
            evidence=(
                f"{pending_entries} journal entrie(s) pending; "
                f"flush and checkpoint first, replaying old "
                f"journals with new code is where corruption is "
                f"born"
            ),
        )
    return CheckResult(
        name="journal",
        severity="pass",
        evidence="journal empty or checkpointed",
    )


def preflight(results: list[CheckResult]) -> str:
    if not results:
        raise Invalid("a preflight of zero checks clears nothing")
    order = {"block": 0, "warn": 1, "pass": 2}
    ordered = sorted(
        results, key=lambda held: (order[held.severity], held.name)
    )
    lines = [held.line() for held in ordered]
    if any(held.severity == "block" for held in results):
        verdict = (
            "DO NOT UPGRADE: proceeding past a block is an outage "
            "with a countdown"
        )
    elif any(held.severity == "warn" for held in results):
        verdict = "PROCEED WITH CARE: warnings are choices"
    else:
        verdict = "CLEAR TO UPGRADE"
    lines.append(verdict)
    return "\n".join(lines)
