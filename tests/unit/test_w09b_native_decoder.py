"""W09b trusted native decoder acceptance against existing RAW/YUV readers.

The tested path is W09a's same-descriptor SHA verifier, not an isolated fake
decoder. Data comes from repository-owned public fixture files.
"""
from __future__ import annotations

import hashlib
from dataclasses import replace
from threading import Event
from pathlib import Path
from uuid import uuid4

import pytest

from pixelscope.core.image_document import ImageDocument
from pixelscope.core.review_analysis_sources import snapshot_source
from pixelscope.core.review_record import (
    ReviewFingerprintV1,
    ReviewLocatorV1,
    ReviewNativeSignatureV1,
    ReviewSourceV1,
    canonical_json,
)
from pixelscope.io.raw_profile import RawProfile
from pixelscope.io.raw_reader import read_raw
from pixelscope.io.review_native_decoder import (
    ProductionNativeCandidateDecoder,
    UnsupportedNativeCandidate,
)
from pixelscope.io.review_repository import ReviewCancelled, verify_review_source
from pixelscope.ui.review_restore_controller import ApprovedCandidate, _verify_batch
from pixelscope.io.yuv_profile import YuvProfile
from pixelscope.io.yuv_reader import read_yuv

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "test_data" / "manual" / "raw_chart_set"
YUV = ROOT / "test_data" / "manual" / "yuv_chart_set"


def _stored_source(path: Path, profile: RawProfile | YuvProfile) -> ReviewSourceV1:
    if isinstance(profile, RawProfile):
        pixels = read_raw(path, profile)
        doc = ImageDocument(
            path, "fixture", pixels, profile.channel_layout, profile.bit_depth, raw_profile=profile
        )
    else:
        frame = read_yuv(path, profile)
        doc = ImageDocument(
            path, "fixture", frame.y, frame.layout, profile.bit_depth, yuv_frame=frame
        )
    captured = snapshot_source(doc, str(uuid4()))
    signature = ReviewNativeSignatureV1(
        captured.profile_signature,
        captured.native_shape,
        captured.reference_shape,
        captured.native_dtype,
        captured.channel_layout,
        captured.effective_bits,
        canonical_json(captured.native_interpretation.to_portable(), limit=16_384),
    )
    payload = path.read_bytes()
    return ReviewSourceV1(
        captured.source_key,
        ReviewLocatorV1(path.name, local_path=str(path.resolve())),
        signature,
        ReviewFingerprintV1(
            "sha256",
            hashlib.sha256(payload).hexdigest(),
            len(payload),
            path.stat().st_mtime_ns,
            "verified",
        ),
    )


@pytest.mark.parametrize(
    "basename",
    [
        "01_gray_10bit_u16le_lsb",
        "01_gray_12bit_u16le_lsb",
        "01_gray_14bit_u16le_lsb",
        "02_bayer_10bit_01_rggb_u16le_lsb",
        "02_bayer_10bit_02_rggb_mipi_raw10",
        "02_bayer_10bit_03_rggb_packed_stream_msb",
        "02_bayer_12bit_01_rggb_u16le_msb",
        "02_bayer_12bit_02_rggb_mipi_raw12",
        "02_bayer_14bit_01_rggb_mipi_raw14",
    ],
)
def test_verified_raw_matches_production_reader_signature(basename):
    path = RAW / (basename + ".raw")
    profile = RawProfile.load_json(RAW / (basename + ".json"))
    source = _stored_source(path, profile)
    outcome = verify_review_source(source, path, ProductionNativeCandidateDecoder(profile))
    assert outcome.status == "verified", outcome.reason
    assert outcome.may_bind_historical_finding


@pytest.mark.parametrize(
    "filename,layout",
    [
        ("01_yuv444_16x12.yuv", "YUV444"),
        ("02_yuv422_16x12.yuv", "YUV422"),
        ("03_yuv420_16x12.yuv", "YUV420"),
    ],
)
def test_verified_yuv_matches_production_reader_signature(filename, layout):
    path = YUV / filename
    profile = YuvProfile(width=16, height=12, channel_layout=layout)
    source = _stored_source(path, profile)
    outcome = verify_review_source(source, path, ProductionNativeCandidateDecoder(profile))
    assert outcome.status == "verified", outcome.reason


