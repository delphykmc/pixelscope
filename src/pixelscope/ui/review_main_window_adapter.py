"""W09b canonical MainWindow integration adapter (orchestrator wiring seam).

This is the only Review code that invokes Base registration/selection. It is
NOT installed by import and never replaces a runtime MainWindow method. The
Base owner installs it with an explicit typed hook after common composition,
and forwards terminal load/layout notifications to the Review controller.
"""
from __future__ import annotations

import weakref
from dataclasses import dataclass
from typing import Any

from pixelscope.core.line_profile import LineSelection
from pixelscope.core.review_analysis_sources import native_profile_signature
from pixelscope.core.review_record import ReviewDocumentV1
from pixelscope.core.roi import RoiBounds
from pixelscope.io.path_discovery import ImageInput
from pixelscope.io.review_native_decoder import ENCODED_IMAGE_EXTENSIONS
from pixelscope.ui.display_gain import display_gain_state
from pixelscope.ui.review_restore_controller import (
    CanonicalReviewRestoreAuthority,
    RestorePlan,
    RestoreReport,
)
from pixelscope.ui.review_view_state_adapter import (
    ReviewRestoreResult,
    VerifiedViewSource,
    restore_review_view_state,
)


@dataclass(frozen=True)
class PreparedReviewStage:
    epoch: int
    document_id: str
    source_keys: tuple[str, ...]
    source_paths: tuple[str, ...]


