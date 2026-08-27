from __future__ import annotations

import pytest

from quarry.captokens import mint, tampered, verify
from quarry.errors import Invalid, Stale

SECRET = "server-secret-1"


def export_token():
    return mint(
        SECRET,
        "export",
        "tenant-acme",
        today=100,
        lifetime_days=7,
    )


class TestMinting:
    def test_a_token_names_verb_scope_and_death(self):
        token = export_token()
        assert token.verb == "export"
        assert token.expires_day == 107
        assert token.render().startswith("export:tenant-acme:107:")

    def test_unknown_verbs_are_refused(self):
        with pytest.raises(Invalid, match="not a capability"):
            mint(SECRET, "administer", "x", 100, 5)

    def test_scopeless_tokens_are_admin_keys_in_costume(self):
        with pytest.raises(Invalid, match="costume"):
            mint(SECRET, "export", "  ", 100, 5)

    def test_the_lifetime_ceiling_holds(self):
        with pytest.raises(Invalid, match="liability"):
            mint(SECRET, "export", "tenant-acme", 100, 90)


class TestVerification:
    def test_the_honest_token_verifies(self):
        message = verify(
            SECRET, export_token(), "export", "tenant-acme", 103
        )
        assert message == (
            "export on tenant-acme permitted until day 107"
        )

    def test_tampered_scope_breaks_the_signature(self):
        forged = tampered(export_token(), scope="tenant-rival")
        with pytest.raises(Invalid, match="does not verify"):
            verify(SECRET, forged, "export", "tenant-rival", 103)

    def test_tampered_expiry_breaks_the_signature(self):
        forged = tampered(export_token(), expires_day=9999)
        with pytest.raises(Invalid, match="does not verify"):
            verify(SECRET, forged, "export", "tenant-acme", 103)

    def test_expiry_beats_everything_after_the_signature(self):
        with pytest.raises(Stale, match="expired on day 107"):
            verify(
                SECRET, export_token(), "export", "tenant-acme", 107
            )

    def test_the_wrong_verb_is_refused_without_hints(self):
        with pytest.raises(Invalid, match="does not permit 'delete'"):
            verify(
                SECRET, export_token(), "delete", "tenant-acme", 103
            )

    def test_the_wrong_scope_is_out_of_reach(self):
        with pytest.raises(Invalid, match="does not reach"):
            verify(
                SECRET, export_token(), "export", "tenant-rival", 103
            )

    def test_the_wrong_secret_never_verifies(self):
        with pytest.raises(Invalid, match="does not verify"):
            verify(
                "other-secret",
                export_token(),
                "export",
                "tenant-acme",
                103,
            )
