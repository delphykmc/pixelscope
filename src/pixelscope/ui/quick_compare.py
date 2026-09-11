from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from PySide6.QtCore import QEvent, QObject, QRectF, Qt, QTimer
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QKeyEvent
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QButtonGroup,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QTextEdit,
    QToolButton,
    QWidget,
)

from pixelscope.io.path_discovery import discover_image_inputs
from pixelscope.ui.design_tokens import TOKENS
from pixelscope.ui.image_viewer import ImageViewer


@dataclass(frozen=True)
class _BlinkSnapshot:
    viewer: ImageViewer
    image: object
    rect: QRectF


class QuickCompareController(QObject):
    """Issue #77 WP-C interaction controller without parallel selection state."""

    _THREE_VIEW_VARIANTS = ("Equal", "Focus")

    def __init__(self, window: Any) -> None:
        super().__init__(window)
        self.window = window
        self.view = window.multi_compare_view
        self._three_view_context: tuple[frozenset[str], bool] | None = None
        self._three_view_override: str | None = None
        self._pending_difference_pair: tuple[str, str] | None = None
        self._difference_retry_count = 0
        self._blink_snapshot: _BlinkSnapshot | None = None
        self._protected_difference_pair: tuple[str, str] | None = None

        self._original_prepare = self.view._prepare_viewers_for_documents
        self._original_fixed_geometry = self.view._fixed_geometry
        self._original_render_selection = window._render_selection

        self._difference_retry_timer = QTimer(self)
        self._difference_retry_timer.setInterval(50)
        self._difference_retry_timer.timeout.connect(self._try_pending_difference)
        window.difference_panel.result_ready.connect(  # type: ignore[attr-defined]
            self._quick_difference_completed
        )

        self._build_three_view_controls()
        self._install_three_view_geometry()
        self._install_render_hook()
        self._install_input_filter()

    def _build_three_view_controls(self) -> None:
        group = QWidget(self.window.presentation_controls)
        group.setObjectName("threeViewVariantControl")
        layout = QHBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(TOKENS.spacing_xs)
        label = QLabel("3 View", group)
        equal = QToolButton(group)
        focus = QToolButton(group)
        equal.setText("Equal")
        focus.setText("Focus")
        for button in (equal, focus):
            button.setCheckable(True)
            button.setAutoRaise(True)
        buttons = QButtonGroup(group)
        buttons.setExclusive(True)
        buttons.addButton(equal)
        buttons.addButton(focus)
        equal.clicked.connect(  # type: ignore[attr-defined]
            lambda: self.set_three_view_variant("Equal")
        )
        focus.clicked.connect(  # type: ignore[attr-defined]
            lambda: self.set_three_view_variant("Focus")
        )
        layout.addWidget(label)
        layout.addWidget(equal)
        layout.addWidget(focus)
        group.hide()
        self.window.presentation_controls_layout.addWidget(group)

        self.three_view_group = group
        self.three_view_label = label
        self.three_view_equal = equal
        self.three_view_focus = focus
        self._sync_three_view_buttons("Equal")

    def _install_three_view_geometry(self) -> None:
        def prepare_viewers_for_documents(documents: list[Any]) -> None:
            self._original_prepare(documents)
            target = documents[: self.view.capacity]
            context = (
                frozenset(str(document.document_id) for document in target),
                any(document.channel_layout == "DIFFERENCE" for document in target),
            )
            if context != self._three_view_context:
                self._three_view_context = context
                self._three_view_override = None
            self._sync_three_view_buttons(self._effective_three_view_variant())

        def fixed_geometry(count: int) -> Any:
            if count == 3 and self._effective_three_view_variant() == "Equal":
                return (
                    ((0, 0, 1, 1), (0, 1, 1, 1), (0, 2, 1, 1)),
                    (1,),
                    (1, 1, 1),
                )
            return self._original_fixed_geometry(count)

        self.view._prepare_viewers_for_documents = prepare_viewers_for_documents
        self.view._fixed_geometry = fixed_geometry

    def _install_render_hook(self) -> None:
        def render_selection(preserve_view: bool = False) -> None:
            self._end_blink()
            self._original_render_selection(preserve_view)
            self._update_three_view_controls()

        self.window._render_selection = render_selection

    def _install_input_filter(self) -> None:
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            raise RuntimeError("Quick Compare requires QApplication")
        app.installEventFilter(self)
        self._app = app
        surfaces = [
            self.window.central_stack,
            self.window.viewer,
            self.window.multi_compare_view,
            self.window.viewer._graphics,
            self.window.viewer._graphics.viewport(),
        ]
        surfaces.extend(viewer._graphics for viewer in self.window.multi_compare_view.viewers)
        surfaces.extend(
            viewer._graphics.viewport() for viewer in self.window.multi_compare_view.viewers
        )
        for surface in surfaces:
            if isinstance(surface, QWidget):
                surface.setAcceptDrops(True)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        event_type = event.type()
        if (
            event_type in (QEvent.Type.DragEnter, QEvent.Type.Drop)
            and self._is_image_surface(watched)
        ):
            drop_event = cast(QDropEvent, event)
            paths = self._local_paths(drop_event)
            if paths:
                if event_type == QEvent.Type.DragEnter:
                    cast(QDragEnterEvent, event).acceptProposedAction()
                    return True
                if any(path.is_dir() for path in paths):
                    self.window._handle_dropped_paths(paths)
                    drop_event.acceptProposedAction()
                    return True
                if self.handle_image_drop(paths):
                    drop_event.acceptProposedAction()
                    return True

        if event_type == QEvent.Type.KeyPress:
            key_event = cast(QKeyEvent, event)
            if (
                self._app.activeWindow() is self.window
                and key_event.key() == Qt.Key.Key_B
                and key_event.modifiers() == Qt.KeyboardModifier.NoModifier
                and not key_event.isAutoRepeat()
                and not self._text_input_has_focus()
                and self._begin_blink()
            ):
                event.accept()
                return True
        elif event_type == QEvent.Type.KeyRelease:
            key_event = cast(QKeyEvent, event)
            if (
                key_event.key() == Qt.Key.Key_B
                and not key_event.isAutoRepeat()
                and self._blink_snapshot is not None
            ):
                self._end_blink()
                event.accept()
                return True
        # QApplication can route internal Qt objects (for example QWidgetItem) through
        # an application-level filter. Calling QObject.eventFilter() with those Python
        # wrappers raises in PySide6; the default QObject implementation is a no-op.
        return False

    def _is_image_surface(self, watched: QObject) -> bool:
        if not isinstance(watched, QWidget):
            return False
        central = self.window.central_stack
        return watched is central or central.isAncestorOf(watched)

    @staticmethod
    def _local_paths(event: QDropEvent) -> list[Path]:
        mime = event.mimeData()
        if not mime.hasUrls():
            return []
        return [Path(url.toLocalFile()) for url in mime.urls() if url.isLocalFile()]

    def handle_image_drop(self, paths: list[Path]) -> bool:
        files = [path for path in paths if path.is_file()]
        if not files:
            return False
        document_ids = self.window._register_inputs(
            discover_image_inputs(files),
            resolve_raw_profiles=True,
        )
        if not document_ids:
            self.window.statusBar().showMessage("Quick Compare: no supported images", 4000)
            return True
        self._apply_registered_drop(document_ids)
        return True

    def _apply_registered_drop(self, document_ids: list[str]) -> None:
        previous_ids = [document.document_id for document in self.window.selected_documents]
        previous_set = set(previous_ids)
        unique_dropped: list[str] = []
        seen: set[str] = set()
        for document_id in document_ids:
            if document_id not in seen:
                unique_dropped.append(document_id)
                seen.add(document_id)
        additions = [
            document_id for document_id in unique_dropped if document_id not in previous_set
        ]
        merged = [*previous_ids, *additions]
        if additions:
            self.window._select_document_ids(merged, preserve_view=True)

        added = len(additions)
        if added:
            self.window.statusBar().showMessage(
                f"Quick Compare: added {added} image(s) · {len(merged)} selected",
                4000,
            )
        else:
            self.window.statusBar().showMessage(
                "Quick Compare: dropped image(s) already selected",
                3500,
            )

        pair = self._quick_difference_pair(previous_ids, unique_dropped, merged)
        if pair is not None:
            self._schedule_difference(pair)

    def _quick_difference_pair(
        self,
        previous_ids: list[str],
        dropped_ids: list[str],
        merged_ids: list[str],
    ) -> tuple[str, str] | None:
        existing = self.window._difference_source_ids
        if existing is not None and set(existing).issubset(set(merged_ids)):
            return None
        protected = self._protected_difference_pair
        if protected is not None:
            still_selected = set(protected).issubset(set(merged_ids))
            in_flight = (
                self._pending_difference_pair == protected
                or self.window.difference_panel._worker is not None
            )
            if still_selected and in_flight:
                return None
            self._protected_difference_pair = None
        if len(dropped_ids) == 2 and dropped_ids[0] != dropped_ids[1]:
            return dropped_ids[0], dropped_ids[1]
        if (
            len(dropped_ids) == 1
            and len(previous_ids) == 1
            and len(merged_ids) == 2
            and dropped_ids[0] != previous_ids[0]
        ):
            return previous_ids[0], dropped_ids[0]
        return None

    def _schedule_difference(self, pair: tuple[str, str]) -> None:
        self._pending_difference_pair = pair
        self._protected_difference_pair = pair
        self._difference_retry_count = 0
        self._try_pending_difference()

    def _try_pending_difference(self) -> None:
        pair = self._pending_difference_pair
        if pair is None:
            self._difference_retry_timer.stop()
            return
        selected_ids = {document.document_id for document in self.window.selected_documents}
        if not set(pair).issubset(selected_ids):
            self._clear_pending_difference(clear_protected=True)
            return
        existing = self.window._difference_source_ids
        if existing is not None and existing != pair and set(existing).issubset(selected_ids):
            self._clear_pending_difference(clear_protected=True)
            return

        comparison = self.window.current_comparison_documents()
        comparison_ids = {document.document_id for document in comparison}
        if not set(pair).issubset(comparison_ids):
            self.window.statusBar().showMessage(
                "Quick Compare: Difference requires both dropped sources on the current page",
                4500,
            )
            self._clear_pending_difference(clear_protected=True)
            return

        pair_documents = [self.window.documents.get(document_id) for document_id in pair]
        if any(document is None for document in pair_documents):
            self._clear_pending_difference(clear_protected=True)
            return
        if any(document.preview is None for document in pair_documents):
            self._difference_retry_count += 1
            if self._difference_retry_count >= 200:
                self.window.statusBar().showMessage(
                    "Quick Compare: Difference unavailable because a source did not finish loading",
                    5000,
                )
                self._clear_pending_difference(clear_protected=True)
            else:
                self._difference_retry_timer.start()
            return

        panel = self.window.difference_panel
        panel.set_documents(comparison, pair, self.window._shared_roi)
        selected_pair = panel.selected_documents()
        if (
            selected_pair is not None
            and tuple(document.document_id for document in selected_pair) == pair
            and panel.calculate.isEnabled()
        ):
            self._clear_pending_difference(clear_protected=False)
            panel.calculate_difference()
            return

        message = panel.status.text().strip() or "Difference is unavailable for the dropped pair"
        self.window.statusBar().showMessage(f"Quick Compare: {message}", 5000)
        self._clear_pending_difference(clear_protected=True)

    def _clear_pending_difference(self, *, clear_protected: bool) -> None:
        self._pending_difference_pair = None
        self._difference_retry_count = 0
        self._difference_retry_timer.stop()
        if clear_protected:
            self._protected_difference_pair = None

    def _quick_difference_completed(
        self,
        _title: object,
        _numerical: object,
        _preview: object,
    ) -> None:
        protected = self._protected_difference_pair
        if protected is None:
            return
        pair = self.window.difference_panel.selected_documents()
        if pair is not None and tuple(document.document_id for document in pair) == protected:
            self._protected_difference_pair = None

    def _effective_three_view_variant(self) -> str:
        if self._three_view_override in self._THREE_VIEW_VARIANTS:
            return self._three_view_override
        if self._three_view_context is not None and self._three_view_context[1]:
            return "Focus"
        return "Equal"

    def set_three_view_variant(self, variant: str) -> None:
        if variant not in self._THREE_VIEW_VARIANTS:
            raise ValueError(f"unsupported 3-view variant: {variant}")
        if self.view._document_count != 3:
            return
        state = self.view.capture_view_state()
        self._three_view_override = variant
        self._sync_three_view_buttons(variant)
        self.view._arranged_count = -1
        self.view._arrange_viewers(3)
        self.view._layout.activate()
        self.view.restore_view_state(state)

    def _sync_three_view_buttons(self, variant: str) -> None:
        for button, name in (
            (self.three_view_equal, "Equal"),
            (self.three_view_focus, "Focus"),
        ):
            button.blockSignals(True)
            button.setChecked(variant == name)
            button.blockSignals(False)

    def _update_three_view_controls(self) -> None:
        visible = (
            self.window.central_stack.currentWidget() is self.window.multi_compare_view
            and self.view._document_count == 3
        )
        self.three_view_group.setVisible(visible)
        self._sync_three_view_buttons(self._effective_three_view_variant())

    def _text_input_has_focus(self) -> bool:
        focus = self._app.focusWidget()
        return isinstance(
            focus,
            QLineEdit | QAbstractSpinBox | QComboBox | QTextEdit | QPlainTextEdit,
        )

    def _blink_sources(self) -> tuple[Any, Any] | None:
        if self.window._channel_split_active:
            return None
        sources = self.window.selected_documents
        if len(sources) != 2:
            return None
        if any(document.preview is None for document in sources):
            return None
        return sources[0], sources[1]

    def _viewer_for_document(self, document_id: str) -> ImageViewer | None:
        if (
            self.window.viewer.document is not None
            and self.window.viewer.document.document_id == document_id
        ):
            return self.window.viewer
        viewer = next(
            (
                candidate
                for candidate in self.view.viewers
                if candidate.document is not None
                and candidate.document.document_id == document_id
            ),
            None,
        )
        return cast(ImageViewer | None, viewer)

    def _begin_blink(self) -> bool:
        if self._blink_snapshot is not None:
            return True
        sources = self._blink_sources()
        if sources is None:
            return False
        reference, alternate = sources
        reference_viewer = self._viewer_for_document(reference.document_id)
        alternate_viewer = self._viewer_for_document(alternate.document_id)
        if reference_viewer is None:
            return False
        alternate_image: object | None = None
        alternate_rect: QRectF | None = None
        if alternate_viewer is not None and alternate_viewer.image_item.image is not None:
            alternate_image = alternate_viewer.image_item.image
            alternate_rect = QRectF(alternate_viewer.image_item.boundingRect())
        elif alternate.preview is not None:
            alternate_image = alternate.preview
            alternate_rect = QRectF(reference_viewer._presentation_rect(alternate))
        if alternate_image is None or alternate_rect is None:
            return False
        current_image = reference_viewer.image_item.image
        if current_image is None:
            return False

        self._blink_snapshot = _BlinkSnapshot(
            reference_viewer,
            current_image,
            QRectF(reference_viewer.image_item.boundingRect()),
        )
        reference_viewer.image_item.setImage(cast(Any, alternate_image), autoLevels=False)
        reference_viewer.image_item.setRect(alternate_rect)
        return True

    def _end_blink(self) -> None:
        snapshot = self._blink_snapshot
        if snapshot is None:
            return
        snapshot.viewer.image_item.setImage(cast(Any, snapshot.image), autoLevels=False)
        snapshot.viewer.image_item.setRect(snapshot.rect)
        self._blink_snapshot = None


def install_quick_compare_workflow(window: Any) -> QuickCompareController:
    existing = getattr(window, "quick_compare_controller", None)
    if isinstance(existing, QuickCompareController):
        return existing
    controller = QuickCompareController(window)
    window.quick_compare_controller = controller
    return controller
