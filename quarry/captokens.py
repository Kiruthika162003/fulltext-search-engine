"""Capability tokens: the token IS the permission, and it expires.

Handing a partner the admin key because they need one export is
how admin keys end up in partner logs, so access is minted as
capability tokens: each names the single verb it allows, the
scope it allows it on, and the day it dies, signed with a
server secret so tampering with any field breaks the
signature. Verification checks four things in an order that
matters, signature first because an attacker's token deserves
no further reading, then expiry, then verb, then scope, and
each refusal names only its own failure, never hinting at what
a valid token would look like. Tokens are never stored
server-side, the signature is the storage, which is the point:
revocation before expiry is impossible by design, so expiry
windows stay short, and the mint refuses to sign a token
living longer than the ceiling because a capability that
outlives its purpose is a liability with a signature on it.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from quarry.errors import Invalid, Stale

VERBS = ("search", "export", "delete", "reindex")
MAX_LIFETIME_DAYS = 30


def _signature(
    secret: str, verb: str, scope: str, expires_day: int
) -> str:
    body = f"{secret}|{verb}|{scope}|{expires_day}"
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:24]


@dataclass(frozen=True)
class CapToken:
    verb: str
    scope: str
    expires_day: int
    signature: str

    def render(self) -> str:
        return (
            f"{self.verb}:{self.scope}:{self.expires_day}:"
            f"{self.signature}"
        )


def mint(
    secret: str,
    verb: str,
    scope: str,
    today: int,
    lifetime_days: int,
) -> CapToken:
    if verb not in VERBS:
        raise Invalid(
            f"{verb!r} is not a capability; the verbs are "
            f"{', '.join(VERBS)}"
        )
    if not scope.strip():
        raise Invalid(
            "a token without a scope is the admin key wearing a "
            "costume"
        )
    if not 1 <= lifetime_days <= MAX_LIFETIME_DAYS:
        raise Invalid(
            f"a lifetime of {lifetime_days} day(s) is outside "
            f"[1, {MAX_LIFETIME_DAYS}]; a capability that outlives "
            f"its purpose is a liability with a signature on it"
        )
    expires = today + lifetime_days
    return CapToken(
        verb=verb,
        scope=scope,
        expires_day=expires,
        signature=_signature(secret, verb, scope, expires),
    )


def verify(
    secret: str,
    token: CapToken,
    verb: str,
    scope: str,
    today: int,
) -> str:
    expected = _signature(
        secret, token.verb, token.scope, token.expires_day
    )
    if token.signature != expected:
        raise Invalid("the signature does not verify")
    if today >= token.expires_day:
        raise Stale(
            f"the token expired on day {token.expires_day}"
        )
    if token.verb != verb:
        raise Invalid(
            f"this token does not permit {verb!r}"
        )
    if token.scope != scope:
        raise Invalid(
            f"this token does not reach {scope!r}"
        )
    return (
        f"{verb} on {scope} permitted until day "
        f"{token.expires_day}"
    )


def tampered(token: CapToken, **changes: object) -> CapToken:
    """A test helper: the same token with one field altered."""
    fields = {
        "verb": token.verb,
        "scope": token.scope,
        "expires_day": token.expires_day,
        "signature": token.signature,
    }
    strays = set(changes) - set(fields)
    if strays:
        raise Invalid(
            f"no such field(s): {', '.join(sorted(strays))}"
        )
    fields.update(changes)
    return CapToken(**fields)
