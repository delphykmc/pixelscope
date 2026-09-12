from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray
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

from pixelscope.core.display_transform import render_ordinary_display_preview
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.raw_display import render_raw_preview
from pixelscope.io.path_discovery import discover_image_inputs
from pixelscope.io.raw_profile import RawProfile
from pixelscope.ui.design_tokens import TOKENS
from pixelscope.ui.display_gain import display_gain_state, is_display_gain_capable
from pixelscope.ui.image_viewer import ImageViewer, _display_preview_thread_pool
from pixelscope.workers.task_worker import TaskWorker

_BlinkRenderIdentity = tuple[int, int, int, int, float]


@dataclass(frozen=True)
class _BlinkSnapshot:
    viewer: ImageViewer
    reference: ImageDocument
    alternate: ImageDocument


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
        self._blink_render_worker: TaskWorker | None = None
        self._blink_render_request_serial = 0
        self._blink_render_request_identity: _BlinkRenderIdentity | None = None
        self._blink_cache_identity: _BlinkRenderIdentity | None = None
        self._blink_cache_preview: NDArray[np.uint8] | None = None
        self._protected_difference_pair: tuple[str, str] | None = None

        self._original_prepare = self.view._prepare_viewers_for_documents
        self._original_fixed_geometry = self.view._fixed_geometry
        self._original_render_selection = window._render_selection
        self._display_gain_state = display_gain_state()
        self._display_gain_state.gain_changed.connect(self._display_gain_changed_during_blink)

        self._difference_retry_timer = QTimer(self)
        self._difference_retry_timer.setInterval(50)
        self._difference_retry_timer.timeout.connect(  # type: ignore[attr-defined]
            self._try_pending_difference
        )
        window.difference_panel.result_ready.connect(self._quick_difference_completed)

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

        command_layout = self.window.presentation_controls_layout
        stretch_index = command_layout.count()
        for index in range(command_layout.count()):
            item = command_layout.itemAt(index)
            if item is not None and item.spacerItem() is not None:
                stretch_index = index
                break
        command_layout.insertWidget(stretch_index, group)
        metric_owner = getattr(self.window, "_command_row_metric_refresh", None)
        refresh = getattr(metric_owner, "refresh", None)
        if callable(refresh):
            refresh()

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
            self._clear_blink_cache()
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
        if event_type in (QEvent.Type.DragEnter, QEvent.Type.Drop) and self._is_image_surface(
            watched
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

        if event_type in (QEvent.Type.ApplicationDeactivate, QEvent.Type.WindowDeactivate):
            self._end_blink()
        elif watched is self.window and event_type == QEvent.Type.Close:
            self._end_blink()
            self._cancel_blink_render(clear_cache=True)

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

    def _blink_sources(self) -> tuple[ImageDocument, ImageDocument] | None:
        if self.window._channel_split_active:
            return None
        sources = self.window.selected_documents
        if len(sources) != 2:
            return None
        if any(document.preview is None for document in sources):
            return None
        return sources[0], sources[1]

    def _viewer_for_document(self, document_id: str) -> ImageViewer | None:
        single_viewer = self.window.viewer
        if (
            isinstance(single_viewer, ImageViewer)
            and single_viewer.document is not None
            and single_viewer.document.document_id == document_id
        ):
            return single_viewer
        for candidate in self.view.viewers:
            if (
                isinstance(candidate, ImageViewer)
                and candidate.document is not None
                and candidate.document.document_id == document_id
            ):
                return candidate
        return None

    def _blink_context(self) -> tuple[ImageViewer, ImageDocument, ImageDocument] | None:
        sources = self._blink_sources()
        if sources is None:
            return None

        if self.window.central_stack.currentWidget() is self.window.viewer:
            visible = self.window.viewer.document
            if visible is None:
                return None
            reference = next(
                (document for document in sources if document.document_id == visible.document_id),
                None,
            )
            if reference is None:
                return None
            alternate = sources[1] if sources[0] is reference else sources[0]
            return self.window.viewer, reference, alternate

        reference, alternate = sources
        reference_viewer = self._viewer_for_document(reference.document_id)
        if reference_viewer is None:
            return None
        return reference_viewer, reference, alternate

    def _blink_render_identity(
        self,
        document: ImageDocument,
        gain: float,
    ) -> _BlinkRenderIdentity | None:
        source = document.source
        preview = document.preview
        if source is None or preview is None:
            return None
        return (id(document), id(source), id(preview), document.generation, float(gain))

    def _blink_presentation(self, document: ImageDocument) -> tuple[object, QRectF] | None:
        preview = document.preview
        if preview is None:
            return None
        rect = QRectF(ImageViewer._presentation_rect(document))
        gain_capable = is_display_gain_capable(document)
        gain = self._display_gain_state.gain
        candidate = self._viewer_for_document(document.document_id)
        if (
            candidate is not None
            and candidate.image_item.image is not None
            and (not gain_capable or gain == 1.0 or candidate._displayed_gain == gain)
        ):
            return candidate.image_item.image, rect
        if not gain_capable or gain == 1.0:
            return preview, rect

        identity = self._blink_render_identity(document, gain)
        if (
            identity is not None
            and identity == self._blink_cache_identity
            and self._blink_cache_preview is not None
        ):
            return self._blink_cache_preview, rect
        return None

    def _request_blink_render(self, document: ImageDocument) -> bool:
        gain = self._display_gain_state.gain
        if not is_display_gain_capable(document) or gain == 1.0:
            return False
        identity = self._blink_render_identity(document, gain)
        if identity is None:
            return False
        if identity == self._blink_cache_identity and self._blink_cache_preview is not None:
            return True
        if (
            identity == self._blink_render_request_identity
            and self._blink_render_worker is not None
        ):
            return True

        clear_cache = self._blink_cache_identity != identity
        self._cancel_blink_render(clear_cache=clear_cache)
        source = document.source
        preview = document.preview
        if source is None or preview is None:
            return False

        request_serial = self._blink_render_request_serial
        profile = document.raw_profile
        if isinstance(profile, RawProfile):
            worker = TaskWorker(
                render_raw_preview,
                source,
                document_id=document.document_id,
                generation=document.generation,
                channel_layout=document.channel_layout,
                bit_depth=profile.bit_depth,
                black_level=profile.black_level,
                bayer_pattern=profile.bayer_pattern,
                gain=gain,
            )
        else:
            worker = TaskWorker(
                render_ordinary_display_preview,
                source,
                document_id=document.document_id,
                generation=document.generation,
                channel_layout=document.channel_layout,
                transform=document.display_transform,
                canonical_preview=preview,
                gain=gain,
            )
        worker.signals.succeeded.connect(
            lambda task_id, document_id, generation, result: self._blink_render_succeeded(
                task_id,
                document_id,
                generation,
                result,
                request_serial=request_serial,
                expected_identity=identity,
                expected_document=document,
                expected_source=source,
                expected_preview=preview,
                expected_gain=gain,
            )
        )
        worker.signals.finished.connect(self._blink_render_finished)
        self._blink_render_worker = worker
        self._blink_render_request_identity = identity
        _display_preview_thread_pool().start(worker)
        return True

    def _blink_render_succeeded(
        self,
        task_id: str,
        document_id: object,
        generation: int,
        result: object,
        *,
        request_serial: int,
        expected_identity: _BlinkRenderIdentity,
        expected_document: ImageDocument,
        expected_source: object,
        expected_preview: object,
        expected_gain: float,
    ) -> None:
        worker = self._blink_render_worker
        if (
            worker is None
            or worker.task_id != task_id
            or request_serial != self._blink_render_request_serial
            or self._blink_render_request_identity != expected_identity
            or document_id != expected_document.document_id
            or generation != expected_document.generation
            or expected_document.source is not expected_source
            or expected_document.preview is not expected_preview
            or self._display_gain_state.gain != expected_gain
        ):
            return
        if not isinstance(result, np.ndarray) or result.dtype != np.uint8:
            return
        if not isinstance(expected_preview, np.ndarray) or result.shape != expected_preview.shape:
            return

        self._blink_cache_identity = expected_identity
        self._blink_cache_preview = result
        snapshot = self._blink_snapshot
        if snapshot is not None and snapshot.alternate is expected_document:
            self._show_blink_alternate(snapshot)

    def _blink_render_finished(self, task_id: str) -> None:
        worker = self._blink_render_worker
        if worker is not None and worker.task_id == task_id:
            self._blink_render_worker = None
            self._blink_render_request_identity = None

    def _cancel_blink_render(self, *, clear_cache: bool) -> None:
        self._blink_render_request_serial += 1
        worker = self._blink_render_worker
        if worker is not None:
            worker.cancel()
        self._blink_render_worker = None
        self._blink_render_request_identity = None
        if clear_cache:
            self._clear_blink_cache()

    def _clear_blink_cache(self) -> None:
        self._blink_cache_identity = None
        self._blink_cache_preview = None

    def _show_blink_alternate(self, snapshot: _BlinkSnapshot) -> bool:
        presentation = self._blink_presentation(snapshot.alternate)
        if presentation is None:
            return False
        image, rect = presentation
        snapshot.viewer.image_item.setImage(cast(Any, image), autoLevels=False)
        snapshot.viewer.image_item.setRect(rect)
        return True

    def _begin_blink(self) -> bool:
        if self._blink_snapshot is not None:
            return True
        context = self._blink_context()
        if context is None:
            return False
        reference_viewer, reference, alternate = context
        if reference_viewer.image_item.image is None:
            return False

        snapshot = _BlinkSnapshot(reference_viewer, reference, alternate)
        reference_viewer._cancel_display_preview()
        self._blink_snapshot = snapshot
        if self._show_blink_alternate(snapshot):
            return True
        if self._request_blink_render(alternate):
            return True

        self._blink_snapshot = None
        reference_viewer._ensure_display_preview()
        return False

    def _display_gain_changed_during_blink(self, _gain: float) -> None:
        snapshot = self._blink_snapshot
        self._cancel_blink_render(clear_cache=True)
        if snapshot is None:
            return
        snapshot.viewer._cancel_display_preview()
        if self._show_blink_alternate(snapshot):
            return
        if not self._request_blink_render(snapshot.alternate):
            self._end_blink()

    def _end_blink(self) -> None:
        snapshot = self._blink_snapshot
        if snapshot is None:
            return
        self._blink_snapshot = None
        self._cancel_blink_render(clear_cache=False)
        viewer = snapshot.viewer
        viewer._cancel_display_preview()
        document = viewer.document
        if document is None or viewer._displayed_preview is None:
            return
        viewer._upload_preview(viewer._displayed_preview, document)
        viewer._ensure_display_preview()


def install_quick_compare_workflow(window: Any) -> QuickCompareController:
    existing = getattr(window, "quick_compare_controller", None)
    if isinstance(existing, QuickCompareController):
        return existing
    controller = QuickCompareController(window)
    window.quick_compare_controller = controller
    return controller