class MainWindowReviewRestoreAuthority(CanonicalReviewRestoreAuthority):
    """Preflight never mutates; commit uses only existing canonical MainWindow APIs.

    This adapter is deliberately limited to the Originals + RAW/YUV profile
    path. Other display modes must be expanded in their owning W05 component,
    not emulated by Review.
    """

    def __init__(self, window: Any, review: ReviewDocumentV1) -> None:
        self._window_ref = weakref.ref(window)
        self.review = review
        self._binding: dict[str, tuple[str, int]] = {}
        self._committed_epoch: int | None = None
        self._overlay_epoch: int | None = None
        self._recipe_epoch: int | None = None
        self._single_applied_epoch: int | None = None

    @property
    def window(self) -> Any:
        window = self._window_ref()
        if window is None or window._closing:
            raise RuntimeError("MainWindow unavailable or closing")
        return window

    def matches_committed_selection(self, ids: tuple[str, ...]) -> bool:
        """Distinguish this restore's publication from a new user selection."""
        return self._committed_epoch is not None and ids == tuple(
            document_id for document_id, _generation in self._binding.values()
        )

    def memo_overlay_bindings(self) -> dict[str, tuple[str, int]]:
        """Copy the explicit verified restore bindings; never locate/match sources."""
        return dict(self._binding)

    def prepare(self, plan: RestorePlan) -> PreparedReviewStage:
        window = self.window
        finding = plan.finding
        if finding.view_state.presentation_mode != "originals":
            raise ValueError("Review needs explicit W05 presentation-mode adapter")
        if finding.channel != "All":
            raise ValueError("Unsupported historical native channel: " + finding.channel)
        if finding.line_ref is not None:
            LineSelection(*finding.line_ref)
        if (
            finding.difference_intent is not None
            and finding.difference_intent.region == "Active ROI"
            and finding.roi_ref is None
        ):
            raise ValueError("Active ROI Difference requires recorded ROI")
        if tuple(item.approved.source_key for item in plan.candidates) != finding.source_keys:
            raise ValueError("Finding source order drift")
        if not all(item.verified and item.still_current() for item in plan.candidates):
            raise ValueError("a required source is not verified")
        # Canonical MainWindow registration deduplicates by _path_key(path).
        # Reject collisions *before* any catalog/selection/layout mutation.
        canonical_keys = tuple(window._path_key(item.approved.path) for item in plan.candidates)
        if len(set(canonical_keys)) != len(canonical_keys):
            raise ValueError("multiple Review Source UUIDs resolve to one canonical path")
        existing_ids = tuple(window._document_id_by_path.get(key) for key in canonical_keys)
        reused = tuple(document_id for document_id in existing_ids if document_id is not None)
        if len(set(reused)) != len(reused):
            raise ValueError("multiple Review Source UUIDs reuse one document ID")
        by_key = {source.source_key: source for source in self.review.sources}
        for item in plan.candidates:
            source = by_key.get(item.approved.source_key)
            if source is None:
                raise ValueError("candidate is outside the opened Review")
            if (
                source.native_signature.reference_shape
                != finding.view_state.source_shapes_ref[source.source_key]
            ):
                raise ValueError("native/reference geometry changed")
            suffix = item.approved.path.suffix.lower()
            if suffix not in (".raw", ".yuv") and suffix not in ENCODED_IMAGE_EXTENSIONS:
                raise ValueError("unsupported canonical Review input extension")
            if suffix in ENCODED_IMAGE_EXTENSIONS and item.approved.profile is not None:
                raise ValueError("encoded source must not use a RAW/YUV profile")
        if window._channel_split_active:
            raise ValueError("Split Channels must be exited before Review activation")
        return PreparedReviewStage(
            plan.epoch,
            self.review.document_id,
            finding.source_keys,
            tuple(str(item.approved.path) for item in plan.candidates),
        )

    def commit(self, prepared: object, plan: RestorePlan) -> RestoreReport:
        if (
            not isinstance(prepared, PreparedReviewStage)
            or prepared.epoch != plan.epoch
            or prepared.document_id != self.review.document_id
            or prepared.source_keys != plan.finding.source_keys
        ):
            return RestoreReport(plan.epoch, "unavailable", "preflight state changed")
        if not all(item.still_current() for item in plan.candidates):
            return RestoreReport(plan.epoch, "unavailable", "file changed after preflight")
        window = self.window
        self._committed_epoch = plan.epoch
        self._overlay_epoch = None
        self._recipe_epoch = None
        self._single_applied_epoch = None
        self._binding.clear()
        # The registration phase is the irreversible commit point. Failures
        # after this point must be reported as partial; never claim rollback.
        try:
            action = getattr(window, "diff_action", None)
            if action is not None:
                blocked = action.blockSignals(True)
                action.setChecked(False)
                action.blockSignals(blocked)
            window._difference_document = None
            window._difference_source_ids = None
            selected_ids: list[str] = []
            for item in plan.candidates:
                path = item.approved.path
                prior = window._document_id_by_path.get(window._path_key(path))
                document_id = window._register_input(
                    ImageInput(path, None),
                    resolve_raw_profile=False,
                )
                if document_id is None:
                    raise RuntimeError(f"canonical registration refused {path.name}")
                profile = (
                    item.approved.profile.copy(deep=True)
                    if item.approved.profile is not None
                    else None
                )
                if profile is not None:
                    window._raw_profiles[document_id] = profile
                if prior is not None:
                    window._mark_document_for_reload(document_id, profile)
                if document_id in selected_ids:
                    raise RuntimeError("canonical Source UUID collision during registration")
                selected_ids.append(document_id)
                current = window.documents[document_id]
                self._binding[item.approved.source_key] = (
                    document_id,
                    current.generation,
                )
            window._select_document_ids(selected_ids)
            desired_layout = (
                "Single View" if plan.finding.view_state.layout_kind == "Single" else "Multi View"
            )
            if window._layout_mode != desired_layout:
                window.set_layout_mode(desired_layout)
            primary_id = self._binding[plan.finding.view_state.primary_source_key][0]
            window._set_focus_document(primary_id)
            window.comparison_analysis_panel.bind_review_source_keys(
                {doc_id: key for key, (doc_id, _) in self._binding.items()}
            )
            if plan.finding.view_state.layout_kind != "Single":
                window.multi_compare_view.begin_review_restore(plan.epoch)
            display_gain_state().set_gain(plan.finding.display_gain)
            # Reused/resident sources can settle synchronously: apply immediately.
            return self.retry(plan)
        except Exception as exc:  # noqa: BLE001 - registration may already be committed
            return RestoreReport(
                plan.epoch,
                "unavailable",
                f"post-commit stage failed: {exc}",
                True,
            )

    def retry(self, plan: RestorePlan) -> RestoreReport:
        if self._committed_epoch != plan.epoch:
            return RestoreReport(plan.epoch, "interrupted", "stale restore epoch")
        window = self.window
        if not all(item.still_current() for item in plan.candidates):
            return RestoreReport(plan.epoch, "unavailable", "candidate file changed", True)
        bound: dict[str, VerifiedViewSource] = {}
        expected = {s.source_key: s.native_signature for s in self.review.sources}
        for key in plan.finding.source_keys:
            pair = self._binding.get(key)
            if pair is None:
                return RestoreReport(plan.epoch, "unavailable", "source binding missing", True)
            doc_id, generation = pair
            document = window.documents.get(doc_id)
            if document is None or document.generation != generation:
                return RestoreReport(plan.epoch, "unavailable", "generation replaced", True)
            if document.loading_state == "error":
                return RestoreReport(plan.epoch, "unavailable", "foreground load error", True)
            if document.source is None or document.loading_state != "ready":
                return RestoreReport(plan.epoch, "pending", "foreground load pending", True)
            if (
                native_profile_signature(document) != expected[key].profile_signature
                or document.reference_shape != expected[key].reference_shape
            ):
                return RestoreReport(plan.epoch, "unavailable", "loaded profile mismatch", True)
            bound[key] = VerifiedViewSource(document, generation, True)
        if tuple(d.document_id for d in window.current_comparison_documents()) != tuple(
            self._binding[key][0] for key in plan.finding.source_keys
        ):
            return RestoreReport(plan.epoch, "unavailable", "canonical page changed", True)
        # Apply canonical overlays once, before W04's geometry preflight.
        # Revealing the Line panel changes viewport size; avoid repeated
        # layout churn during pending W04 retries.
        if self._overlay_epoch != plan.epoch:
            if plan.finding.roi_ref is not None:
                roi = RoiBounds(*plan.finding.roi_ref)
                if not window._apply_shared_roi(roi, allow_channel_split=False):
                    return RestoreReport(plan.epoch, "unavailable", "ROI rejected", True)
            else:
                window.clear_roi()
            if plan.finding.line_ref is not None:
                line = LineSelection(*plan.finding.line_ref)
                window._shared_line_changed(line)
                if window._shared_line != line:
                    return RestoreReport(plan.epoch, "unavailable", "Line restore rejected", True)
            elif window._shared_line is not None:
                window.clear_line()
                if window._shared_line is not None:
                    return RestoreReport(plan.epoch, "unavailable", "Line not cleared", True)
            self._overlay_epoch = plan.epoch
        if self._recipe_epoch != plan.epoch:
            recipe_reason = self._restore_difference_recipe(plan)
            if recipe_reason is not None:
                return RestoreReport(plan.epoch, "unavailable", recipe_reason, True)
            self._recipe_epoch = plan.epoch
        state = (
            self._restore_single_view(plan, bound)
            if plan.finding.view_state.layout_kind == "Single"
            else restore_review_view_state(
                window.multi_compare_view,
                plan.finding.view_state,
                bound,
                epoch=plan.epoch,
                presentation_mode="originals",
            )
        )
        if state.status == "applied":
            # W04 restores the viewport owner. Mirror its committed Sync state
            # into the canonical action without emitting a second range change.
            action = window.sync_action
            blocked = action.blockSignals(True)
            try:
                action.setChecked(plan.finding.view_state.sync_enabled)
            finally:
                action.blockSignals(blocked)
            window._update_action_states()
            if not self._difference_recipe_matches(plan):
                return RestoreReport(plan.epoch, "unavailable", "Difference recipe changed", True)
            if plan.finding.line_ref is not None:
                line = window._shared_line
                if line is None or (line.x1, line.y1, line.x2, line.y2) != plan.finding.line_ref:
                    return RestoreReport(plan.epoch, "unavailable", "Line changed after W04", True)
            elif window._shared_line is not None:
                return RestoreReport(plan.epoch, "unavailable", "Stale Line still active", True)
            if plan.finding.roi_ref is not None:
                roi = window._shared_roi
                if roi is None or (roi.x, roi.y, roi.width, roi.height) != plan.finding.roi_ref:
                    return RestoreReport(plan.epoch, "unavailable", "ROI changed after W04", True)
            elif window._shared_roi is not None:
                return RestoreReport(plan.epoch, "unavailable", "ROI not cleared", True)
        return RestoreReport(
            plan.epoch,
            state.status,
            state.reason or state.status,
            state.partial_state or state.status == "unavailable",
        )

    def _restore_single_view(
        self,
        plan: RestorePlan,
        bound: dict[str, VerifiedViewSource],
    ) -> ReviewRestoreResult:
        """Apply a one-image Memo through the actual Single View owner.

        W04 multi-view restore is intentionally not invoked on its hidden
        viewer. Controller epoch and actual display readiness still gate all
        asynchronous transitions.
        """
        epoch = plan.epoch
        window = self.window
        state = plan.finding.view_state
        if self._committed_epoch != epoch:
            return ReviewRestoreResult("interrupted", epoch, "single-epoch-revoked")
        if self._single_applied_epoch == epoch:
            return ReviewRestoreResult("interrupted", epoch, "single-already-applied")
        key = state.page_source_keys[0]
        viewer = window.viewer
        expected = bound[key].document
        if (
            window.central_stack.currentWidget() is not viewer
            or viewer.document is not expected
            or viewer.presented_document is not expected
            or viewer._geometry_timer.isActive()
            or viewer._display_preview_worker is not None
            or viewer._graphics_resources_disposed
        ):
            return ReviewRestoreResult("pending", epoch, "single-view-not-settled")
        target = state.per_source.get(key)
        if target is None:
            return ReviewRestoreResult("unavailable", epoch, "single-viewport-not-recorded")
        measurement = viewer.measure_physical_zoom()
        if not measurement.valid:
            return ReviewRestoreResult("pending", epoch, "physical-zoom-not-ready")
        result = viewer.set_physical_zoom(
            target.physical_scale * 100.0,
            target.center_ref_xy,
        )
        if not result.achieved:
            return ReviewRestoreResult("pending", epoch, "single-physical-zoom-pending")
        self._single_applied_epoch = epoch
        return ReviewRestoreResult("applied", epoch, "single memo ROI and viewport restored")

    def _difference_recipe_matches(self, plan: RestorePlan) -> bool:
        intent = plan.finding.difference_intent
        if intent is None:
            return True
        panel = self.window.difference_panel
        first = self._binding.get(intent.reference_key)
        second = self._binding.get(intent.target_key)
        pair = panel.selected_documents()
        return (
            first is not None
            and second is not None
            and pair is not None
            and tuple(doc.document_id for doc in pair) == (first[0], second[0])
            and panel.channel.currentText() == intent.channel
            and panel.mode.currentText() == intent.mode
            and panel.region.currentText() == intent.region
            and panel.gain.value() == intent.gain
            and panel.threshold.value() == intent.threshold
        )

    def _restore_difference_recipe(self, plan: RestorePlan) -> str | None:
        """Restore canonical Difference controls without calculating any map."""
        intent = plan.finding.difference_intent
        if intent is None:
            return None
        panel = self.window.difference_panel
        first = self._binding.get(intent.reference_key)
        second = self._binding.get(intent.target_key)
        if first is None or second is None or first[0] == second[0]:
            return "Difference pair has no two distinct canonical bindings"
        selectors = (
            (panel.a_selector, first[0]),
            (panel.b_selector, second[0]),
        )
        if any(selector.findData(document_id) < 0 for selector, document_id in selectors):
            return "Historical Difference pair not present in canonical selectors"
        panel._cancel_worker()
        panel._cancel_preview_worker()
        panel._display_timer.stop()
        for selector, document_id in selectors:
            was_blocked = selector.blockSignals(True)
            try:
                selector.setCurrentIndex(selector.findData(document_id))
            finally:
                selector.blockSignals(was_blocked)
        panel._update_channels()
        values = (
            (panel.channel, intent.channel),
            (panel.mode, intent.mode),
            (panel.region, intent.region),
        )
        if any(control.findText(value) < 0 for control, value in values):
            return "Saved Difference channel/mode/region unsupported by live controls"
        numeric = ((panel.gain, intent.gain), (panel.threshold, intent.threshold))
        if any(not control.minimum() <= value <= control.maximum() for control, value in numeric):
            return "Saved Difference gain/threshold outside current range"
        for control, value in values:
            was_blocked = control.blockSignals(True)
            try:
                control.setCurrentText(value)
            finally:
                control.blockSignals(was_blocked)
        for control, amount in numeric:
            was_blocked = control.blockSignals(True)
            try:
                control.setValue(amount)
            finally:
                control.blockSignals(was_blocked)
        # This intentionally clears historical live metrics. A recipe alone
        # never authorizes Calculate, cached Difference, or W02 current results.
        panel.last_result = None
        panel._clear_metrics()
        pair = panel.selected_documents()
        if pair is None or tuple(doc.document_id for doc in pair) != (first[0], second[0]):
            return "Historical Difference pair was not retained"
        if any(control.currentText() != value for control, value in values):
            return "Difference presentation controls diverged"
        if any(control.value() != value for control, value in numeric):
            return "Saved Difference numeric controls were clamped"
        return None

    def cancel(self, epoch: int) -> None:
        window = self._window_ref()
        if window is not None and self._committed_epoch == epoch:
            window.multi_compare_view.cancel_review_restore()
            self._committed_epoch = None
            self._overlay_epoch = None
            self._recipe_epoch = None
            self._single_applied_epoch = None
            self._binding.clear()
