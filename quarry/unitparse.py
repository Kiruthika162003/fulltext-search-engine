"""Human units at the door: 10k means the same thing every time.

Configs and CLIs collect numbers from humans, humans write 10k
and 2.5M and 300ms, and every ad-hoc parser disagrees about
whether k is a thousand or 1024 and whether M survives a
lowercase m. The parser here declares its table once: counts
scale by decimal thousands because nobody provisions documents
in powers of two, bytes scale by binary units with the i
spelled out, KiB and MiB, because disks are bought in the
units disks lie in, and durations name their unit explicitly,
ms, s, m, h, with bare numbers refused since a timeout of 30
is a bug wearing an integer, thirty of what. Fractions are
allowed where they divide cleanly and refused where they
cannot, half a millisecond exists and half a document does
not, and every refusal shows the accepted forms because a
parser that rejects without teaching gets worked around with
a calculator.
"""

from __future__ import annotations

from quarry.errors import Invalid

COUNT_SUFFIXES = {"": 1, "k": 1_000, "m": 1_000_000, "b": 1_000_000_000}
BYTE_SUFFIXES = {
    "b": 1,
    "kib": 1024,
    "mib": 1024**2,
    "gib": 1024**3,
}
DURATION_SUFFIXES = {"ms": 1, "s": 1000, "m": 60_000, "h": 3_600_000}


def _split(text: str) -> tuple[float, str]:
    cleaned = text.strip().lower()
    if not cleaned:
        raise Invalid("emptiness is not a quantity")
    digits = ""
    for index, char in enumerate(cleaned):
        if char.isdigit() or char == ".":
            digits += char
        else:
            suffix = cleaned[index:].strip()
            break
    else:
        suffix = ""
    if not digits:
        raise Invalid(f"{text!r} holds no number at all")
    try:
        value = float(digits)
    except ValueError as broken:
        raise Invalid(f"{digits!r} is not a number") from broken
    return value, suffix


def parse_count(text: str) -> int:
    value, suffix = _split(text)
    scale = COUNT_SUFFIXES.get(suffix)
    if scale is None:
        listed = ", ".join(
            repr(key) for key in COUNT_SUFFIXES if key
        )
        raise Invalid(
            f"{text!r}: counts take {listed}, decimal thousands; "
            f"nobody provisions documents in powers of two"
        )
    scaled = value * scale
    if scaled != int(scaled):
        raise Invalid(
            f"{text!r} is {scaled} of a thing; half a document "
            f"does not exist"
        )
    return int(scaled)


def parse_bytes(text: str) -> int:
    value, suffix = _split(text)
    scale = BYTE_SUFFIXES.get(suffix)
    if scale is None:
        raise Invalid(
            f"{text!r}: bytes take b, kib, mib, gib, the units "
            f"disks lie in, with the i spelled out"
        )
    scaled = value * scale
    if scaled != int(scaled):
        raise Invalid(
            f"{text!r} lands between bytes; storage is integers"
        )
    return int(scaled)


def parse_duration_ms(text: str) -> int:
    value, suffix = _split(text)
    if suffix == "":
        raise Invalid(
            f"{text!r}: a timeout of {text.strip()} is a bug "
            f"wearing an integer, thirty of what; name ms, s, m, "
            f"or h"
        )
    scale = DURATION_SUFFIXES.get(suffix)
    if scale is None:
        raise Invalid(
            f"{text!r}: durations take ms, s, m, h"
        )
    scaled = value * scale
    if scaled != int(scaled):
        raise Invalid(
            f"{text!r} lands between milliseconds; the clock "
            f"does not tick there"
        )
    return int(scaled)
