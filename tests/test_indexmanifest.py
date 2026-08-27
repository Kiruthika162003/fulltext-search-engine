from __future__ import annotations

import dataclasses

import pytest

from quarry.errors import Invalid, Stale
from quarry.indexmanifest import (
    build_manifest,
    segment_digest,
    verify_manifest,
)
from quarry.schema import Schema
from quarry.segment import Segment, SegmentBuilder


def make_segment(name: str, texts: list[str]) -> Segment:
    schema = Schema()
    schema.add_text("body")
    schema.seal()
    builder = SegmentBuilder(schema=schema)
    for text in texts:
        builder.add({"body": text})
    return builder.seal(name)


def pair() -> list[Segment]:
    return [
        make_segment("alpha", ["a quiet cove", "the long walk"]),
        make_segment("beta", ["rain on the harbor"]),
    ]


class TestDigests:
    def test_the_digest_is_content_stable(self):
        left = make_segment("s", ["same text here"])
        right = make_segment("s", ["same text here"])
        assert segment_digest(left) == segment_digest(right)

    def test_deletes_change_the_digest(self):
        segment = make_segment("s", ["one doc", "two doc"])
        before = segment_digest(segment)
        segment.delete(0)
        assert segment_digest(segment) != before


class TestBuilding:
    def test_the_manifest_reads_as_one_page(self):
        manifest = build_manifest("body", "lower=1", pair())
        page = manifest.canonical_text()
        assert page.startswith("format 2\nschema body\nanalyzer lower=1")
        assert "segment alpha: 2 live of 2" in page
        assert manifest.total_live() == 3

    def test_the_id_tracks_the_content(self):
        left = build_manifest("body", "lower=1", pair())
        right = build_manifest("body", "lower=0", pair())
        assert left.manifest_id() != right.manifest_id()

    def test_zero_segments_describe_nothing(self):
        with pytest.raises(Invalid, match="nothing worth"):
            build_manifest("body", "lower=1", [])


class TestVerification:
    def test_an_honest_restore_is_restorable(self):
        segments = pair()
        manifest = build_manifest("body", "lower=1", segments)
        clean, page = verify_manifest(manifest, segments)
        assert clean
        assert page.endswith("RESTORABLE")

    def test_tampered_segments_are_named(self):
        segments = pair()
        manifest = build_manifest("body", "lower=1", segments)
        segments[0].delete(0)
        clean, page = verify_manifest(manifest, segments)
        assert not clean
        assert "alpha: digest mismatch" in page
        assert page.endswith("DO NOT RESTORE")

    def test_missing_segments_are_named(self):
        segments = pair()
        manifest = build_manifest("body", "lower=1", segments)
        clean, page = verify_manifest(manifest, segments[:1])
        assert not clean
        assert "beta: MISSING from disk" in page

    def test_stowaway_segments_are_named(self):
        segments = pair()
        manifest = build_manifest("body", "lower=1", segments[:1])
        clean, page = verify_manifest(manifest, segments)
        assert not clean
        assert "beta: on disk but not in the manifest" in page

    def test_newer_formats_refuse_with_instructions(self):
        manifest = build_manifest("body", "lower=1", pair())
        future = dataclasses.replace(manifest, format_version=9)
        with pytest.raises(Stale, match="upgrade before"):
            verify_manifest(future, pair())
