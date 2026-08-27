"""Check digits: ids typed by humans catch their own typos.

Support reads document ids over the phone, and a transposed
pair silently names the wrong record unless the id carries its
own tripwire: the Luhn digit, computed over the number and
appended, catches every single-digit slip and nearly every
adjacent transposition before the lookup runs. Stamping takes
the bare number and returns it with the digit attached;
checking strips and verifies, refusing rather than guessing
when the tail does not match, because a lookup that proceeds
past a failed check digit has disarmed the tripwire it was
given.
"""

from __future__ import annotations

from quarry.errors import Invalid


def _luhn_sum(digits: str) -> int:
    total = 0
    for index, char in enumerate(reversed(digits)):
        value = int(char)
        if index % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total


def stamp(external: int) -> str:
    if external < 0:
        raise Invalid("negative ids are nobody's document")
    body = str(external)
    check = (10 - _luhn_sum(body + "0") % 10) % 10
    return f"{body}{check}"


def verify(stamped: str) -> int:
    cleaned = stamped.strip()
    if len(cleaned) < 2 or not cleaned.isdigit():
        raise Invalid(
            f"{stamped!r} is not a stamped id; a stamped id is "
            f"the number plus its check digit"
        )
    if _luhn_sum(cleaned) % 10 != 0:
        raise Invalid(
            f"{stamped!r} fails its check digit; a slip or a "
            f"transposition happened between the record and here"
        )
    return int(cleaned[:-1])
