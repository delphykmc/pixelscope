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
    ProductionNativeCandidateDecoder,
    native_sample_sha256,
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
    profile: RawProfile | YuvProfile
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
        source_key_map[pair_target_document_id]
        if pair_target_document_id is not None
        else None
    )
    capture = capture_review_view_state(
        view, source_key_map,
        reference_source_key=reference_key,
        primary_source_key=primary_key,
        page_source_keys=keys,
    )
    if capture.state is None:
        raise ReviewValidationError(f"view state unavailable: {capture.reason}")
    pending: list[CaptureSource] = []
    for document, key in zip(page, keys, strict=True):
        profile = document.raw_profile
        if not isinstance(profile, RawProfile | YuvProfile):
            raise ReviewValidationError(
                "W09b currently supports only explicitly profiled RAW/YUV sources"
            )
        if document.source_path is None:
            raise ReviewValidationError("unloaded source path")
        original = snapshot_source(document, key)
        source = ReviewSourceV1(
            key,
            ReviewLocatorV1(
                document.source_path.name,
                local_path=(
                    str(document.source_path.resolve()) if persist_local_paths else None
                ),
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
                key, document, document.generation, document.source_path.resolve(),
                profile.copy(deep=True), source,
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
                    probe = ReviewFindingV1(
                        str(uuid4()), title, note, tags, utc_now(), keys,
                        reference_key, pair_key, capture.state, roi_ref, line_ref,
                        channel, display_gain, difference_intent, (captured,), "available",
                    )
                    # No persistence, just the same document-level evidence
                    # signature checks that a real .pxreview load will enforce.
                    ReviewDocumentV1(
                        str(uuid4()), "0.1.0", probe.captured_utc, probe.captured_utc,
                        tuple(p.source for p in pending),
                        ReviewWorkspaceIntentV1(source_order=keys),
                        (probe,),
                        allow_local_paths=persist_local_paths,
                    )
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
        id=str(uuid4()), title=title, note=note, tags=tags, captured_utc=utc_now(),
        source_keys=keys, reference_key=reference_key, pair_target_key=pair_key,
        view_state=capture.state, roi_ref=roi_ref, line_ref=line_ref, channel=channel,
        display_gain=display_gain, difference_intent=difference_intent,
        analysis=(analysis,), availability="available" if analysis.status == "captured"
        else "unavailable",
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
            pending.path, cancel=cancel, max_bytes=MAX_NATIVE_VERIFY_BYTES,
        )
        candidate = replace(
            pending.source,
            fingerprint=ReviewFingerprintV1(
                "sha256", digest.sha256, digest.size_bytes,
                digest.mtime_ns, "verified",
            ),
        )
        decoder = ProductionNativeCandidateDecoder(pending.profile)
        status: SourceResolutionV1 = verify_review_source(
            candidate, pending.path, decoder, confirmed_by_user=True,
            cancel=cancel, max_bytes=MAX_NATIVE_VERIFY_BYTES,
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
    return AttestedFinding(stage.finding, tuple(verified_sources), stage.sources)
