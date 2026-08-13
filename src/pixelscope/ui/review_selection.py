from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton, QWidget

from pixelscope.core.image_document import ImageDocument
from pixelscope.core.review_selection import ReviewSelectionState
from pixelscope.ui.design_tokens import TOKENS, tile_style
from pixelscope.ui.image_viewer import ImageViewer


def _selection_button_style() -> str:
    return (
        f"QToolButton {{ background: transparent; color: {TOKENS.text_primary}; "
        f"border: 1px solid {TOKENS.border}; border-radius: 2px; padding: 0 {TOKENS.spacing_md}px; }}"
        f"QToolButton:hover {{ background: {TOKENS.raised_background}; }}"
        f"QToolButton:pressed {{ background: {TOKENS.workspace_background}; border-color: {TOKENS.accent}; }}"
        f"QToolButton:disabled {{ color: {TOKENS.text_disabled}; border-color: {TOKENS.border}; }}"
    )


def _insert_before_stretch(layout: QHBoxLayout, widget: QWidget) -> None:
    target = layout.count()
    for index in range(layout.count()):
        item = layout.itemAt(index)
        if item is not None and item.spacerItem() is not None:
            target = index
            break
    layout.insertWidget(target, widget)


class ReviewSelectionController(QObject):
    """Own direct temporary source curation without becoming analysis authority."""

    def __init__(self, window: Any) -> None:
        super().__init__(window)
        self.window = window
        self.state = ReviewSelectionState()
        self._applying = False
        self._original_select_document_ids = window._select_document_ids
        self._original_remove_document_ids = window._remove_document_ids
        self._build_controls()
        self._connect_viewers()
        self._install_selection_invalidation_boundary()
        self._sync_all()

    @property
    def active(self) -> bool:
        return self.state.active

    @property
    def picked_count(self) -> int:
        return self.state.picked_count

    @property
    def picked_ids(self) -> frozenset[str]:
        return frozenset(self.state.picked_ids)

    def enter_review(self) -> bool:
        selected = self._selected_ids()
        if not selected:
            self._sync_all()
            return False
        self.state.enter(selected)
        self._sync_all()
        return True

    def cancel_review(self) -> None:
        if self.state.active:
            self.state.exit()
        self._sync_all()

    def clear_picks(self) -> None:
        self.state.clear_picks()
        self._sync_all()

    def keep_picked(self) -> bool:
        kept_ids = self.state.kept_selected_ids()
        if not self.state.active or not kept_ids:
            self._sync_all()
            return False
        self._close_active_difference()
        self._applying = True
        try:
            self._original_select_document_ids(list(kept_ids))
        finally:
            self._applying = False
            self.state.exit()
        self._sync_all()
        return True

    def _close_active_difference(self) -> None:
        difference = getattr(self.window, "_difference_document", None)
        action = getattr(self.window, "diff_action", None)
        if action is not None and action.isChecked():
            action.setChecked(False)
        if difference is not None and self.window.viewer.presented_document is difference:
            self.window.viewer.set_document(None)
            self.window.viewer.set_navigation_items([], "")
        difference_id = difference.document_id if isinstance(difference, ImageDocument) else None
        if difference_id is not None:
            self.window._multi_display_order = [
                item for item in self.window._multi_display_order if item != difference_id
            ]
            if self.window._focus_document_id == difference_id:
                self.window._focus_document_id = None
            if self.window._active_document_id == difference_id:
                self.window._active_document_id = None
        self.window._six_image_diff_restore_state = None
        self.window._difference_document = None
        self.window._difference_source_ids = None

    def _build_controls(self) -> None:
        parent = self.window.presentation_controls
        layout = self.window.presentation_controls_layout
        if not isinstance(parent, QWidget) or not isinstance(layout, QHBoxLayout):
            raise RuntimeError("Curation controls require the image presentation command row")
        self.separator = QFrame(parent)
        self.separator.setObjectName("curationSelectionSeparator")
        self.separator.setFrameShape(QFrame.Shape.VLine)
        self.separator.setFrameShadow(QFrame.Shadow.Plain)
        self.separator.setFixedHeight(TOKENS.control_height - 4)
        self.separator.setStyleSheet(f"QFrame {{ color: {TOKENS.border}; }}")
        self.count_label = QLabel("Selected 0", parent)
        self.count_label.setObjectName("reviewPickedCount")
        self.count_label.setAccessibleName("Temporary selected image count")
        self.count_label.setStyleSheet(f"QLabel {{ color: {TOKENS.text_primary}; font-weight: 600; }}")
        self.clear_button = QToolButton(parent)
        self.clear_button.setObjectName("reviewClearPicks")
        self.clear_button.setText("Clear Selection")
        self.clear_button.setAccessibleName("Clear Selection")
        self.clear_button.setToolTip("Clear the temporary multi-view selection without changing Files Selected")
        self.keep_button = QToolButton(parent)
        self.keep_button.setObjectName("reviewKeepPicked")
        self.keep_button.setText("Keep Selection")
        self.keep_button.setAccessibleName("Keep Selection")
        self.keep_button.setToolTip("Replace Files Selected with the temporary selection in original Selected order")
        for button in (self.clear_button, self.keep_button):
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.setFixedHeight(TOKENS.control_height)
            button.setMinimumWidth(96)
            button.setStyleSheet(_selection_button_style())
        self.clear_button.clicked.connect(self.clear_picks)  # type: ignore[attr-defined]
        self.keep_button.clicked.connect(self.keep_picked)  # type: ignore[attr-defined]
        for widget in (self.separator, self.count_label, self.clear_button, self.keep_button):
            _insert_before_stretch(layout, widget)

    def _connect_viewers(self) -> None:
        for viewer in self._all_viewers():
            viewer.header.pick_requested.connect(lambda checked, current=viewer: self._pick_requested(current, checked))
            viewer.document_changed.connect(lambda _document, current=viewer: self._sync_tile(current))

    def _install_selection_invalidation_boundary(self) -> None:
        def select_document_ids(document_ids: Sequence[str], *args: object, **kwargs: object) -> Any:
            requested = tuple(item for item in document_ids if item in self.window.documents)
            self._invalidate_for_selected_mutation(requested)
            result = self._original_select_document_ids(list(document_ids), *args, **kwargs)
            self._sync_all()
            return result

        def remove_document_ids(document_ids: Sequence[str], *args: object, **kwargs: object) -> Any:
            self._invalidate_for_removed_ids(document_ids)
            result = self._original_remove_document_ids(list(document_ids), *args, **kwargs)
            self._sync_all()
            return result

        self.window._select_document_ids = select_document_ids
        self.window._remove_document_ids = remove_document_ids
        self.window.document_list.selection_changing.connect(self._files_selection_changing)
        self.window.document_list.itemSelectionChanged.connect(self._files_selection_changed)
        self.window.document_list.remove_changing.connect(self._files_remove_changing)
        self.window.document_list.remove_requested.connect(self._files_remove_changed)

    def _invalidate_for_selected_mutation(self, requested: Sequence[str]) -> None:
        if self.state.active and not self._applying and tuple(requested) != self.state.baseline_selected_ids:
            self.state.exit()

    def _invalidate_for_removed_ids(self, document_ids: Sequence[str]) -> None:
        if not self.state.active or self._applying:
            return
        baseline = set(self.state.baseline_selected_ids)
        if any(item in baseline for item in document_ids):
            self.state.exit()

    def _files_selection_changing(self) -> None:
        if self.state.active and not self._applying:
            self.state.exit()

    def _files_selection_changed(self) -> None:
        self._sync_all()

    def _files_remove_changing(self, document_ids: object) -> None:
        if isinstance(document_ids, list):
            self._invalidate_for_removed_ids([str(item) for item in document_ids])

    def _files_remove_changed(self, _document_ids: object) -> None:
        if self.state.active and not self.state.matches_selected_ids(self._selected_ids()):
            self.state.exit()
        self._sync_all()

    def _pick_requested(self, viewer: ImageViewer, checked: bool) -> None:
        document_id = self._pickable_document_id(viewer.presented_document)
        if document_id is None or viewer not in self.window.multi_compare_view.viewers:
            self._sync_tile(viewer)
            return
        if checked and not self.state.active:
            selected = self._selected_ids()
            if not selected or document_id not in selected:
                self._sync_tile(viewer)
                return
            self.state.enter(selected)
        if not self.state.active:
            self._sync_tile(viewer)
            return
        self.state.set_picked(document_id, checked)
        self._sync_all()

    def _pickable_document_id(self, document: ImageDocument | None) -> str | None:
        if document is None or document.document_id not in self.window.documents:
            return None
        authority = self.state.baseline_selected_ids if self.state.active else self._selected_ids()
        return document.document_id if document.document_id in authority else None

    def _selected_ids(self) -> tuple[str, ...]:
        return tuple(document.document_id for document in self.window.selected_documents)

    def _all_viewers(self) -> tuple[ImageViewer, ...]:
        return (self.window.viewer, *tuple(self.window.multi_compare_view.viewers))

    def _sync_all(self) -> None:
        self.count_label.setText(f"Selected {self.state.picked_count}")
        self.count_label.setEnabled(bool(self._selected_ids()))
        enabled = self.state.picked_count > 0
        self.clear_button.setEnabled(enabled)
        self.keep_button.setEnabled(enabled)
        for viewer in self._all_viewers():
            self._sync_tile(viewer)

    def _difference_tooltip(self) -> str:
        source_ids = getattr(self.window, "_difference_source_ids", None)
        if not isinstance(source_ids, tuple) or len(source_ids) != 2:
            return "Derived from source images. Keep Selection closes the active Difference."
        names = [self.window.documents[item].display_name if item in self.window.documents else item for item in source_ids]
        return f"Derived from {names[0]} / {names[1]}. Keep Selection closes the active Difference; its cache is retained."

    def _difference_reference(self, difference: ImageDocument) -> tuple[str, int, str, int, str, str] | None:
        source_ids = getattr(self.window, "_difference_source_ids", None)
        if not isinstance(source_ids, tuple) or len(source_ids) != 2:
            return None
        slots = {document.document_id: index + 1 for index, document in enumerate(self.window.current_comparison_documents())}
        a = self.window.documents.get(source_ids[0])
        b = self.window.documents.get(source_ids[1])
        a_slot, b_slot = slots.get(source_ids[0]), slots.get(source_ids[1])
        if a is None or b is None or a_slot is None or b_slot is None:
            return None
        semantic, separator, _details = difference.display_name.partition(":")
        prefix = f"{semantic.strip()}:" if separator else "Difference:"
        tooltip = f"{prefix} [{a_slot}] {a.display_name} vs [{b_slot}] {b.display_name}"
        return prefix, a_slot, a.display_name, b_slot, b.display_name, tooltip

    def _sync_tile(self, viewer: ImageViewer) -> None:
        presented = viewer.presented_document
        difference = getattr(self.window, "_difference_document", None)
        is_difference = presented is not None and presented is difference
        document_id = self._pickable_document_id(presented) if viewer in self.window.multi_compare_view.viewers else None
        picked = document_id in self.state.picked_ids if document_id is not None else False
        viewer.setProperty("reviewPicked", picked)
        viewer.setStyleSheet(tile_style(bool(getattr(viewer, "_active", False))))
        viewer.header.set_review_pick(visible=document_id is not None, picked=picked)
        viewer.header.set_review_derived(visible=is_difference, tooltip=self._difference_tooltip() if is_difference else "")
        reference = self._difference_reference(difference) if is_difference else None
        if reference is None:
            viewer.header.set_difference_reference(visible=False)
            return
        prefix, a_slot, a_name, b_slot, b_name, tooltip = reference
        viewer.header.set_difference_reference(visible=True, prefix=prefix, a_slot=a_slot, a_name=a_name, b_slot=b_slot, b_name=b_name, detailed=viewer is self.window.viewer, tooltip=tooltip)


def install_review_selection(window: Any) -> ReviewSelectionController:
    existing = getattr(window, "review_selection_controller", None)
    if isinstance(existing, ReviewSelectionController):
        return existing
    controller = ReviewSelectionController(window)
    window.review_selection_controller = controller
    return controller
