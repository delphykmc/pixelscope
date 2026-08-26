from __future__ import annotations

from contextlib import suppress
from typing import Any

from pixelscope.core.image_document import ImageDocument


class DifferenceCurationLifecycle:
    """Apply the owner-final Keep/Calculate/toolbar contract around Diff owners."""

    def __init__(self, window: Any, review_controller: Any) -> None:
        self.window = window
        self.review_controller = review_controller
        self._syncing_action = False
        self._resetting_difference = False
        self._original_render_selection = window._render_selection
        self._original_set_difference_visible = window._set_difference_visible
        self._original_update_action_states = window._update_action_states
        self._install()

    def _install(self) -> None:
        self.review_controller.keep_picked = self.keep_picked
        self.review_controller._difference_tooltip = self._difference_tooltip
        with suppress(RuntimeError):
            self.review_controller.keep_button.clicked.disconnect()
        self.review_controller.keep_button.clicked.connect(self.keep_picked)

        # Passive selection/page renders may rebind DifferencePanel inputs and
        # metrics, but do not automatically show cached Difference results.
        self.window._render_selection = self._render_selection
        self.window._difference_result_matches_current_pair = self._active_result_bound
        self.window._update_action_states = self._update_action_states

        action = self.window.diff_action
        try:
            action.toggled.disconnect(self._original_set_difference_visible)
        except (RuntimeError, TypeError):
            action.toggled.disconnect()
        action.toggled.connect(self._set_difference_visible)
        self._enforce_action_state()

    def _active_result_bound(self) -> bool:
        source_ids = getattr(self.window, "_difference_source_ids", None)
        return (
            getattr(self.window, "_difference_document", None) is not None
            and isinstance(source_ids, tuple)
            and len(source_ids) == 2
        )

    def _cached_result_available(self) -> bool:
        """Return whether the current page owns an actionable cached A/B pair."""

        panel = getattr(self.window, "difference_panel", None)
        if panel is None or not panel.has_cached_map():
            return False
        pair = panel.selected_documents()
        if pair is None:
            return False
        page_ids = {
            document.document_id for document in self.window.current_comparison_documents()
        }
        if len(page_ids) < 2:
            return False
        pair_ids = {pair[0].document_id, pair[1].document_id}
        return len(pair_ids) == 2 and pair_ids.issubset(page_ids)

    def _active_sources_still_selected(self) -> bool:
        source_ids = getattr(self.window, "_difference_source_ids", None)
        if not isinstance(source_ids, tuple) or len(source_ids) != 2:
            return False
        selected_ids = {document.document_id for document in self.window.selected_documents}
        return all(source_id in selected_ids for source_id in source_ids)

    def _render_selection(self, preserve_view: bool = False) -> None:
        # Ordinary logical Selected mutations can invalidate an explicitly
        # established Difference just as surely as Keep. If either provenance source
        # has left Selected, close the active binding before rendering the new
        # workspace while preserving the generation-keyed map cache.
        if (
            not self._resetting_difference
            and self._active_result_bound()
            and not self._active_sources_still_selected()
        ):
            self._reset_active_difference()

        panel = self.window.difference_panel
        cached_display = panel.cached_display_for_current
        calculate = panel.calculate_difference
        panel.cached_display_for_current = lambda: None
        panel.calculate_difference = lambda *args, **kwargs: None
        try:
            self._original_render_selection(preserve_view=preserve_view)
        finally:
            panel.cached_display_for_current = cached_display
            panel.calculate_difference = calculate
        self._enforce_action_state()

    def _update_action_states(self) -> None:
        """Apply the Difference lifecycle gate after the base action-state update."""

        self._original_update_action_states()
        self._enforce_action_state()

    def _enforce_action_state(self) -> None:
        if self._syncing_action:
            return
        self._syncing_action = True
        try:
            action = self.window.diff_action
            active = self._active_result_bound()
            cached = self._cached_result_available()
            action.blockSignals(True)
            if not active:
                action.setChecked(False)
            action.setEnabled(active or cached)
            action.blockSignals(False)
            tooltip = (
                "Hide active Difference"
                if active and action.isChecked()
                else "Show active Difference"
                if active
                else "Show cached Difference for current pair"
                if cached
                else "Calculate Difference in Analysis first"
            )
            action.setToolTip(tooltip)
            action.setStatusTip(tooltip)
        finally:
            self._syncing_action = False

    def _set_difference_visible(self, visible: bool) -> None:
        if not visible:
            self._original_set_difference_visible(False)
            self._enforce_action_state()
            return

        difference = getattr(self.window, "_difference_document", None)
        if not self._active_result_bound():
            if not self._cached_result_available():
                self._enforce_action_state()
                return
            cached = self.window.difference_panel.cached_display_for_current()
            if cached is None:
                self._enforce_action_state()
                return
            # Toolbar activation is an explicit user command, but it never computes a
            # new Difference map. It may only bind and display the current cached map.
            self.window._store_difference_document(*cached, switch_to_result=False)
            difference = getattr(self.window, "_difference_document", None)

        if not self._active_result_bound() or not isinstance(difference, ImageDocument):
            self._enforce_action_state()
            return

        # Re-show the established result itself. Toolbar UI never infers another pair
        # and never starts numerical Difference work.
        if len(self.window.current_comparison_documents()) >= 6:
            self.window._capture_six_image_diff_restore_state()
            self.window._navigate_single_view("difference")
        elif self.window._layout_mode == "Single View":
            self.window._navigate_single_view("difference")
            self.window._set_active_document(difference)
        else:
            self.window._layout_mode = "Multi View"
            self.window._focus_document_id = difference.document_id
            self.window._promote_multi_document(difference.document_id)
            self.window.layout_selector.blockSignals(True)
            self.window.layout_selector.setCurrentText("Multi View")
            self.window.layout_selector.blockSignals(False)
            self.window._render_selection(preserve_view=True)
        self.window._update_action_states()
        self._enforce_action_state()

    def keep_picked(self) -> bool:
        kept_ids = self.review_controller.state.kept_selected_ids()
        if not self.review_controller.state.active or not kept_ids:
            self.review_controller._sync_all()
            return False

        self._reset_active_difference()
        self.review_controller._applying = True
        try:
            self.review_controller._original_select_document_ids(list(kept_ids))
        finally:
            self.review_controller._applying = False
            self.review_controller.state.exit()
        self.review_controller._sync_all()
        self._enforce_action_state()
        return True

    def _reset_active_difference(self) -> None:
        if self._resetting_difference:
            return
        self._resetting_difference = True
        try:
            difference = getattr(self.window, "_difference_document", None)
            difference_id = (
                difference.document_id if isinstance(difference, ImageDocument) else None
            )
            action = self.window.diff_action

            if action.isChecked():
                # False delegates to the original PR #32 visibility teardown before
                # the active binding/provenance are cleared.
                action.setChecked(False)

            if difference_id is not None:
                self.window._multi_display_order = [
                    document_id
                    for document_id in self.window._multi_display_order
                    if document_id != difference_id
                ]
                if self.window._focus_document_id == difference_id:
                    self.window._focus_document_id = None
                if self.window._active_document_id == difference_id:
                    self.window._active_document_id = None

            if difference is not None and self.window.viewer.presented_document is difference:
                self.window.viewer.set_document(None)
                self.window.viewer.set_navigation_items([], "")

            self.window._six_image_diff_restore_state = None
            self.window._difference_document = None
            self.window._difference_source_ids = None
        finally:
            self._resetting_difference = False
        self._enforce_action_state()

    def _difference_tooltip(self) -> str:
        source_ids = getattr(self.window, "_difference_source_ids", None)
        if not isinstance(source_ids, tuple) or len(source_ids) != 2:
            return "Derived from source images. Keep Selection closes the active Difference."
        names: list[str] = []
        for document_id in source_ids:
            document = self.window.documents.get(document_id)
            names.append(document.display_name if document is not None else str(document_id))
        return (
            f"Derived from {names[0]} / {names[1]}. "
            "Keep Selection closes the active Difference; its cache is retained."
        )


def install_difference_curation_lifecycle(
    window: Any,
    review_controller: Any,
) -> None:
    existing = getattr(window, "difference_curation_lifecycle", None)
    if isinstance(existing, DifferenceCurationLifecycle):
        return
    lifecycle = DifferenceCurationLifecycle(window, review_controller)
    window.difference_curation_lifecycle = lifecycle
