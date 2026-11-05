"""W09b Finding library: strict metadata edits, revision-aware persistence and offline gate."""
from __future__ import annotations

import hashlib
from dataclasses import replace
from uuid import uuid4

import pytest

from pixelscope.core.review_analysis_native import AnalysisNativeInterpretationV1
from pixelscope.core.review_record import (
    ReviewAnalysisCaptureV1,
    ReviewFindingV1,
    ReviewFingerprintV1,
    ReviewLocatorV1,
    ReviewNativeSignatureV1,
    ReviewSourceV1,
    ReviewValidationError,
    utc_now,
)
from pixelscope.core.review_view_state import ReviewViewStateV1
from pixelscope.core.review_workflow import ReviewLibrary
from pixelscope.io.review_repository import ReviewConflictError, SourceResolutionV1


def _sources(tmp_path):
    result = []
    for name in ("ref.raw", "target.raw"):
        path = tmp_path / name
        payload = b"pixel-source:" + name.encode("ascii")
        path.write_bytes(payload)
        signature = ReviewNativeSignatureV1(
            "1" * 64,
            (4, 5),
            (4, 5),
            "uint8",
            "GRAY",
            8,
            __import__("json")
            .dumps(
                AnalysisNativeInterpretationV1().to_portable(),
                sort_keys=True,
                separators=(",", ":"),
            )
            .encode("utf-8"),
        )
        result.append(
            ReviewSourceV1(
                str(uuid4()),
                ReviewLocatorV1(path.name),
                signature,
                ReviewFingerprintV1(
                    "sha256",
                    hashlib.sha256(payload).hexdigest(),
                    len(payload),
                    path.stat().st_mtime_ns,
                    "verified",
                ),
            )
        )
    return tuple(result)


def _finding(sources, roi, *, title="halo"):
    keys = tuple(s.source_key for s in sources)
    state = ReviewViewStateV1(
        reference_source_key=keys[0],
        page_source_keys=keys,
        active_source_key=keys[1],
        primary_source_key=keys[0],
        layout_kind="Grid 2x2",
        presentation_mode="originals",
        sync_enabled=True,
        center_ref_xy=(2.0, 1.5),
        physical_scale=1.0,
        reference_shape=(4, 5),
        source_shapes_ref={key: (4, 5) for key in keys},
        per_source={},
    )
    return ReviewFindingV1(
        id=str(uuid4()),
        title=title,
        note="한글 메모",
        tags=("halo",),
        captured_utc=utc_now(),
        source_keys=keys,
        reference_key=keys[0],
        pair_target_key=keys[1],
        view_state=state,
        roi_ref=roi,
        line_ref=(0, 0, 4, 3),
        channel="All",
        display_gain=1.0,
        difference_intent=None,
        analysis=(ReviewAnalysisCaptureV1("unavailable", reason="not calculated"),),
        availability="unavailable",
    )


def test_three_named_findings_edit_delete_save_restart_and_cas(tmp_path):
    library = ReviewLibrary()
    sources = _sources(tmp_path)
    rois = [(0, 0, 2, 2), (1, 1, 2, 2), (2, 1, 3, 2)]
    findings = [library.add(_finding(sources, roi), sources) for roi in rois]
    assert tuple(f.roi_ref for f in library.document.findings) == tuple(rois)

    library.edit(
        findings[1].id,
        title="Texture loss / 紋理",
        note="기록 Δ has metadata",
        tags=("edge", "Δ"),
    )
    assert library.get(findings[1].id).roi_ref == rois[1]
    assert library.get(findings[1].id).note == "기록 Δ has metadata"
    first = library.save(tmp_path / "inspection")
    assert first.path.name == "inspection.pxreview"
    assert first.committed and library.dirty is False

    restarted = ReviewLibrary()
    restored = restarted.open(first.path)
    assert [f.roi_ref for f in restored.findings] == rois
    assert restored.findings[1].title == "Texture loss / 紋理"
    assert restored.findings[1].analysis[0].status == "unavailable"

    restarted.delete(findings[2].id)
    changed = restarted.save(first.path, overwrite=True)
    assert changed.revision_sha256 != first.revision_sha256
    assert len(ReviewLibrary().open(changed.path).findings) == 2
    library.edit(findings[0].id, title="conflict", note="", tags=())
    with pytest.raises(ReviewConflictError, match="revision|changed|conflict"):
        library.save(first.path, overwrite=True)


def test_invalid_metadata_and_same_uuid_conflict_never_mutate_library(tmp_path):
    lib = ReviewLibrary()
    sources = _sources(tmp_path)
    finding = _finding(sources, (0, 0, 2, 2))
    lib.add(finding, sources)
    before = lib.document.to_bytes()
    with pytest.raises(ReviewValidationError):
        lib.edit(finding.id, title="", note="", tags=())
    assert lib.document.to_bytes() == before
    with pytest.raises(ReviewValidationError):
        lib.add(
            replace(finding, id=str(uuid4())),
            (
                replace(
                    sources[0],
                    native_signature=replace(
                        sources[0].native_signature, profile_signature="2" * 64
                    ),
                ),
                sources[1],
            ),
        )
    assert lib.document.to_bytes() == before
    with pytest.raises(KeyError):
        lib.delete(str(uuid4()))
    assert lib.document.to_bytes() == before


def test_corrupt_load_and_future_schema_leave_active_library_unchanged(tmp_path):
    lib = ReviewLibrary()
    sources = _sources(tmp_path)
    lib.add(_finding(sources, (1, 1, 2, 2)), sources)
    initial = lib.document.to_bytes()
    corrupt = tmp_path / "corrupt.pxreview"
    corrupt.write_bytes(b"{")
    with pytest.raises(Exception):
        lib.open(corrupt)
    assert lib.document.to_bytes() == initial
    future = tmp_path / "future.pxreview"
    future.write_bytes(initial.replace(b'"schema_version":1', b'"schema_version":999'))
    with pytest.raises(Exception):
        lib.open(future)
    assert lib.document.to_bytes() == initial


def test_preflight_offline_finding_requires_all_sources_verified(tmp_path):
    lib = ReviewLibrary()
    sources = _sources(tmp_path)
    finding = lib.add(_finding(sources, (1, 1, 2, 2)), sources)
    verified = {
        item.source_key: SourceResolutionV1(
            item.source_key,
            "verified",
            str((tmp_path / item.locator.basename).resolve()),
            True,
            "digest_match",
            "native interpretation matched",
        )
        for item in sources
    }
    assert lib.preflight_finding(finding.id, verified) == finding
    with pytest.raises(ReviewValidationError, match="unverified"):
        lib.preflight_finding(finding.id, {sources[0].source_key: verified[sources[0].source_key]})
    changed = SourceResolutionV1(
        sources[1].source_key,
        "changed",
        verified[sources[1].source_key].candidate_path,
        True,
        "digest_mismatch",
        "changed source",
    )
    with pytest.raises(ReviewValidationError, match="unverified"):
        lib.preflight_finding(
            finding.id,
            {
                sources[0].source_key: verified[sources[0].source_key],
                sources[1].source_key: changed,
            },
        )
