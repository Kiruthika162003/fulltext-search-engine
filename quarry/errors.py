"""Errors that name the mistake, because a refusal is documentation.

Every raised error in this engine says what was wrong in the words
the caller was thinking in: a query that parses to nothing, a field
the schema never declared, a segment consulted after it was merged
away. The hierarchy stays shallow so callers catch QuarryError for
everything or the specific class when recovery differs, and no
error carries machinery beyond its message and an optional detail
map, because an error object with behaviour is a second bug waiting
inside the first.
"""

from __future__ import annotations


class QuarryError(Exception):
    def __init__(self, message: str, **details):
        super().__init__(message)
        self.details = details


class Invalid(QuarryError):
    """The request contradicts itself; nothing was indexed or read."""


class Missing(QuarryError):
    """Something referenced does not exist under that name."""


class Frozen(QuarryError):
    """A write arrived at something sealed against writes."""


class Retired(QuarryError):
    """A reader consulted a segment the merge already swallowed."""
