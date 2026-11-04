"""W04 adapters between live multi-view geometry and durable ReviewViewStateV1.

This is deliberately not a source registry or a restore transaction.  MainWindow
is the only authority for source registration, page, active/primary roles and
load generations. W09 supplies *verified* bindings after canonical staging and
calls restore again on settled foreground load/layout notifications. No timers,
nested event loops, worker callbacks or implicit Difference Calculate live here.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from typing import TYPE_CHECKING, Literal

from shiboken6 import isValid

from pixelscope.core.image_document import ImageDocument
from pixelscope.core.review_view_state import (
    SUPPORTED_PRESENTATIONS,
    ReviewViewStateV1,
    ReviewViewportV1,
)

if TYPE_CHECKING:
    from pixelscope.ui.image_viewer import ImageViewer
    from pixelscope.ui.multi_compare_view import MultiCompareView


@dataclass(frozen=True)
class ReviewCaptureResult:
    state: ReviewViewStateV1 | None = None
    reason: str | None = None

    @property
    def available(self) -> bool:
        return self.state is not None


@dataclass(frozen=True)
class VerifiedViewSource:
    """Runtime-only binding. Never serialize or treat its document ID as a key."""

    document: ImageDocument
    expected_generation: int
    verified: bool


@dataclass(frozen=True)
class ReviewRestoreResult:
    status: Literal["applied", "pending", "unavailable", "interrupted"]
    epoch: int
    reason: str | None = None

    @property
    def applied(self) -> bool:
        return self.status == "applied"


def _viewport(viewer: ImageViewer) -> ReviewViewportV1 | None:
    measured = viewer.measure_physical_zoom()
    if not measured.valid or measured.percent is None:
        return None
    ranges = viewer.view_box.viewRange()
    center = (
        (float(ranges[0][0]) + float(ranges[0][1])) / 2.0,
        (float(ranges[1][0]) + float(ranges[1][1])) / 2.0,
    )
    if not all(isfinite(v) for v in center):
        return None
    return ReviewViewportV1(center, measured.percent / 100.0)


def _ready(view: MultiCompareView) -> str | None:
    if not isValid(view):
        return "owner-deleted"
    if view._review_restore_closed:
        return "owner-closed"
    if view._setting_documents or view._layout_refit_active or not view.isVisible():
        return "layout-not-settled"
    for viewer in view.visible_viewers:
        if not isValid(viewer):
            return "viewer-deleted"
        if viewer._graphics_resources_disposed:
            return "viewer-closed"
    if not view.occupied_viewers:
        return "no-presented-sources"
    for viewer in view.occupied_viewers:
        if viewer._geometry_timer.isActive():
            return "layout-not-settled"
        document = viewer.document
        if document is None:
            return "missing-presented-source"
        if viewer.presented_document is not document:
            return "foreground-load-pending"
        if document.loading_state == "error" or document.error_state is not None:
            return "source-load-failed"
        if document.preview is None:
            return "foreground-load-pending"
        if viewer._display_preview_worker is not None:
            return "display-gain-pending"
        if viewer.view_box.width() <= 0 or viewer.view_box.height() <= 0:
            return "layout-not-settled"
    return None


def capture_review_view_state(
    view: MultiCompareView,
    source_key_map: Mapping[str, str],
    *,
    reference_source_key: str,
    primary_source_key: str,
    presentation_mode: str = "originals",
    page_source_keys: tuple[str, ...] | None = None,
) -> ReviewCaptureResult:
    """Capture settled physical geometry, never manufacture fallback zooms.

    `source_key_map` maps transient ImageDocument.document_id to UUID source
    keys; aliases and slot indices are forbidden. Optional page ordering must
    match the *exact* currently presented source set. The owner supplies the
    primary/reference authority instead of inferring it from visual tile order.
    """
    reason = _ready(view)
    if reason is not None:
        return ReviewCaptureResult(reason=reason)
    if presentation_mode not in SUPPORTED_PRESENTATIONS:
        return ReviewCaptureResult(reason="unknown-presentation-mode")
    source_viewers: dict[str, ImageViewer] = {}
    presented_order: list[str] = []
    for viewer in view.occupied_viewers:
        document = viewer.document
        if document is None or document.channel_layout == "DIFFERENCE":
            return ReviewCaptureResult(reason="derived-source-not-durable")
        key = source_key_map.get(document.document_id)
        if key is None or key in source_viewers:
            return ReviewCaptureResult(reason="source-identity-missing-or-duplicate")
        source_viewers[key] = viewer
        presented_order.append(key)
    page = tuple(presented_order) if page_source_keys is None else tuple(page_source_keys)
    if len(page) != len(presented_order) or set(page) != set(presented_order):
        return ReviewCaptureResult(reason="page-source-set-mismatch")
    active = view._active_viewer
    if active is None or active.document is None:
        return ReviewCaptureResult(reason="active-source-unavailable")
    active_key = source_key_map.get(active.document.document_id)
    if active_key not in source_viewers:
        return ReviewCaptureResult(reason="active-source-not-presented")
    if primary_source_key not in source_viewers or reference_source_key not in source_viewers:
        return ReviewCaptureResult(reason="primary-or-reference-not-presented")
    if len(page) > 1:
        primary_document = source_viewers[primary_source_key].document
        if primary_document is None or view.focus_document_id != primary_document.document_id:
            return ReviewCaptureResult(reason="primary-role-not-staged")
    viewports: dict[str, ReviewViewportV1] = {}
    shapes: dict[str, tuple[int, int]] = {}
    for key, viewer in source_viewers.items():
        viewport = _viewport(viewer)
        if viewport is None or viewer.document is None:
            return ReviewCaptureResult(reason="physical-scale-unavailable")
        viewports[key] = viewport
        shapes[key] = viewer._reference_shape(viewer.document)
    anchor = viewports[reference_source_key]
    if view.sync_enabled:
        for viewport in viewports.values():
            if abs(viewport.physical_scale - anchor.physical_scale) > (
                0.005 * anchor.physical_scale
            ):
                return ReviewCaptureResult(reason="shared-physical-scale-diverged")
            if max(
                abs(viewport.center_ref_xy[axis] - anchor.center_ref_xy[axis])
                * anchor.physical_scale
                for axis in (0, 1)
            ) > 0.5:
                return ReviewCaptureResult(reason="shared-reference-center-diverged")
    ref_viewer = source_viewers[reference_source_key]
    bounds = ref_viewer.view_box.viewRange()
    try:
        state = ReviewViewStateV1(
            reference_source_key=reference_source_key,
            page_source_keys=page,
            active_source_key=active_key,
            primary_source_key=primary_source_key,
            layout_kind=view.layout_kind,
            presentation_mode=presentation_mode,
            sync_enabled=view.sync_enabled,
            center_ref_xy=anchor.center_ref_xy,
            physical_scale=anchor.physical_scale,
            reference_shape=shapes[reference_source_key],
            source_shapes_ref=shapes,
            per_source={} if view.sync_enabled else viewports,
            visible_bounds_ref=(
                float(bounds[0][0]), float(bounds[1][0]),
                float(bounds[0][1]), float(bounds[1][1]),
            ),
        )
    except (ValueError, TypeError, OverflowError) as exc:
        return ReviewCaptureResult(reason=f"invalid-review-geometry: {exc}")
    return ReviewCaptureResult(state=state)


def restore_review_view_state(
    view: MultiCompareView,
    state: ReviewViewStateV1,
    resolved_sources: Mapping[str, VerifiedViewSource],
    *,
    epoch: int,
    presentation_mode: str,
) -> ReviewRestoreResult:
    """Attempt one epoch-guarded apply on an already-staged, settled page.

    The orchestrator MUST call view.begin_review_restore(epoch) after canonical
    source/page/layout/primary staging, then retry this function on terminal
    foreground/display/layout notifications. User input must call
    view.cancel_review_restore(). This routine never schedules a late mutation.
    """
    if (
        not isValid(view)
        or view._review_restore_closed
        or view._review_restore_pending_epoch != epoch
    ):
        return ReviewRestoreResult("interrupted", epoch, "epoch-revoked-or-owner-closed")
    if view._review_restore_applied_epoch == epoch:
        return ReviewRestoreResult("interrupted", epoch, "epoch-already-applied")
    if presentation_mode != state.presentation_mode:
        return ReviewRestoreResult("unavailable", epoch, "presentation-mode-mismatch")
    if view.layout_kind != state.layout_kind:
        return ReviewRestoreResult("pending", epoch, "layout-not-staged")
    if set(resolved_sources) != set(state.page_source_keys):
        return ReviewRestoreResult("unavailable", epoch, "required-source-set-mismatch")

    for key in state.page_source_keys:
        binding = resolved_sources[key]
        if not isinstance(binding, VerifiedViewSource) or not binding.verified:
            return ReviewRestoreResult("unavailable", epoch, f"source-not-verified:{key}")
        doc = binding.document
        if (
            doc.generation != binding.expected_generation
            or doc.reference_shape != state.source_shapes_ref[key]
        ):
            return ReviewRestoreResult("unavailable", epoch, f"source-generation-or-bounds:{key}")
        if doc.loading_state == "error" or doc.error_state is not None:
            return ReviewRestoreResult("unavailable", epoch, f"source-load-failed:{key}")
    reason = _ready(view)
    if reason is not None:
        status: Literal["pending", "unavailable"] = (
            "unavailable"
            if reason in {
                "owner-closed", "owner-deleted", "viewer-deleted",
                "viewer-closed", "source-load-failed",
            }
            else "pending"
        )
        return ReviewRestoreResult(status, epoch, reason)
    # Map *document object* to its canonical key. Matching a tile ordinal or a
    # reused document_id alone would allow a replaced ImageDocument to inherit
    # a different source's old view.
    by_object = {id(binding.document): key for key, binding in resolved_sources.items()}
    presented: dict[str, ImageViewer] = {}
    for viewer in view.occupied_viewers:
        document = viewer.document
        if document is None:
            return ReviewRestoreResult("pending", epoch, "foreground-load-pending")
        matched_key = by_object.get(id(document))
        if (
            matched_key is None
            or resolved_sources[matched_key].document is not document
            or matched_key in presented
        ):
            return ReviewRestoreResult("unavailable", epoch, "presented-source-identity-mismatch")
        if document.generation != resolved_sources[matched_key].expected_generation:
            return ReviewRestoreResult(
                "unavailable", epoch, f"late-generation-change:{matched_key}"
            )
        presented[matched_key] = viewer
    if set(presented) != set(state.page_source_keys):
        return ReviewRestoreResult("pending", epoch, "page-not-fully-presented")
    primary_document = resolved_sources[state.primary_source_key].document
    if (
        len(state.page_source_keys) > 1
        and view.focus_document_id != primary_document.document_id
    ):
        return ReviewRestoreResult("pending", epoch, "primary-role-not-staged")
    requested = (
        {key: ReviewViewportV1(state.center_ref_xy, state.physical_scale)
         for key in state.page_source_keys}
        if state.sync_enabled else state.per_source
    )
    # Preflight all transforms without touching the viewport; no implicit
    # clamp or guessed physical scale when the W01 geometry oracle is invalid.
    for key, viewer in presented.items():
        if _viewport(viewer) is None:
            return ReviewRestoreResult("pending", epoch, f"geometry-unavailable:{key}")
    view._review_restoring = True
    prior_sync = view._syncing_range
    view._syncing_range = True
    applied: list[str] = []
    try:
        view.set_sync_enabled(state.sync_enabled)
        for key in state.page_source_keys:
            target = requested[key]
            result = presented[key].set_physical_zoom(
                100.0 * target.physical_scale, target.center_ref_xy
            )
            if not result.achieved:
                view.cancel_review_restore()
                return ReviewRestoreResult(
                    "interrupted", epoch, f"physical-zoom-not-achieved:{key};applied={applied}"
                )
            applied.append(key)
        if view._review_restore_pending_epoch != epoch or view._review_restore_closed:
            return ReviewRestoreResult("interrupted", epoch, "epoch-revoked-during-apply")
        view._activate_viewer(presented[state.active_source_key])
        view._review_restore_applied_epoch = epoch
        view._review_restore_pending_epoch = None
        return ReviewRestoreResult("applied", epoch)
    except (RuntimeError, ValueError, TypeError) as exc:
        view.cancel_review_restore()
        return ReviewRestoreResult("interrupted", epoch, f"apply-exception:{exc};applied={applied}")
    finally:
        view._syncing_range = prior_sync
        view._review_restoring = False