def test_changed_native_profile_fail_closed_even_when_digest_matches(tmp_path):
    path = RAW / "02_bayer_12bit_01_rggb_u16le_msb.raw"
    profile = RawProfile.load_json(path.with_suffix(".json"))
    source = _stored_source(path, profile)
    changed = profile.copy(update={"bit_alignment": "lsb"})
    mismatch = verify_review_source(source, path, ProductionNativeCandidateDecoder(changed))
    assert mismatch.status == "unsupported_profile"
    assert not mismatch.may_bind_historical_finding

    # Candidate relink is never implied by matching basename or SHA.
    relocated = tmp_path / path.name
    relocated.write_bytes(path.read_bytes())
    without_consent = verify_review_source(
        source, relocated, ProductionNativeCandidateDecoder(profile)
    )
    assert without_consent.status == "candidate_unverified"
    with_consent = verify_review_source(
        source, relocated, ProductionNativeCandidateDecoder(profile), confirmed_by_user=True
    )
    assert with_consent.status == "verified"


def test_candidate_decode_is_bounded_and_not_cached(tmp_path):
    path = RAW / "02_bayer_10bit_02_rggb_mipi_raw10.raw"
    profile = RawProfile.load_json(path.with_suffix(".json"))
    source = _stored_source(path, profile)
    limited = ProductionNativeCandidateDecoder(profile, max_decode_bytes=1)
    rejected = verify_review_source(source, path, limited)
    assert rejected.status == "unsupported_profile"
    assert not rejected.may_bind_historical_finding

    changed = tmp_path / path.name
    changed.write_bytes(path.read_bytes() + b"changed")
    altered = verify_review_source(
        source, changed, ProductionNativeCandidateDecoder(profile), confirmed_by_user=True
    )
    assert altered.status == "changed"
    assert not altered.may_bind_historical_finding

    with pytest.raises(UnsupportedNativeCandidate):
        ProductionNativeCandidateDecoder(profile, max_decode_bytes=0)
    # Caller mutation cannot alter an approved adapter's frozen interpretation.
    adapter = ProductionNativeCandidateDecoder(profile)
    original = adapter.profile.bit_alignment
    profile.bit_alignment = "lsb" if original == "msb" else "msb"
    assert adapter.profile.bit_alignment == original


def test_native_profile_variants_do_not_rebind_incorrect_geometry():
    path = YUV / "03_yuv420_16x12.yuv"
    profile = YuvProfile(width=16, height=12, channel_layout="YUV420")
    source = _stored_source(path, profile)
    bad = profile.copy(update={"channel_layout": "YUV422"})
    mismatch = verify_review_source(source, path, ProductionNativeCandidateDecoder(bad))
    assert mismatch.status == "unsupported_profile"
    assert not mismatch.may_bind_historical_finding

    # A synthetic changed source fingerprint never grants verified by size/mtime.
    modified = replace(
        source, fingerprint=replace(source.fingerprint, digest=None, state="unverified")
    )
    missing_digest = verify_review_source(modified, path, ProductionNativeCandidateDecoder(profile))
    assert missing_digest.status == "candidate_unverified"


def test_bounded_restore_batch_requires_explicit_candidate_and_relink(tmp_path):
    path = RAW / "02_bayer_10bit_02_rggb_mipi_raw10.raw"
    profile = RawProfile.load_json(path.with_suffix(".json"))
    source = _stored_source(path, profile)
    original = ApprovedCandidate(source.source_key, path.resolve(), profile, False)
    verified = _verify_batch((source,), (original,), Event())
    assert len(verified) == 1
    assert verified[0].verified
    assert verified[0].still_current()

    relocated = tmp_path / path.name
    relocated.write_bytes(path.read_bytes())
    denied = ApprovedCandidate(source.source_key, relocated.resolve(), profile, False)
    unapproved = _verify_batch((source,), (denied,), Event())
    assert not unapproved[0].verified
    assert unapproved[0].resolution.status == "candidate_unverified"

    accepted = ApprovedCandidate(source.source_key, relocated.resolve(), profile, True)
    approved = _verify_batch((source,), (accepted,), Event())
    assert approved[0].verified
    assert approved[0].resolution.status == "verified"
    relocated.write_bytes(relocated.read_bytes() + b"changed")
    assert not approved[0].still_current()

    cancelled = Event()
    cancelled.set()
    with pytest.raises(ReviewCancelled):
        _verify_batch((source,), (original,), cancelled)
