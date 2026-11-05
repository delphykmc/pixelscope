"""W09b two-phase Finding capture: GUI immutable snapshot, worker attestation.

No implicit statistics/Difference calculations, source reload, or workspace
mutation occurs. A stage is unavailable until the native bytes and loaded
samples match on a bounded worker. The GUI owner must recheck document object
identity and generation before committing the immutable Finding to W09a.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from pixelscope.core.image_document import ImageDocument
from pixelscope.core.review_analysis import (
    AnalysisPanelAdapter,
    PresentedAnalysisTokenV1,
    capture_presented_analysis,
)
from pixelscope.core.review_analysis_sources import snapshot_source
from pixelscope.core.review_record import (
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
    utc_now,
)
from pixelscope.io.raw_profile import RawProfile
from pixelscope.io.review_native_decoder import (
    MAX_NATIVE_VERIFY_BYTES,
    ENCODED_IMAGE_EXTENSIONS,
    native_sample_sha256,
    review_candidate_decoder,
)
from pixelscope.io.review_repository import (
    ReviewCancelled,
    SourceResolutionV1,
    stream_source_sha256,
    verify_review_source,
)
from pixelscope.io.yuv_profile import YuvProfile
from pixelscope.ui.multi_compare_view import MultiCompareView
from pixelscope.ui.review_view_state_adapter import capture_review_view_state


@dataclass(frozen=True)
class CaptureSource:
    key: str
    document: ImageDocument
    generation: int
    path: Path
    profile: RawProfile | YuvProfile | None
    source: ReviewSourceV1

    def still_loaded_as(self, current: Mapping[str, ImageDocument]) -> bool:
        document = current.get(self.document.document_id)
        return (
            document is self.document
            and document.generation == self.generation
            and document.source_path is not None
            and document.source_path.resolve() == self.path
        )


@dataclass(frozen=True)
class StagedFinding:
    finding: ReviewFindingV1
    sources: tuple[CaptureSource, ...]


@dataclass(frozen=True)
class CaptureGuiFence:
    """Exact GUI/presentation state at Add; every field is compared at commit."""

    finding_id: str
    source_ids: tuple[str, ...]
    selection_ids: tuple[str, ...]
    generations: tuple[int, ...]
    page_start: int
    current_index: int
    focus_document_id: str | None
    primary_id: str
    active_document_id: str | None
    roi: tuple[int, int, int, int] | None
    line: tuple[int, int, int, int] | None
    w04: object
    pair_ids: tuple[str, ...]
    difference_controls: tuple[object, ...]
    display_gain: float
    w02_presented: object
    w02_current: object


def capture_gui_fence(window: Any, stage: StagedFinding) -> CaptureGuiFence:
    """Read-only GUI-thread revision oracle; fail closed if a view is unsettled."""
    from pixelscope.ui.display_gain import display_gain_state

    page = tuple(window.current_comparison_documents())
    expected = stage.finding
    doc_ids = tuple(document.document_id for document in page)
    keys = dict(zip(doc_ids, expected.source_keys, strict=True))
    if doc_ids != tuple(item.document.document_id for item in stage.sources):
        raise ReviewValidationError("comparison page/order changed during capture")
    analysis_panel = window.comparison_analysis_panel
    if any(analysis_panel.source_key_for_document(doc_id) != key for doc_id, key in keys.items()):
        raise ReviewValidationError("live durable Source UUID mapping changed")
    view_result = capture_review_view_state(
        window.multi_compare_view,
        keys,
        reference_source_key=expected.reference_key,
        primary_source_key=expected.view_state.primary_source_key,
        page_source_keys=expected.source_keys,
    )
    if view_result.state is None:
        raise ReviewValidationError("W04 view not settled: " + str(view_result.reason))
    reference_primary_id = next(
        (doc_id for doc_id, key in keys.items() if key == expected.view_state.primary_source_key),
        None,
    )
    primary = window._primary_document_for_page(list(page))
    if primary is None or primary.document_id != reference_primary_id:
        raise ReviewValidationError("Primary changed during capture")
    roi = window._shared_roi
    line = window._shared_line
    panel = window.difference_panel
    pair = panel.selected_documents()
    analysis = window.comparison_analysis_panel
    return CaptureGuiFence(
        finding_id=expected.id,
        source_ids=doc_ids,
        selection_ids=tuple(window._selection_order),
        generations=tuple(document.generation for document in page),
        page_start=window._page_start,
        current_index=window._current_index,
        focus_document_id=window._focus_document_id,
        primary_id=primary.document_id,
        active_document_id=window._active_document_id,
        roi=None if roi is None else (roi.x, roi.y, roi.width, roi.height),
        line=None if line is None else (line.x1, line.y1, line.x2, line.y2),
        w04=view_result.state,
        pair_ids=tuple(d.document_id for d in pair) if pair is not None else (),
        difference_controls=(
            panel.channel.currentText(),
            panel.mode.currentText(),
            panel.gain.value(),
            panel.threshold.value(),
            panel.region.currentText(),
        ),
        display_gain=display_gain_state().gain,
        w02_presented=analysis.get_presented_analysis_token(),
        w02_current=analysis.get_current_analysis_token(),
    )


def assert_same_capture_context(expected: CaptureGuiFence, actual: CaptureGuiFence) -> None:
    """No historical Finding may be committed after a GUI-context revision."""
    if actual != expected:
        raise ReviewValidationError(
            "comparison/ROI/Line/Pair/View/W02 context changed during source attestation"
        )


@dataclass(frozen=True)
class AttestedFinding:
    finding: ReviewFindingV1
    sources: tuple[ReviewSourceV1, ...]
    bindings: tuple[CaptureSource, ...]


def stage_named_finding(
    view: MultiCompareView,
    page: tuple[ImageDocument, ...],
    source_key_map: Mapping[str, str],
    *,
    title: str,
    note: str,
    tags: tuple[str, ...],
    reference_document_id: str,
    primary_document_id: str,
    pair_target_document_id: str | None,
    roi_ref: tuple[int, int, int, int] | None,
    line_ref: tuple[int, int, int, int] | None,
    channel: str,
    display_gain: float,
    difference_intent: ReviewDifferenceIntentV1 | None,
    analysis_panel: AnalysisPanelAdapter | None = None,
    persist_local_paths: bool = False,
) -> StagedFinding:
    """Capture exactly presented geometry and frozen W02 token, without any IO."""
    if not 1 <= len(page) <= 6 or len({d.document_id for d in page}) != len(page):
        raise ReviewValidationError("Finding requires one to six unique native sources")
    if not all(d.source is not None and d.source_path is not None for d in page):
        raise ReviewValidationError("Finding page contains unloaded sources")
    keys = tuple(source_key_map[d.document_id] for d in page)
    if len(set(keys)) != len(keys):
        raise ReviewValidationError("ambiguous Review source UUIDs")
    reference_key = source_key_map[reference_document_id]
    primary_key = source_key_map[primary_document_id]
    pair_key = (
        source_key_map[pair_target_document_id] if pair_target_document_id is not None else None
    )
    capture = capture_review_view_state(
        view,
        source_key_map,
        reference_source_key=reference_key,
        primary_source_key=primary_key,
        page_source_keys=keys,
    )
    if capture.state is None:
        raise ReviewValidationError(f"view state unavailable: {capture.reason}")
    pending: list[CaptureSource] = []
    for document, key in zip(page, keys, strict=True):
        profile = document.raw_profile
        suffix = document.source_path.suffix.lower() if document.source_path else ""
        if profile is None and suffix not in ENCODED_IMAGE_EXTENSIONS:
            raise ReviewValidationError("Finding source format is not supported")
        if profile is not None and not isinstance(profile, RawProfile | YuvProfile):
            raise ReviewValidationError("Finding source has invalid native profile")
        if document.source_path is None:
            raise ReviewValidationError("unloaded source path")
        original = snapshot_source(document, key)
        source = ReviewSourceV1(
            key,
            ReviewLocatorV1(
                document.source_path.name,
                local_path=(str(document.source_path.resolve()) if persist_local_paths else None),
            ),
            ReviewNativeSignatureV1(
                original.profile_signature,
                original.native_shape,
                original.reference_shape,
                original.native_dtype,
                original.channel_layout,
                original.effective_bits,
                canonical_json(original.native_interpretation.to_portable(), limit=16_384),
            ),
            ReviewFingerprintV1("sha256", None, 0, None, "unverified"),
        )
        pending.append(
            CaptureSource(
                key,
                document,
                document.generation,
                document.source_path.resolve(),
                profile.copy(deep=True) if profile is not None else None,
                source,
            )
        )
    # No pending/stale/uncomputed W02 result is copied, and a Pivot is never
    # treated as numerical authority.
    analysis = ReviewAnalysisCaptureV1("unavailable", reason="uncomputed_or_stale")
    if analysis_panel is not None:
        token = analysis_panel.get_current_analysis_token()
        if isinstance(token, PresentedAnalysisTokenV1):
            result = capture_presented_analysis(analysis_panel, token)
            if result.snapshot is not None:
                try:
                    captured = ReviewAnalysisCaptureV1.from_snapshot(result.snapshot)
                    # Enforce exact W02 scope/channel and source interpretation
                    # via Finding and W09a document validation downstream.
                    ReviewFindingV1(
                        str(uuid4()),
                        title,
                        note,
                        tags,
                        utc_now(),
                        keys,
                        reference_key,
                        pair_key,
                        capture.state,
                        roi_ref,
                        line_ref,
                        channel,
                        display_gain,
                        difference_intent,
                        (captured,),
                        "available",
                    )
                    # W02 source digest may exist, but candidate fingerprints
                    # are deliberately UNVERIFIED at GUI staging time. Reconcile
                    # with the attested bytes only after the worker completes.
                    analysis = captured
                except (ReviewValidationError, ValueError, TypeError):
                    analysis = ReviewAnalysisCaptureV1(
                        "unavailable", reason="presentation_source_scope_mismatch"
                    )
            else:
                analysis = ReviewAnalysisCaptureV1(
                    "unavailable", reason=(result.reason or "stale")[:1024]
                )
    finding = ReviewFindingV1(
        id=str(uuid4()),
        title=title,
        note=note,
        tags=tags,
        captured_utc=utc_now(),
        source_keys=keys,
        reference_key=reference_key,
        pair_target_key=pair_key,
        view_state=capture.state,
        roi_ref=roi_ref,
        line_ref=line_ref,
        channel=channel,
        display_gain=display_gain,
        difference_intent=difference_intent,
        analysis=(analysis,),
        availability="available" if analysis.status == "captured" else "unavailable",
    )
    return StagedFinding(finding, tuple(pending))


def attest_staged_finding(
    stage: StagedFinding,
    *,
    cancel: Callable[[], bool] | None = None,
) -> AttestedFinding:
    """Worker-only: three independent assertions (bytes, interpretation, pixels).

    The previously loaded native samples are compared against a fresh decode
    from W09a's candidate descriptor. Without this check, an older loaded
    image could be labeled with a newer file's SHA-256.
    """
    verified_sources: list[ReviewSourceV1] = []
    for pending in stage.sources:
        if cancel is not None and cancel():
            raise ReviewCancelled("capture cancelled before source attestation")
        digest = stream_source_sha256(
            pending.path,
            cancel=cancel,
            max_bytes=MAX_NATIVE_VERIFY_BYTES,
        )
        candidate = replace(
            pending.source,
            fingerprint=ReviewFingerprintV1(
                "sha256",
                digest.sha256,
                digest.size_bytes,
                digest.mtime_ns,
                "verified",
            ),
        )
        decoder = review_candidate_decoder(pending.path, pending.profile)
        status: SourceResolutionV1 = verify_review_source(
            candidate,
            pending.path,
            decoder,
            confirmed_by_user=True,
            cancel=cancel,
            max_bytes=MAX_NATIVE_VERIFY_BYTES,
        )
        if not status.may_bind_historical_finding:
            raise ReviewValidationError(f"capture source unavailable: {status.status}")
        if (
            decoder.native_sample_digest is None
            or decoder.native_sample_digest != native_sample_sha256(pending.document)
        ):
            raise ReviewValidationError(
                "loaded native samples differ from newly verified candidate"
            )
        verified_sources.append(candidate)
    if cancel is not None and cancel():
        raise ReviewCancelled("capture cancelled before commit")
    finding = stage.finding
    # A completed W02 capture is historical evidence only if its own source
    # interpretations and optional SHA agree with newly attested candidate
    # content. Otherwise keep the Finding but record explicit unavailability.
    if any(c.status == "captured" for c in finding.analysis):
        try:
            ReviewDocumentV1(
                str(uuid4()),
                "0.1.0",
                finding.captured_utc,
                finding.captured_utc,
                tuple(verified_sources),
                ReviewWorkspaceIntentV1(
                    source_order=tuple(s.source_key for s in verified_sources),
                ),
                (finding,),
                allow_local_paths=any(s.locator.local_path for s in verified_sources),
            )
        except ReviewValidationError:
            finding = replace(
                finding,
                analysis=(
                    ReviewAnalysisCaptureV1(
                        "unavailable", reason="attested_source_or_analysis_context_mismatch"
                    ),
                ),
                availability="unavailable",
            )
    return AttestedFinding(finding, tuple(verified_sources), stage.sources)
