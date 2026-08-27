"""Delta and varint coding: posting lists priced in actual bytes.

Posting lists store sorted document ids, and the two classic
observations pay for most of an index's disk: sorted ids can be
stored as gaps, which are small, and small numbers can be
stored in fewer bytes, seven payload bits per byte with the
high bit saying whether another byte follows. The codec here
does both, with the contracts stated: encoding demands a
strictly ascending list because a repeated id would encode as
a gap of zero and decode into a phantom duplicate, decoding
refuses a stream that ends mid-number rather than guessing the
tail, and round-tripping is pinned by test on every shape that
has ever caused trouble, single ids, dense runs, and gaps past
the one-byte boundary. The savings report compares against
flat eight-byte ids, measured on the actual list, because
compression quoted from the paper instead of the data is
marketing.
"""

from __future__ import annotations

from quarry.errors import Invalid


def encode_varint(value: int) -> bytes:
    if value < 0:
        raise Invalid("varints carry counts and gaps, never debt")
    out = bytearray()
    while True:
        piece = value & 0x7F
        value >>= 7
        if value:
            out.append(piece | 0x80)
        else:
            out.append(piece)
            return bytes(out)


def decode_varint(data: bytes, start: int) -> tuple[int, int]:
    value = 0
    shift = 0
    index = start
    while True:
        if index >= len(data):
            raise Invalid(
                "the stream ends mid-number; decoding a guess "
                "would invent a document"
            )
        piece = data[index]
        value |= (piece & 0x7F) << shift
        index += 1
        if not piece & 0x80:
            return value, index
        shift += 7


def encode_postings(doc_ids: list[int]) -> bytes:
    if not doc_ids:
        raise Invalid("an empty posting list encodes nothing")
    out = bytearray()
    previous = -1
    for doc in doc_ids:
        if doc <= previous:
            raise Invalid(
                f"doc {doc} after {previous} is not ascending; a "
                f"zero gap would decode into a phantom duplicate"
            )
        gap = doc - previous - 1 if previous >= 0 else doc
        out.extend(encode_varint(gap))
        previous = doc
    return bytes(out)


def decode_postings(data: bytes) -> list[int]:
    if not data:
        raise Invalid("an empty stream holds no postings")
    out: list[int] = []
    index = 0
    previous = -1
    while index < len(data):
        gap, index = decode_varint(data, index)
        doc = gap if previous < 0 else previous + gap + 1
        out.append(doc)
        previous = doc
    return out


def savings_report(doc_ids: list[int]) -> str:
    encoded = encode_postings(doc_ids)
    flat = len(doc_ids) * 8
    packed = len(encoded)
    ratio = flat / packed
    return (
        f"{len(doc_ids)} posting(s): {flat} flat bytes -> "
        f"{packed} packed ({ratio:.1f}x), measured on this list, "
        f"not quoted from the paper"
    )
