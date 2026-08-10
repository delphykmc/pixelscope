from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QWidget

from pixelscope.core.image_document import ImageDocument
from pixelscope.core.review_selection import ReviewSelectionState
from pixelscope.ui.design_tokens import TOKENS, tile_style
from pixelscope.ui.image_viewer import ImageViewer


def _review_controls_style() -> str:
    return (
        f"QWidget#reviewSelectionControl {{ color: {TOKENS.text_primary}; }}"
        f"QWidget#reviewSelectionControl QLabel {{ color: {TOKENS.text_secondary}; }}"
        f"QWidget#reviewSelectionControl QToolButton {{ background: transparent; "
        f"color: {TOKENS.text_primary}; border: 1px solid {TOKENS.border}; "
        f"border-radius: 2px; padding: 0 {TOKENS.spacing_sm}px; }}"
        f"QWidget#reviewSelectionControl QToolButton:hover {{ "
        f"background: {TOKENS.raised_background}; }}"
        f"QWidget#reviewSelectionControl QToolButton:checked {{ "
        f"color: {TOKENS.accent}; border-color: {TOKENS.accent}; }}"
        f"QWidget#reviewSelectionControl QToolButton:disabled {{ "
        f"color: {TOKENS.text_disabled}; border-color: {TOKENS.border}; }}"
    )


