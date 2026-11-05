"""W09a strict Review v1, atomic persistence and source identity regression tests."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import threading
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest

from pixelscope.core.comparison_set import Session, SessionSource
from pixelscope.core.review_analysis import (
    AnalysisMeasurementV1,
    AnalysisSnapshotV1,
    AnalysisSourceV1,
    PresentedAnalysisTokenV1,
    serialize_analysis_context,
)
from pixelscope.core.review_analysis_native import AnalysisNativeInterpretationV1
from pixelscope.core.review_record import (
    MAX_REVIEW_BYTES,
    ReviewAnalysisCaptureV1,
    ReviewDifferenceIntentV1,
    ReviewDocumentV1,
    ReviewFindingV1,
    ReviewFingerprintV1,
    ReviewLocatorV1,
    ReviewNativeSignatureV1,
    ReviewSourceV1,
    ReviewValidationError,
    ReviewWorkspaceIntentV1,
    canonical_json,
    new_review,
    project_portable_review,
    utc_now,
)
from pixelscope.core.review_view_state import ReviewViewStateV1
from pixelscope.io.comparison_set_repository import ComparisonSetRepository
from pixelscope.io.review_repository import (
    CandidateDecodeProbeV1,
    CandidateNativeDecoderV1,
    ReviewCancelled,
    ReviewConflictError,
    ReviewRepository,
    SourceHashUnstable,
    normalize_review_path,
    stream_source_sha256,
    verify_review_source,
)


def _key() -> str:
    return str(uuid4())


def _native(digest: str = "1" * 64) -> ReviewNativeSignatureV1:
    return ReviewNativeSignatureV1.from_dict(
        {
            "profile_signature": digest,
            "native_shape": [4, 5],
            "reference_shape": [4, 5],
            "native_dtype": "uint8",
            "channel_layout": "GRAY",
            "effective_bits": 8,
            "native_interpretation": AnalysisNativeInterpretationV1().to_portable(),
        }
    )


class _FixtureNativeDecoder(CandidateNativeDecoderV1):
    """Only test fixtures implement this decoder; W09b must supply real native IO."""

    def __init__(
        self, expected: bytes, signature: ReviewNativeSignatureV1 | None = None
    ) -> None:
        self.expected = expected
        self.signature = signature

    def decode_signature(self, probe: CandidateDecodeProbeV1) -> ReviewNativeSignatureV1:
        actual = probe.read()
        if actual != self.expected:
            raise ValueError("unexpected decoded fixture input")
        return self.signature if self.signature is not None else _native()


def _decode_fixture_bytes(
    expected: bytes, signature: ReviewNativeSignatureV1 | None = None
) -> CandidateNativeDecoderV1:
    return _FixtureNativeDecoder(expected, signature)



def _source(
    path: Path,
    *,
    source_key: str | None = None,
    sha: str | None = None,
    local: bool = False,
    signature: ReviewNativeSignatureV1 | None = None,
) -> ReviewSourceV1:
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest() if sha == "auto" else sha
    return ReviewSourceV1(
        source_key or _key(),
        ReviewLocatorV1(path.name, local_path=str(path.resolve()) if local else None),
        signature or _native(),
        ReviewFingerprintV1(
            "sha256",
            digest,
            len(payload),
            path.stat().st_mtime_ns,
            "verified" if digest is not None else "unverified",
        ),
    )


def _view(keys: tuple[str, ...]) -> ReviewViewStateV1:
    return ReviewViewStateV1(
        reference_source_key=keys[0],
        page_source_keys=keys,
        active_source_key=keys[0],
        primary_source_key=keys[0],
        layout_kind="Grid 2x2" if len(keys) > 1 else "Auto",
        presentation_mode="originals",
        sync_enabled=True,
        center_ref_xy=(2.0, 1.5),
        physical_scale=2.0,
        reference_shape=(4, 5),
        source_shapes_ref={k: (4, 5) for k in keys},
        per_source={},
    )


def _snapshot(source_key: str) -> AnalysisSnapshotV1:
    source = AnalysisSourceV1(
        source_key=source_key,
        document_id="runtime-id-NOT-PORTABLE",
        generation=3,
        native_shape=(4, 5),
        reference_shape=(4, 5),
        native_dtype="uint8",
        channel_layout="GRAY",
        effective_bits=8,
        profile_signature="1" * 64,
        native_interpretation=AnalysisNativeInterpretationV1(),
    )
    token = PresentedAnalysisTokenV1(
        feature="statistics",
        request_id="request-42",
        request_epoch=7,
        source_documents=((source.document_id, 3),),
        source_keys=(source_key,),
        roi_ref=(1, 1, 2, 2),
        channel="All",
        domain="native",
        profile_signatures=("1" * 64,),
        difference_cache_key=None,
    )
    return AnalysisSnapshotV1(
        snapshot_id=_key(),
        captured_utc=utc_now(),
        token=token,
        sources=(source,),
        measurements=(
            AnalysisMeasurementV1(
                source_key,
                "Gray",
                "mean",
                10.25,
                4,
            ),
        ),
    )


def _finding(
    keys: tuple[str, ...],
    *,
    title: str = "색 번짐 / halo",
    analysis: tuple[ReviewAnalysisCaptureV1, ...] = (),
    finding_id: str | None = None,
) -> ReviewFindingV1:
    return ReviewFindingV1(
        id=finding_id or _key(),
        title=title,
        note="고주파 노이즈 Δ↔ 詳細\nline 2",
        tags=("색차", "Edge_α", "테스트"),
        captured_utc=utc_now(),
        source_keys=keys,
        reference_key=keys[0],
        pair_target_key=keys[1] if len(keys) > 1 else None,
        view_state=_view(keys),
        roi_ref=(1, 1, 2, 2),
        line_ref=(0, 0, 4, 3),
        channel="All",
        display_gain=1.0,
        difference_intent=(
            ReviewDifferenceIntentV1(keys[0], keys[1], "All", "Absolute", 10.0, 1, "Active ROI")
            if len(keys) > 1
            else None
        ),
        analysis=analysis,
        availability="available"
        if any(x.status == "captured" for x in analysis)
        else "unavailable",
    )


def _review(tmp_path: Path, *, with_analysis: bool = False) -> ReviewDocumentV1:
    a, b = tmp_path / "a.raw", tmp_path / "b.raw"
    a.write_bytes(b"source-a-content")
    b.write_bytes(b"source-b-content")
    sources = (_source(a, sha="auto"), _source(b, sha="auto"))
    keys = tuple(s.source_key for s in sources)
    analysis = (
        (ReviewAnalysisCaptureV1.from_snapshot(_snapshot(keys[0])),)
        if (with_analysis)
        else (ReviewAnalysisCaptureV1("unavailable", reason="not calculated"),)
    )
    finding = _finding(keys, analysis=analysis)
    return replace(
        new_review(sources),
        workspace_intent=ReviewWorkspaceIntentV1(
            source_order=keys,
            selected_keys=keys,
            page_anchor_key=keys[0],
            active_key=keys[1],
            primary_key=keys[0],
            layout_mode="Multi View",
            display_gain=2.0,
        ),
        findings=(
            finding,
            replace(
                _finding(keys, title="Texture loss 粒子"), analysis=(), availability="unavailable"
            ),
        ),
    )



def test_w02_w04_identity_cannot_be_cross_bound(tmp_path):
    doc = _review(tmp_path, with_analysis=True)
    ref, target = (source.source_key for source in doc.sources)
    original = doc.to_dict()

    mismatched_profile = copy.deepcopy(original)
    mismatched_profile["sources"][0]["native_signature"]["profile_signature"] = "f" * 64
    with pytest.raises(ReviewValidationError, match="W02 source interpretation"):
        ReviewDocumentV1.from_dict(mismatched_profile)

    mismatched_view = copy.deepcopy(original)
    mismatched_view["findings"][0]["view_state"]["source_shapes_ref"][target] = [5, 5]
    with pytest.raises(ReviewValidationError, match="W04 shape"):
        ReviewDocumentV1.from_dict(mismatched_view)

    mismatched_roi = copy.deepcopy(original)
    mismatched_roi["findings"][0]["analysis"][0]["context"]["roi_ref"] = [0, 0, 2, 2]
    with pytest.raises(ReviewValidationError, match="W02 analysis ROI"):
        ReviewDocumentV1.from_dict(mismatched_roi)

    mismatched_sha = copy.deepcopy(original)
    mismatched_sha["findings"][0]["analysis"][0]["context"]["sources"][0][
        "sha256"
    ] = "f" * 64
    with pytest.raises(ReviewValidationError, match="fingerprint"):
        ReviewDocumentV1.from_dict(mismatched_sha)

    invalid_snapshot_id = copy.deepcopy(original)
    invalid_snapshot_id["findings"][0]["analysis"][0]["context"]["snapshot_id"] = "opaque"
    with pytest.raises(ReviewValidationError, match="UUID"):
        ReviewDocumentV1.from_dict(invalid_snapshot_id)


def test_reject_w02_channel_and_scope_mismatch(tmp_path):
    doc = _review(tmp_path, with_analysis=True)
    original = doc.to_dict()

    wrong_channel = copy.deepcopy(original)
    wrong_channel["findings"][0]["analysis"][0]["context"]["channel"] = "R"
    with pytest.raises(ReviewValidationError, match="channel"):
        ReviewDocumentV1.from_dict(wrong_channel)

    wrong_scope = copy.deepcopy(original)
    context = wrong_scope["findings"][0]["analysis"][0]["context"]
    context["roi_ref"] = None
    context["scope"] = "full"
    with pytest.raises(ReviewValidationError, match="scope/ROI"):
        ReviewDocumentV1.from_dict(wrong_scope)

    # W02 contexts do not carry enough trusted recipe detail to silently
    # attach a Difference snapshot without explicit pair/cache/region checks.
    incomplete_difference = copy.deepcopy(original)
    diff_context = incomplete_difference["findings"][0]["analysis"][0]["context"]
    diff_context["feature"] = "difference"
    diff_context["difference_cache_key"] = "a" * 64
    with pytest.raises(ReviewValidationError, match="pair order"):
        ReviewDocumentV1.from_dict(incomplete_difference)

    complete_difference = copy.deepcopy(incomplete_difference)
    context_sources = complete_difference["findings"][0]["analysis"][0]["context"]["sources"]
    second = copy.deepcopy(context_sources[0])
    second["source_key"] = doc.sources[1].source_key
    complete_difference["findings"][0]["analysis"][0]["context"]["sources"].append(second)
    complete_context = complete_difference["findings"][0]["analysis"][0]["context"]
    complete_context["presentation"] = {
        "mode": "Absolute",
        "gain": "1",
        "threshold": "10",
        "pair_a": doc.sources[0].source_key,
        "pair_b": doc.sources[1].source_key,
    }
    ReviewDocumentV1.from_dict(complete_difference)

    for field, value in (("mode", "Mask"), ("gain", "2"), ("threshold", "11")):
        altered = copy.deepcopy(complete_difference)
        altered["findings"][0]["analysis"][0]["context"]["presentation"][field] = value
        with pytest.raises(ReviewValidationError, match="presentation recipe"):
            ReviewDocumentV1.from_dict(altered)

    swapped = copy.deepcopy(complete_difference)
    swapped["findings"][0]["analysis"][0]["context"]["sources"].reverse()
    with pytest.raises(ReviewValidationError, match="pair order"):
        ReviewDocumentV1.from_dict(swapped)


def test_review_records_do_not_retain_mutable_caller_sequences(tmp_path):
    doc = _review(tmp_path)
    keys = [s.source_key for s in doc.sources]
    selected = keys[:]
    workspace = ReviewWorkspaceIntentV1(source_order=keys, selected_keys=selected)
    selected.clear()
    keys.clear()
    assert len(workspace.source_order) == 2
    assert len(workspace.selected_keys) == 2

    tags = ["edge", "banding"]
    finding_sources = list(doc.findings[0].source_keys)
    analyses = list(doc.findings[0].analysis)
    finding = replace(doc.findings[0], tags=tags,
                      source_keys=finding_sources, analysis=analyses)
    tags.append("mutation")
    finding_sources.clear()
    analyses.clear()
    assert finding.tags == ("edge", "banding")
    assert len(finding.source_keys) == 2
    assert len(finding.analysis) == 1

    sources, findings = list(doc.sources), list(doc.findings)
    durable = replace(doc, sources=sources, findings=findings)
    sources.clear()
    findings.clear()
    assert len(durable.sources) == 2
    assert len(durable.findings) == 2


def test_source_resolution_requires_canonical_id_and_candidate_bound_callback(tmp_path):
    from pixelscope.io.review_repository import SourceResolutionV1

    file = tmp_path / "candidate.raw"
    file.write_bytes(b"verified-source")
    source = _source(file, sha="auto", local=True)
    paths = []

    class InspectCandidate(CandidateNativeDecoderV1):
        def decode_signature(self, probe: CandidateDecodeProbeV1) -> ReviewNativeSignatureV1:
            paths.append(probe.path)
            assert probe.path == file
            assert probe.read() == file.read_bytes()
            return _native()

    result = verify_review_source(source, file, InspectCandidate())
    assert result.status == "verified"
    assert paths == [file]
    assert result.may_bind_historical_finding

    untrusted_dto = verify_review_source(source, file, _native())
    assert untrusted_dto.status == "candidate_unverified"
    assert not untrusted_dto.may_bind_historical_finding
    # Merely wrapping cached data in a callable must never authorize binding.
    cached_callback = verify_review_source(source, file, lambda probe: _native())
    assert cached_callback.status == "candidate_unverified"
    assert not cached_callback.may_bind_historical_finding
    with pytest.raises(ReviewValidationError, match="UUID"):
        SourceResolutionV1("not-uuid", "verified", str(file), True, "digest_match", "reason")


def test_serialized_review_limit_includes_terminal_newline(tmp_path, monkeypatch):
    import pixelscope.core.review_record as review_module

    doc = _review(tmp_path)
    encoded = doc.to_bytes()
    monkeypatch.setattr(review_module, "MAX_REVIEW_BYTES", len(encoded) - 1)
    with pytest.raises(ReviewValidationError):
        doc.to_bytes()


def test_minimal_zero_finding_roundtrip_and_reject_path_traversal(tmp_path):
    repository = ReviewRepository()
    minimal = new_review()
    target = tmp_path / "minimal"
    result = repository.save(target, minimal)
    assert result.path.name == "minimal.pxreview"
    reopened = repository.load(result.path)
    assert reopened.to_dict() == minimal.to_dict()
    assert reopened.findings == ()
    assert reopened.sources == ()
    for relative in ("../escape", "/absolute", "C:/drive", "//server/share", "a/../b"):
        with pytest.raises(ReviewValidationError):
            ReviewLocatorV1("safe.raw", relative_hint=relative)


def test_roundtrip_multiple_findings_unicode_w02_w04_and_session_unchanged(tmp_path):
    repo = ReviewRepository()
    doc = _review(tmp_path, with_analysis=True)
    target = tmp_path / "검증회차"
    result = repo.save(target, doc)
    assert result.path.suffix == ".pxreview"
    assert result.path.exists()
    reopened, revision = repo.load_with_revision(result.path)
    assert reopened.to_dict() == doc.to_dict()
    assert revision == result.revision_sha256
    assert len(reopened.findings) == 2
    assert "고주파" in reopened.findings[0].note
    assert reopened.findings[0].tags[1] == "Edge_α"
    assert reopened.findings[0].view_state.to_dict() == doc.findings[0].view_state.to_dict()
    context = reopened.findings[0].analysis[0].to_dict()["context"]
    assert context["measurements"][0]["value"] == 10.25
    assert "runtime-id-NOT-PORTABLE" not in result.path.read_text(encoding="utf-8")

    # Session v1 continues to use its original repository and exact kind.
    local_path = str((tmp_path / "a.raw").resolve())
    session = Session(registered_sources=(SessionSource(local_path),), selected_paths=(local_path,))
    old_repo = ComparisonSetRepository()
    legacy = old_repo.to_payload(session)
    assert legacy["kind"] == "pixelscope-session"
    assert old_repo.from_payload(legacy) == session


def test_w02_snapshot_to_capture_preserves_portable_wire(tmp_path):
    doc = _review(tmp_path)
    snap = _snapshot(doc.sources[0].source_key)
    captured = ReviewAnalysisCaptureV1.from_snapshot(snap)
    assert captured.to_dict()["context"] == json.loads(
        serialize_analysis_context(snap).decode("utf-8")
    )
    again = ReviewAnalysisCaptureV1.from_dict(captured.to_dict())
    assert again.to_dict() == captured.to_dict()
    explicitly_nonfinite = replace(
        snap,
        measurements=(
            AnalysisMeasurementV1(
                doc.sources[0].source_key,
                "Gray",
                "mean",
                None,
                4,
                state="nan",
            ),
        ),
    )
    state = ReviewAnalysisCaptureV1.from_snapshot(explicitly_nonfinite).to_dict()["context"][
        "measurements"
    ][0]
    assert state["state"] == "nan"
    assert state["value"] is None


def test_strict_root_version_unknown_keys_and_corrupt_utf8(tmp_path):
    doc = _review(tmp_path)
    original = doc.to_dict()
    for key, value in (
        ("schema_version", 2),
        ("schema_version", True),
        ("kind", "pixelscope-session"),
    ):
        altered = dict(original, **{key: value})
        with pytest.raises(ReviewValidationError):
            ReviewDocumentV1.from_bytes(canonical_json(altered))
    altered = dict(original, extra_future_field=4)
    with pytest.raises(ReviewValidationError):
        ReviewDocumentV1.from_dict(altered)
    for raw in (b"{", b"\xff", b'{"kind":1,"kind":2}', b'{"x":NaN}'):
        with pytest.raises(ReviewValidationError):
            ReviewDocumentV1.from_bytes(raw)


def test_missing_required_invalid_types_and_nonfinite(tmp_path):
    doc = _review(tmp_path)
    original = doc.to_dict()
    for removal in ("sources", "workspace_intent", "app_version", "findings"):
        altered = dict(original)
        del altered[removal]
        with pytest.raises(ReviewValidationError):
            ReviewDocumentV1.from_dict(altered)
    altered = doc.to_dict()
    altered["workspace_intent"]["display_gain"] = True
    with pytest.raises(ReviewValidationError):
        ReviewDocumentV1.from_dict(altered)
    altered = doc.to_dict()
    altered["findings"][0]["display_gain"] = float("nan")
    with pytest.raises((ReviewValidationError, ValueError)):
        ReviewDocumentV1.from_dict(altered)
    altered = doc.to_dict()
    altered["sources"][0]["fingerprint"]["size_bytes"] = True
    with pytest.raises(ReviewValidationError):
        ReviewDocumentV1.from_dict(altered)


def test_duplicate_source_finding_ids_and_reference_geometry(tmp_path):
    doc = _review(tmp_path)
    altered = doc.to_dict()
    altered["sources"][1]["source_key"] = altered["sources"][0]["source_key"]
    with pytest.raises(ReviewValidationError, match="duplicate"):
        ReviewDocumentV1.from_dict(altered)
    altered = doc.to_dict()
    altered["findings"][1]["id"] = altered["findings"][0]["id"]
    with pytest.raises(ReviewValidationError, match="duplicate"):
        ReviewDocumentV1.from_dict(altered)
    altered = doc.to_dict()
    altered["findings"][0]["roi_ref"]["width"] = 999
    with pytest.raises(ReviewValidationError, match="ROI"):
        ReviewDocumentV1.from_dict(altered)


def test_resource_limits_duplicate_nested_keys_and_text_budget(tmp_path):
    doc = _review(tmp_path)
    altered = doc.to_dict()
    altered["findings"] = [altered["findings"][0]] * 1001
    with pytest.raises(ReviewValidationError):
        ReviewDocumentV1.from_dict(altered)
    altered = doc.to_dict()
    altered["findings"][0]["note"] = "한" * 12000
    with pytest.raises(ReviewValidationError):
        ReviewDocumentV1.from_dict(altered)
    altered = doc.to_dict()
    altered["extensions"] = {"nested": [0]}
    current = altered["extensions"]["nested"]
    for _ in range(50):
        current.append([])
        current = current[-1]
    with pytest.raises(ReviewValidationError):
        ReviewDocumentV1.from_bytes(json.dumps(altered).encode())
    with pytest.raises(ReviewValidationError):
        ReviewDocumentV1.from_bytes(b" " * (MAX_REVIEW_BYTES + 1))
    with pytest.raises(ReviewValidationError, match="duplicate"):
        ReviewDocumentV1.from_bytes(
            doc.to_bytes().replace(
                b'"schema_version":1,', b'"schema_version":1,"schema_version":1,'
            )
        )


def test_local_path_opt_in_and_portable_projection_excludes_sensitive_data(tmp_path):
    doc = _review(tmp_path)
    sensitive = str((tmp_path / "PrivateUser" / "secrets" / "sample.raw").resolve())
    sources = (
        replace(doc.sources[0], locator=ReviewLocatorV1("private.raw", local_path=sensitive)),
        doc.sources[1],
    )
    with pytest.raises(ReviewValidationError, match="opt-in"):
        replace(doc, sources=sources)
    local = replace(
        doc,
        sources=sources,
        allow_local_paths=True,
        extensions_json=canonical_json({"private": sensitive}),
    )
    local_bytes = local.to_bytes()
    assert sensitive.encode() in local_bytes
    portable = project_portable_review(local).to_bytes()
    assert sensitive.encode() not in portable
    assert b"private.raw" not in portable
    assert "고주파" not in portable.decode("utf-8")
    projected = json.loads(portable)
    assert projected["kind"] == "pixelscope-portable-review"
    assert projected["sources"][0]["source_id"] == "Source 1"
    assert projected["findings"][0]["title"] == "Finding 1"
    assert projected["findings"][0]["note"] == ""


def test_atomic_create_extension_collision_and_update_cas(tmp_path):
    repo = ReviewRepository()
    doc = _review(tmp_path)
    target = tmp_path / "my-report"
    assert normalize_review_path(target) == target.with_name("my-report.pxreview")
    first = repo.save(target, doc)
    original = first.path.read_bytes()
    with pytest.raises(ReviewConflictError):
        repo.save(target, doc)
    assert first.path.read_bytes() == original
    changed = replace(
        doc, updated_utc=utc_now(), findings=(replace(doc.findings[0], title="new finding"),)
    )
    with pytest.raises(ReviewConflictError):
        repo.save(target, changed, overwrite=True, expected_revision="0" * 64)
    result = repo.save(target, changed, overwrite=True, expected_revision=first.revision_sha256)
    assert repo.load(result.path).findings[0].title == "new finding"
    assert result.revision_sha256 != first.revision_sha256
    with pytest.raises(ReviewConflictError):
        repo.save(target, doc, overwrite=True, expected_revision=first.revision_sha256)


def test_overwrite_rejects_unrelated_and_session_and_source(tmp_path):
    repo = ReviewRepository()
    doc = _review(tmp_path)
    target = tmp_path / "target.pxreview"
    saved = repo.save(target, doc)
    other = replace(doc, document_id=_key())
    with pytest.raises(ReviewConflictError, match="unrelated"):
        repo.save(target, other, overwrite=True, expected_revision=saved.revision_sha256)
    bad = tmp_path / "old.pxreview"
    bad.write_text('{"kind":"pixelscope-session","schema_version":1}', encoding="utf-8")
    with pytest.raises(ReviewConflictError):
        repo.save(
            bad, doc, overwrite=True, expected_revision=hashlib.sha256(bad.read_bytes()).hexdigest()
        )
    protected = tmp_path / "protected.pxreview"
    protected.write_bytes(b"ORIGINAL SOURCE")
    with pytest.raises(ReviewConflictError):
        repo.save(protected, doc, protected_paths=[protected])
    assert protected.read_bytes() == b"ORIGINAL SOURCE"


def test_atomic_cancel_partial_write_and_permission_errors(tmp_path, monkeypatch):
    import pixelscope.io.review_repository as module

    repo = ReviewRepository()
    doc = _review(tmp_path)
    target = tmp_path / "failure.pxreview"
    with pytest.raises(ReviewCancelled):
        repo.save(target, doc, cancel=lambda: True)
    assert not list(tmp_path.glob(".failure*"))

    def fail_link(source, destination):
        raise PermissionError("denied/locked")

    with monkeypatch.context() as patch:
        patch.setattr(module.os, "link", fail_link)
        with pytest.raises(PermissionError):
            repo.save(target, doc)
    assert not target.exists()
    assert not list(tmp_path.glob(".failure*"))

    with monkeypatch.context() as patch:
        original_fsync = module.os.fsync

        def fail_fsync(fd):
            raise OSError("disk full")

        patch.setattr(module.os, "fsync", fail_fsync)
        with pytest.raises(OSError):
            repo.save(target, doc)
        patch.setattr(module.os, "fsync", original_fsync)
    assert not target.exists()
    assert not list(tmp_path.glob(".failure*"))

    # Cancellation after the flush but before publication leaves target absent.
    checks = iter((False, False, False, True))
    with pytest.raises(ReviewCancelled):
        repo.save(target, doc, cancel=lambda: next(checks, False))
    assert not target.exists()
    assert not list(tmp_path.glob(".failure*"))


def test_existing_read_only_and_locked_destination(tmp_path):
    repo = ReviewRepository()
    doc = _review(tmp_path)
    saved = repo.save(tmp_path / "readonly.pxreview", doc)
    os.chmod(saved.path, 0o444)
    try:
        with pytest.raises(ReviewConflictError):
            repo.save(saved.path, doc, overwrite=True, expected_revision=saved.revision_sha256)
    finally:
        os.chmod(saved.path, 0o644)
    locked = tmp_path / ".readonly.pxreview.lock"
    locked.write_bytes(b"locked")
    with pytest.raises(ReviewConflictError):
        repo.save(saved.path, doc, overwrite=True, expected_revision=saved.revision_sha256)
    assert locked.read_bytes() == b"locked"


def test_concurrent_create_has_exactly_one_winner(tmp_path):
    repo = ReviewRepository()
    doc = _review(tmp_path)
    target = tmp_path / "race"
    barrier = threading.Barrier(2)
    outcomes = []
    guard = threading.Lock()

    def writer():
        barrier.wait(timeout=3)
        try:
            repo.save(target, doc)
            status = "committed"
        except ReviewConflictError:
            status = "conflict"
        with guard:
            outcomes.append(status)

    threads = [threading.Thread(target=writer), threading.Thread(target=writer)]
    for item in threads:
        item.start()
    for item in threads:
        item.join(timeout=5)
        assert not item.is_alive()
    assert sorted(outcomes) == ["committed", "conflict"]


def test_hash_match_and_relink_consent_never_uses_basename(tmp_path):
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    first = first_dir / "same.raw"
    second = second_dir / "same.raw"
    first.write_bytes(b"pixel-1")
    second.write_bytes(b"pixel-2")
    source = _source(first, sha="auto", local=True)
    sig = _native()
    direct = verify_review_source(source, first, _decode_fixture_bytes(first.read_bytes(), sig))
    assert direct.status == "verified"
    assert direct.may_bind_historical_finding
    changed = verify_review_source(
        source, second, _decode_fixture_bytes(first.read_bytes(), sig), confirmed_by_user=True
    )
    assert changed.status == "changed"
    assert changed.verification == "digest_mismatch"
    second.write_bytes(first.read_bytes())
    pending = verify_review_source(source, second, _decode_fixture_bytes(first.read_bytes(), sig))
    assert pending.status == "candidate_unverified"
    assert pending.verification == "digest_match"
    approved = verify_review_source(
        source, second, _decode_fixture_bytes(first.read_bytes(), sig), confirmed_by_user=True
    )
    assert approved.status == "verified"
    assert approved.candidate_path == str(second)
    assert approved.source_key == source.source_key


def test_native_decoder_changes_file_revision_never_verifies(tmp_path):
    path = tmp_path / "decode-toc-tou.raw"
    original = b"stable-native-bytes"
    path.write_bytes(original)
    source = _source(path, sha="auto", local=True)

    class MutatingDecoder(CandidateNativeDecoderV1):
        def decode_signature(self, probe: CandidateDecodeProbeV1) -> ReviewNativeSignatureV1:
            assert probe.read() == original
            path.write_bytes(b"replacement-native")
            return _native()

    resolution = verify_review_source(source, path, MutatingDecoder())
    assert resolution.status == "candidate_unverified"
    assert not resolution.may_bind_historical_finding
    assert resolution.verification == "unavailable"


def test_missing_native_mismatch_unverified_hash_and_cancel(tmp_path):
    path = tmp_path / "raw.bin"
    path.write_bytes(b"native" * 40)
    source = _source(path, sha="auto")
    assert verify_review_source(source, None, _native()).status == "missing"
    assert verify_review_source(source, path.with_name("absent.bin"), _native()).status == "missing"
    mismatch = verify_review_source(
        source, path, _decode_fixture_bytes(path.read_bytes(), _native("2" * 64)),
        confirmed_by_user=True,
    )
    assert mismatch.status == "unsupported_profile"
    assert mismatch.verification == "digest_match"
    unverified = replace(
        source, fingerprint=replace(source.fingerprint, digest=None, state="unverified")
    )
    result = verify_review_source(
        unverified, path, _decode_fixture_bytes(path.read_bytes()), confirmed_by_user=True
    )
    assert result.status == "candidate_unverified"
    with pytest.raises(ReviewCancelled):
        stream_source_sha256(path, cancel=lambda: True)
    events = []
    probe = stream_source_sha256(
        path, progress=lambda completed, total: events.append((completed, total))
    )
    assert probe.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert events[-1] == (len(path.read_bytes()), len(path.read_bytes()))


def test_hash_revision_changed_during_progress_is_not_verified(tmp_path):
    path = tmp_path / "unstable.raw"
    path.write_bytes(b"a" * 10000)
    source = _source(path, sha="auto")

    def mutation(completed, total):
        path.write_bytes(b"b" * 10000)

    with pytest.raises(SourceHashUnstable):
        stream_source_sha256(path, progress=mutation)
    path.write_bytes(b"a" * 10000)
    result = verify_review_source(
        source, path, _decode_fixture_bytes(path.read_bytes()),
        confirmed_by_user=True, progress=mutation
    )
    assert result.status == "candidate_unverified"
    assert not result.may_bind_historical_finding