class ReviewSelectionController(QObject):
    """Own temporary review picks without acquiring source or analysis authority."""

    def __init__(self, window: Any) -> None:
        super().__init__(window)
        self.window = window
        self.state = ReviewSelectionState()
        self._applying = False
        self._original_selection_changed = window._selection_changed
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
        selected_ids = self._selected_ids()
        if not selected_ids:
            self._sync_all()
            return False
        self.state.enter(selected_ids)
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
        self._applying = True
        try:
            self._original_select_document_ids(list(kept_ids))
        finally:
            self._applying = False
            self.state.exit()
        self._sync_all()
        return True

    def _build_controls(self) -> None:
        parent = self.window.presentation_controls
        self.host = QWidget(parent)
        self.host.setObjectName("reviewSelectionControl")
        self.host.setAccessibleName("Review selection controls")
        self.host.setStyleSheet(_review_controls_style())
        layout = QHBoxLayout(self.host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(TOKENS.spacing_xs)

        self.mode_button = QToolButton(self.host)
        self.mode_button.setObjectName("reviewSelectMode")
        self.mode_button.setText("Review Select")
        self.mode_button.setAccessibleName("Review Select")
        self.mode_button.setCheckable(True)
        self.mode_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.mode_button.setFixedHeight(TOKENS.control_height)
        self.mode_button.setToolTip(
            "Pick images across Comparison Pages, then keep only the picked subset"
        )
        self.mode_button.clicked.connect(self._mode_clicked)  # type: ignore[attr-defined]

        self.count_label = QLabel("Picked 0", self.host)
        self.count_label.setObjectName("reviewPickedCount")
        self.count_label.setAccessibleName("Picked image count")

        self.clear_button = QToolButton(self.host)
        self.clear_button.setObjectName("reviewClearPicks")
        self.clear_button.setText("Clear Picks")
        self.clear_button.setAccessibleName("Clear Picks")
        self.clear_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.clear_button.setFixedHeight(TOKENS.control_height)
        self.clear_button.clicked.connect(self.clear_picks)  # type: ignore[attr-defined]

        self.keep_button = QToolButton(self.host)
        self.keep_button.setObjectName("reviewKeepPicked")
        self.keep_button.setText("Keep Picked")
        self.keep_button.setAccessibleName("Keep Picked")
        self.keep_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.keep_button.setFixedHeight(TOKENS.control_height)
        self.keep_button.setToolTip(
            "Replace Selected with the picked subset in original Selected order"
        )
        self.keep_button.clicked.connect(self.keep_picked)  # type: ignore[attr-defined]

        self.cancel_button = QToolButton(self.host)
        self.cancel_button.setObjectName("reviewCancel")
        self.cancel_button.setText("Cancel")
        self.cancel_button.setAccessibleName("Cancel Review Select")
        self.cancel_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.cancel_button.setFixedHeight(TOKENS.control_height)
        self.cancel_button.clicked.connect(self.cancel_review)  # type: ignore[attr-defined]

        layout.addWidget(self.mode_button)
        layout.addWidget(self.count_label)
        layout.addWidget(self.clear_button)
        layout.addWidget(self.keep_button)
        layout.addWidget(self.cancel_button)
        self.window.presentation_controls_layout.addWidget(self.host)

    def _connect_viewers(self) -> None:
        for viewer in self._all_viewers():
            viewer.header.pick_requested.connect(
                lambda checked, current=viewer: self._pick_requested(current, checked)
            )
            viewer.document_changed.connect(
                lambda _document, current=viewer: self._sync_tile(current)
            )

    def _install_selection_invalidation_boundary(self) -> None:
        def select_document_ids(
            document_ids: Sequence[str],
            *args: object,
            **kwargs: object,
        ) -> Any:
            requested = tuple(
                document_id for document_id in document_ids if document_id in self.window.documents
            )
            self._invalidate_for_selected_mutation(requested)
            result = self._original_select_document_ids(list(document_ids), *args, **kwargs)
            self._sync_all()
            return result

        def remove_document_ids(
            document_ids: Sequence[str],
            *args: object,
            **kwargs: object,
        ) -> Any:
            if self.state.active and not self._applying:
                baseline = set(self.state.baseline_selected_ids)
                if any(document_id in baseline for document_id in document_ids):
                    self.cancel_review()
            result = self._original_remove_document_ids(list(document_ids), *args, **kwargs)
            self._sync_all()
            return result

        self.window._select_document_ids = select_document_ids
        self.window._remove_document_ids = remove_document_ids

        # MainWindow connected these signals during construction, so replacing only
        # the instance attributes would leave the original bound callables stored in
        # Qt. Reconnect the production paths through the review invalidation wrappers.
        self.window.document_list.remove_requested.disconnect(
            self._original_remove_document_ids
        )
        self.window.document_list.remove_requested.connect(remove_document_ids)
        self.window.document_list.itemSelectionChanged.disconnect(
            self._original_selection_changed
        )
        self.window.document_list.itemSelectionChanged.connect(self._files_selection_changing)
        self.window.document_list.itemSelectionChanged.connect(self._selection_changed_and_sync)

    def _invalidate_for_selected_mutation(self, requested: Sequence[str]) -> None:
        if (
            self.state.active
            and not self._applying
            and tuple(requested) != self.state.baseline_selected_ids
        ):
            self.cancel_review()

    def _files_selection_changing(self) -> None:
        if not self.state.active or self._applying:
            return
        selected_ids = {
            str(item.data(0, Qt.ItemDataRole.UserRole))
            for item in self.window.document_list.document_items()
            if item.isSelected()
        }
        if selected_ids != set(self.state.baseline_selected_ids):
            self.state.exit()
            for viewer in self._all_viewers():
                self._sync_tile(viewer)

    def _selection_changed_and_sync(self) -> None:
        self._original_selection_changed()
        self._sync_all()

    def _mode_clicked(self, checked: bool) -> None:
        if checked:
            if not self.enter_review():
                self._sync_controls()
        else:
            self.cancel_review()

    def _pick_requested(self, viewer: ImageViewer, checked: bool) -> None:
        document_id = self._pickable_document_id(viewer.presented_document)
        if document_id is None:
            self._sync_tile(viewer)
            return
        self.state.set_picked(document_id, checked)
        self._sync_all()

    def _pickable_document_id(self, document: ImageDocument | None) -> str | None:
        if not self.state.active or document is None:
            return None
        document_id = document.document_id
        if document_id not in self.state.baseline_selected_ids:
            return None
        if document_id not in self.window.documents:
            return None
        return document_id

    def _selected_ids(self) -> tuple[str, ...]:
        return tuple(document.document_id for document in self.window.selected_documents)

    def _all_viewers(self) -> tuple[ImageViewer, ...]:
        return (self.window.viewer, *tuple(self.window.multi_compare_view.viewers))

    def _sync_all(self) -> None:
        self._sync_controls()
        for viewer in self._all_viewers():
            self._sync_tile(viewer)

    def _sync_controls(self) -> None:
        active = self.state.active
        self.mode_button.blockSignals(True)
        self.mode_button.setChecked(active)
        self.mode_button.blockSignals(False)
        self.mode_button.setEnabled(active or bool(self._selected_ids()))
        self.count_label.setText(f"Picked {self.state.picked_count}")
        self.count_label.setVisible(active)
        self.clear_button.setVisible(active)
        self.keep_button.setVisible(active)
        self.cancel_button.setVisible(active)
        has_picks = self.state.picked_count > 0
        self.clear_button.setEnabled(has_picks)
        self.keep_button.setEnabled(has_picks)

    def _sync_tile(self, viewer: ImageViewer) -> None:
        document_id = self._pickable_document_id(viewer.presented_document)
        picked = document_id in self.state.picked_ids if document_id is not None else False
        viewer.setProperty("reviewPicked", picked)
        viewer.setStyleSheet(tile_style(bool(getattr(viewer, "_active", False))))
        viewer.header.set_review_pick(
            visible=document_id is not None,
            picked=picked,
        )


def install_review_selection(window: Any) -> ReviewSelectionController:
    """Install the P4-A temporary review/curation workflow once per MainWindow."""

    existing = getattr(window, "review_selection_controller", None)
    if isinstance(existing, ReviewSelectionController):
        return existing
    controller = ReviewSelectionController(window)
    window.review_selection_controller = controller
    return controller
