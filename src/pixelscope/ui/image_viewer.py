from __future__ import annotations

from contextlib import suppress
from math import ceil, cos, floor, isfinite, radians, sin
from typing import Any, cast

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import (
    QEvent,
    QObject,
    QPointF,
    QRectF,
    QSignalBlocker,
    Qt,
    QThreadPool,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QHideEvent,
    QKeyEvent,
    QKeySequence,
    QPainter,
    QPaintEvent,
    QPen,
    QShortcut,
    QShowEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsSceneResizeEvent,
    QVBoxLayout,
    QWidget,
)

from pixelscope.core import load_latency_trace
from pixelscope.core.display_transform import render_ordinary_display_preview
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineSelection, clamp_line
from pixelscope.core.raw_display import render_raw_preview
from pixelscope.core.roi import RoiBounds, clamp_roi
from pixelscope.io.raw_profile import RawProfile
from pixelscope.ui.design_tokens import tile_style
from pixelscope.ui.display_gain import display_gain_state, is_display_gain_capable
from pixelscope.ui.physical_zoom import PhysicalZoomMeasurement, ZoomApplyResult, measure_basis
from pixelscope.ui.tile_header import TileHeader
from pixelscope.workers.task_worker import TaskWorker

_DISPLAY_PREVIEW_MAX_THREADS = 2
_DISPLAY_PREVIEW_POOL_ATTRIBUTE = "_pixelscope_display_preview_thread_pool"


def _display_preview_thread_pool() -> QThreadPool:
    """Return the app-owned pool for memory-heavy Display Gain preview work."""

    app = QApplication.instance()
    if not isinstance(app, QApplication):
        raise RuntimeError("Display Gain preview workers require QApplication")
    existing = getattr(app, _DISPLAY_PREVIEW_POOL_ATTRIBUTE, None)
    if isinstance(existing, QThreadPool):
        return existing
    pool = QThreadPool(app)
    # Full-frame gain rendering is memory-bandwidth heavy and may allocate a
    # float32 working image plus an output preview per task. Keep concurrency
    # independent from the general worker pool so a six-tile view cannot launch
    # six such allocations at once or starve foreground/difference workers.
    pool.setMaxThreadCount(_DISPLAY_PREVIEW_MAX_THREADS)
    setattr(app, _DISPLAY_PREVIEW_POOL_ATTRIBUTE, pool)
    return pool


class LoadingSpinnerItem(QGraphicsItem):
    """Fixed-size, low-cost activity spinner drawn inside the image scene."""

    def __init__(self) -> None:
        super().__init__()
        self.phase = 0
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)

    def boundingRect(self) -> QRectF:  # noqa: N802
        return QRectF(-18, -18, 36, 36)

    def paint(self, painter: QPainter, _option: object, _widget: object = None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        for index in range(12):
            alpha = 45 + ((index - self.phase) % 12) * 17
            color = QColor(230, 234, 238, min(alpha, 232))
            pen = QPen(color, 2.4)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            angle = radians(index * 30)
            painter.drawLine(
                QPointF(cos(angle) * 9, sin(angle) * 9),
                QPointF(cos(angle) * 15, sin(angle) * 15),
            )

    def advance_frame(self) -> None:
        self.phase = (self.phase + 1) % 12
        self.update()


class RoiViewBox(pg.ViewBox):  # type: ignore[misc]
    """ViewBox reserving Ctrl+drag for ROI and Shift+drag for Line Profile."""

    roi_dragged = Signal(object, bool)
    line_dragged = Signal(object, bool)
    roi_reset_requested = Signal()
    wheel_zoom_started = Signal()
    # Explicit gesture boundary for cancelling an in-flight W04 restore.
    user_navigation_started = Signal()

    def wheelEvent(self, event: Any, axis: int | None = None) -> None:  # noqa: N802
        self.user_navigation_started.emit()
        self.wheel_zoom_started.emit()
        super().wheelEvent(event, axis)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.interaction_mode = "cursor"
        self.preserve_scale_on_resize = True

    def resizeEvent(self, event: QGraphicsSceneResizeEvent) -> None:  # noqa: N802
        old_size = event.oldSize()
        preserve = (
            self.preserve_scale_on_resize
            and old_size.width() > 0
            and old_size.height() > 0
            and event.newSize().width() > 0
            and event.newSize().height() > 0
        )
        if not preserve:
            super().resizeEvent(event)
            return

        ranges = self.viewRange()
        center_x = (float(ranges[0][0]) + float(ranges[0][1])) / 2.0
        center_y = (float(ranges[1][0]) + float(ranges[1][1])) / 2.0
        pixel_scale = max(
            (float(ranges[0][1]) - float(ranges[0][0])) / old_size.width(),
            (float(ranges[1][1]) - float(ranges[1][0])) / old_size.height(),
        )

        # ViewBox normally expands its visible range to retain the whole target
        # range while resizing. Suppress that transient notification and expose
        # only the final, constant-pixel-scale range to synchronized viewers.
        blocker = QSignalBlocker(self)
        super().resizeEvent(event)
        del blocker
        half_width = pixel_scale * event.newSize().width() / 2.0
        half_height = pixel_scale * event.newSize().height() / 2.0
        self.setRange(
            xRange=(center_x - half_width, center_x + half_width),
            yRange=(center_y - half_height, center_y + half_height),
            padding=0,
        )

    @staticmethod
    def gesture_for_modifiers(modifiers: Qt.KeyboardModifier) -> str | None:
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            return "roi"
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            return "line"
        return None

    def mouseDragEvent(self, event: Any, axis: int | None = None) -> None:  # noqa: N802
        if event.isStart():
            self.user_navigation_started.emit()
        gesture = self.gesture_for_modifiers(event.modifiers())
        if event.button() == Qt.MouseButton.LeftButton and gesture == "roi":
            start = self.mapSceneToView(event.buttonDownScenePos())
            end = self.mapSceneToView(event.scenePos())
            self.roi_dragged.emit((start, end), bool(event.isFinish()))
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton and gesture == "line":
            start = self.mapSceneToView(event.buttonDownScenePos())
            end = self.mapSceneToView(event.scenePos())
            self.line_dragged.emit((start, end), bool(event.isFinish()))
            event.accept()
            return
        super().mouseDragEvent(event, axis)

    def mouseClickEvent(self, event: Any) -> None:
        if event.button() == Qt.MouseButton.LeftButton and event.double():
            self.user_navigation_started.emit()
            self.roi_reset_requested.emit()
            event.accept()
            return
        super().mouseClickEvent(event)


class TracedGraphicsLayoutWidget(pg.GraphicsLayoutWidget):  # type: ignore[misc]
    """Time the actual QGraphicsView paint, not the next Qt timer callback."""

    def __init__(self) -> None:
        super().__init__()
        self.trace_document_id: str | None = None

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        document_id = self.trace_document_id
        if document_id is None or not load_latency_trace.tracks(document_id):
            super().paintEvent(event)
            return
        trace = load_latency_trace.PhaseTimer("viewport.graphics_paint", document_id=document_id)
        load_latency_trace.mark("viewport_graphics_paint_begin", document_id=document_id, once=True)
        try:
            super().paintEvent(event)
        finally:
            trace.checkpoint("graphics_view_paint_returned")
            load_latency_trace.mark(
                "viewport_graphics_paint_returned", document_id=document_id, once=True
            )


class ImageViewer(QWidget):
    """pyqtgraph image canvas with zoom/pan, pixel readout, and shared ROI overlay."""

    cursor_moved = Signal(int, int, object)
    roi_changed = Signal(object)
    roi_cleared = Signal()
    line_changed = Signal(object)
    line_cleared = Signal()
    activated = Signal(object)
    focus_requested = Signal(object)
    navigation_requested = Signal(str)
    zoom_changed = Signal(float)
    document_changed = Signal(object)
    first_frame_painted = Signal(str)
    geometry_settled = Signal()
    display_preview_settled = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ImageViewer")
        self._document: ImageDocument | None = None
        self._pending_document: ImageDocument | None = None
        self._displayed_preview: object | None = None
        self._displayed_gain: float | None = None
        self._display_preview_worker: TaskWorker | None = None
        self._display_preview_request_serial = 0
        self._display_preview_request_identity: tuple[int, int, int, int, float] | None = None
        self._graphics_resources_disposed = False
        self._paint_notified_identity: tuple[str, int, int] | None = None
        self._paint_pending_identity: tuple[str, int, int] | None = None
        self._display_gain_state = display_gain_state()
        self._display_gain_state.gain_changed.connect(self._display_gain_changed)
        self._slot = 1
        self._role = ""
        self._cursor_enabled = True
        self._active = False
        self.header = TileHeader()
        self.header.focus_requested.connect(lambda: self.focus_requested.emit(self))
        self.header.navigation_requested.connect(self.navigation_requested)
        self._graphics = TracedGraphicsLayoutWidget()
        self._physical_zoom_target: float | None = None
        self._last_valid_physical_zoom: float | None = None
        self._screen_recalibration_target: float | None = None
        self._fit_mode = False
        self._watched_window: Any = None
        self._geometry_timer = QTimer(self)
        self._geometry_timer.setSingleShot(True)
        self._geometry_timer.timeout.connect(self._settle_physical_zoom)  # type: ignore[attr-defined]
        self._graphics.viewport().installEventFilter(self)
        self.view_box = RoiViewBox(lockAspect=True, enableMenu=False)
        self._graphics.addItem(self.view_box)
        self.view_box.setMouseMode(pg.ViewBox.PanMode)
        self.view_box.invertY(True)
        self.image_item = pg.ImageItem(axisOrder="row-major")
        # Spatially expanded native planes must retain discrete sample/cell
        # presentation. Pyqtgraph's downsampling path can blend neighboring
        # samples, so keep it explicitly disabled for this correctness view.
        self.image_item.setOpts(autoDownsample=False)
        self.view_box.addItem(self.image_item)
        self._loading_item = LoadingSpinnerItem()
        self._loading_item.setZValue(100)
        self._loading_item.hide()
        self.view_box.addItem(self._loading_item, ignoreBounds=True)
        self._loading_timer = QTimer(self)
        self._loading_timer.setInterval(80)
        self._loading_timer.timeout.connect(self._loading_item.advance_frame)  # type: ignore[attr-defined]
        # ROI interaction is owned by RoiViewBox; this item is presentation-only.
        # Avoid pg.RectROI here because it creates an unused scale Handle and a
        # parentless QMenu, leaving a cyclic PySide/pyqtgraph object graph for
        # Python GC after each ImageViewer teardown.
        self._roi = QGraphicsRectItem()
        self._roi.setPen(pg.mkPen("#ffd54f", width=2))
        self._roi.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self._roi.setZValue(20)
        self._roi.hide()
        self._roi_enabled = False
        self.view_box.addItem(self._roi)
        self._memo_regions: tuple[tuple[str, RoiBounds, bool], ...] = ()
        self._memo_items: list[tuple[QGraphicsRectItem, pg.TextItem]] = []
        self._line_selection: LineSelection | None = None
        self._line_item = pg.PlotCurveItem(
            pen=pg.mkPen("#00e5ff", width=2),
            symbol="o",
            symbolSize=7,
            symbolBrush=pg.mkBrush("#00e5ff"),
            symbolPen=pg.mkPen("#002b36", width=1),
        )
        self._line_item.setZValue(21)
        self._line_item.hide()
        self.view_box.addItem(self._line_item)
        cursor_color = QColor("#f7d154")
        cursor_color.setAlpha(150)
        self._vertical_cursor = pg.InfiniteLine(
            angle=90, movable=False, pen=pg.mkPen(cursor_color, width=1)
        )
        self._horizontal_cursor = pg.InfiniteLine(
            angle=0, movable=False, pen=pg.mkPen(cursor_color, width=1)
        )
        self._vertical_cursor.hide()
        self._horizontal_cursor.hide()
        self.view_box.addItem(self._vertical_cursor)
        self.view_box.addItem(self._horizontal_cursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(self._graphics, 1)
        self._graphics.scene().sigMouseMoved.connect(self._on_scene_mouse_moved)
        self.view_box.roi_dragged.connect(self._on_roi_dragged)
        self.view_box.line_dragged.connect(self._on_line_dragged)
        self.view_box.roi_reset_requested.connect(self._reset_overlays)
        self.view_box.sigRangeChanged.connect(self._update_zoom)
        self.view_box.sigRangeChanged.connect(self._position_loading_item)
        self.view_box.wheel_zoom_started.connect(self._clear_physical_target)
        self.set_active(False)

    @property
    def document(self) -> ImageDocument | None:
        return self._document

    @property
    def presented_document(self) -> ImageDocument | None:
        return self._pending_document or self._document

    def set_header(self, text: str) -> None:
        self.header.set_document(
            self._pending_document or self._document,
            slot=self._slot,
            role=self._role,
            compat_text=text,
        )

    def set_tile_context(self, slot: int, role: str = "") -> None:
        self._slot = slot
        self._role = role
        self.header.set_document(
            self._pending_document or self._document,
            slot=slot,
            role=role,
            compat_text=self.header.text(),
        )

    def set_active(self, active: bool) -> None:
        style = tile_style(active)
        if self._active == active and self.styleSheet() == style:
            return
        self._active = active
        self.setStyleSheet(style)
        cursor_color = QColor("#f7d154")
        cursor_color.setAlpha(150 if active else 55)
        pen = pg.mkPen(cursor_color, width=1)
        self._vertical_cursor.setPen(pen)
        self._horizontal_cursor.setPen(pen)

    def set_focus(self, focused: bool) -> None:
        self.header.set_focus(focused)

    def set_focus_control_visible(self, visible: bool) -> None:
        self.header.set_focus_control_visible(visible)

    def set_navigation_items(
        self,
        items: list[tuple[str, str, str]],
        current_key: str,
    ) -> None:
        self.header.set_navigation_items(items, current_key)

    def _device_pixel_ratio(self) -> float:
        return float(self._graphics.viewport().devicePixelRatioF())

    def _reference_to_viewport(self, x: float, y: float) -> QPointF | None:
        """Map canonical reference geometry through the displayed ImageItem.

        The prescribed presentation rectangle supplies reference→item-local
        sampling. ImageItem.mapToScene and QGraphicsView.viewportTransform then
        incorporate *actual* item/view transforms (including non-unit scaling).
        """
        document = self._document
        if document is None or document.preview is None:
            return None
        reference_rect = self._presentation_rect(document)
        item_rect = self.image_item.boundingRect()
        if (
            reference_rect.width() <= 0
            or reference_rect.height() <= 0
            or item_rect.width() <= 0
            or item_rect.height() <= 0
        ):
            return None
        local = QPointF(
            item_rect.left()
            + (x - reference_rect.left()) * item_rect.width() / reference_rect.width(),
            item_rect.top()
            + (y - reference_rect.top()) * item_rect.height() / reference_rect.height(),
        )
        return cast(
            QPointF,
            self._graphics.viewportTransform().map(self.image_item.mapToScene(local)),
        )

    def measure_physical_zoom(self) -> PhysicalZoomMeasurement:
        """Actual screen physical-pixel scale of one reference-space pixel."""
        dpr = self._device_pixel_ratio()
        if (
            self._graphics_resources_disposed
            or self._document is None
            or self._document.preview is None
            or self.view_box.width() <= 0
            or self.view_box.height() <= 0
        ):
            return PhysicalZoomMeasurement(dpr=dpr)
        # ViewBox defers its child transform until paint or a mapping helper.
        # Direct ImageItem.mapToScene() must see the current range even inside
        # sigRangeChanged and between synchronous zoom correction passes.
        self.view_box.updateMatrix()
        rows, columns = self._reference_shape(self._document)
        center_x, center_y = columns / 2.0, rows / 2.0
        p = self._reference_to_viewport(center_x, center_y)
        px = self._reference_to_viewport(center_x + 1.0, center_y)
        py = self._reference_to_viewport(center_x, center_y + 1.0)
        if p is None or px is None or py is None:
            return PhysicalZoomMeasurement(dpr=dpr)
        return measure_basis(
            (p.x(), p.y()),
            (px.x(), px.y()),
            (py.x(), py.y()),
            dpr,
        )

    @property
    def zoom_percent(self) -> float | None:
        return self.measure_physical_zoom().percent

    def set_physical_zoom(
        self,
        percent: float,
        center_ref: tuple[float, float] | None = None,
        *,
        track_target: bool = True,
    ) -> ZoomApplyResult:
        """Set exact physical zoom by correcting the measured displayed mapping.

        Two bounded synchronous correction passes use the *effective* ViewBox
        ranges, rather than the outer graphics viewport or the image bounds.
        A later viewport/layout event re-applies an explicitly requested target.
        """
        if not isfinite(percent) or percent <= 0:
            raise ValueError("physical zoom must be a positive finite percentage")
        self._fit_mode = False
        if track_target:
            self._physical_zoom_target = percent
        elif (
            self._physical_zoom_target is not None
            and abs(self._physical_zoom_target - percent) > 1e-6
        ):
            self._physical_zoom_target = None
        self._screen_recalibration_target = None
        measurement = self.measure_physical_zoom()
        target = percent / 100.0
        if not measurement.valid:
            self._update_zoom()
            return ZoomApplyResult(percent, measurement, False, 0)
        x_range, y_range = self.view_box.viewRange()
        center_x, center_y = (
            ((x_range[0] + x_range[1]) / 2, (y_range[0] + y_range[1]) / 2)
            if center_ref is None
            else center_ref
        )
        if not all(isfinite(value) for value in (center_x, center_y)):
            raise ValueError("physical zoom center must be finite")
        passes = 0
        for _ in range(2):
            ranges = self.view_box.viewRange()
            actual_center = (
                (ranges[0][0] + ranges[0][1]) / 2.0,
                (ranges[1][0] + ranges[1][1]) / 2.0,
            )
            scale_ok = (
                measurement.valid
                and abs(measurement.scale_x - target) <= target * 0.005
                and abs(measurement.scale_y - target) <= target * 0.005
            )
            # Sync must update the center even if the other tile already has
            # the requested scale (e.g. an ordinary pan at exact 100%).
            center_ok = (
                abs(actual_center[0] - center_x) <= 1e-6
                and abs(actual_center[1] - center_y) <= 1e-6
            )
            if scale_ok and center_ok:
                break
            width = (ranges[0][1] - ranges[0][0]) * measurement.scale_x / target
            height = (ranges[1][1] - ranges[1][0]) * measurement.scale_y / target
            if not all(isfinite(v) and v > 0 for v in (width, height)):
                break
            self.view_box.setRange(
                xRange=(center_x - width / 2.0, center_x + width / 2.0),
                yRange=(center_y - height / 2.0, center_y + height / 2.0),
                padding=0,
            )
            passes += 1
            measurement = self.measure_physical_zoom()
            if not measurement.valid:
                break
        final_ranges = self.view_box.viewRange()
        center_error_x = abs((final_ranges[0][0] + final_ranges[0][1]) / 2.0 - center_x)
        center_error_y = abs((final_ranges[1][0] + final_ranges[1][1]) / 2.0 - center_y)
        achieved = (
            measurement.valid
            and abs(measurement.scale_x - target) <= target * 0.005
            and abs(measurement.scale_y - target) <= target * 0.005
            and center_error_x * target <= 0.5
            and center_error_y * target <= 0.5
        )
        self._update_zoom()
        return ZoomApplyResult(percent, measurement, achieved, passes)

    def _clear_physical_target(self) -> None:
        self._physical_zoom_target = None
        self._fit_mode = False

    def _watch_screen_signal(self) -> None:
        window = self.window().windowHandle()
        if window is self._watched_window:
            return
        if self._watched_window is not None:
            with suppress(RuntimeError, TypeError):
                self._watched_window.screenChanged.disconnect(self._on_screen_changed)
        self._watched_window = window
        if window is not None:
            window.screenChanged.connect(self._on_screen_changed)  # type: ignore[attr-defined]

    def _on_screen_changed(self, _screen: object) -> None:
        if not self._fit_mode and self._physical_zoom_target is None:
            self._screen_recalibration_target = self._last_valid_physical_zoom
        self._geometry_timer.start(0)

    def _settle_physical_zoom(self) -> None:
        if self._graphics_resources_disposed:
            return
        if self._document is None or self._document.preview is None:
            return
        target = self._physical_zoom_target
        explicit_target = target is not None
        if target is None:
            target = self._screen_recalibration_target
        if target is not None and self.view_box.width() > 0 and self.view_box.height() > 0:
            self.set_physical_zoom(target, track_target=explicit_target)
        else:
            self._update_zoom()
        self.geometry_settled.emit()

    def set_document(self, document: ImageDocument | None, fit: bool = True) -> None:
        self._graphics.trace_document_id = (
            document.document_id if document is not None and document.preview is not None else None
        )
        view_trace = load_latency_trace.PhaseTimer(
            "viewer.set_document", document_id=document.document_id if document else None
        )
        previous = self._document
        if document is not previous:
            self.set_memo_regions(())
        if document is None:
            self._cancel_display_preview()
            self._document = None
            self._pending_document = None
            self._displayed_preview = None
            self._displayed_gain = None
            self.image_item.clear()
            self.image_item.setRect()
            self._physical_zoom_target = None
            self._last_valid_physical_zoom = None
            self._loading_item.hide()
            self._loading_timer.stop()
            self.header.clear()
            self.hide_cursor()
            self._roi.hide()
            self._line_item.hide()
            self.header.set_document(None, self._slot, self._role)
            self.document_changed.emit(None)
            return
        if document.preview is None:
            self._cancel_display_preview()
            self._pending_document = document
            clear_previous = document.channel_layout.startswith("CHANNEL_")
            if clear_previous or previous is None or previous.preview is None:
                self._document = None
                self.image_item.clear()
                self.image_item.setRect()
                self._displayed_preview = None
                self._displayed_gain = None
            self._position_loading_item()
            self._loading_item.setVisible(document.loading_state != "error")
            if document.loading_state != "error":
                self._loading_timer.start()
            else:
                self._loading_timer.stop()
            self.header.set_document(document, self._slot, self._role, self.header.text())
            self.document_changed.emit(document)
            view_trace.checkpoint("loading_placeholder_and_header")
            return

        gain_capable = is_display_gain_capable(document)
        desired_gain = self._display_gain_state.gain if gain_capable else None
        reuse_display_preview = (
            previous is document
            and desired_gain is not None
            and self._displayed_gain == desired_gain
            and self._displayed_preview is not None
        )
        preview_changed = (
            not reuse_display_preview and self._displayed_preview is not document.preview
        )
        self._document = document
        self._pending_document = None
        self._loading_item.hide()
        self._loading_timer.stop()
        if preview_changed:
            self._upload_preview(document.preview, document)
            self._displayed_preview = document.preview
            self._displayed_gain = 1.0 if gain_capable else None
        else:
            # A document can retain the same native preview while its
            # presentation mapping changes (for example derived -> identity).
            # Geometry is semantic metadata, so refresh it even without an
            # ndarray upload.
            self.image_item.setRect(self._presentation_rect(document))
        view_trace.checkpoint("image_item_bind_or_geometry")
        self.header.set_document(
            document,
            self._slot,
            self._role,
            self.header.text(),
        )
        if preview_changed and (fit or previous is None or previous.preview is None):
            self.fit_image()
        view_trace.checkpoint("fit_and_header")
        self.document_changed.emit(document)
        self._update_zoom()
        self._ensure_display_preview()
        view_trace.checkpoint("document_signals_and_gain")

    def _display_gain_changed(self, _gain: float) -> None:
        self._ensure_display_preview()

    @staticmethod
    def _reference_shape(document: ImageDocument) -> tuple[int, int]:
        """Return the reference (rows, columns) interaction extent.

        The fallback keeps this widget usable with pre-spatial documents while
        the transient reference-space metadata is absent during loading.
        """

        shape = getattr(document, "reference_shape", None)
        if shape is not None:
            return int(shape[0]), int(shape[1])
        preview = document.preview
        if preview is not None:
            return int(preview.shape[0]), int(preview.shape[1])
        source = document.source
        if source is not None:
            return int(source.shape[0]), int(source.shape[1])
        return 0, 0

    @staticmethod
    def _presentation_rect(document: ImageDocument) -> QRectF:
        sampling = getattr(document, "spatial_sampling", None)
        if sampling is not None:
            presentation_rect = sampling.presentation_rect
            rect = presentation_rect() if callable(presentation_rect) else presentation_rect
            return QRectF(float(rect[0]), float(rect[1]), float(rect[2]), float(rect[3]))
        preview = document.preview
        if preview is None:
            return QRectF()
        return QRectF(0.0, 0.0, float(preview.shape[1]), float(preview.shape[0]))

    def _upload_preview(self, preview: Any, document: ImageDocument) -> None:
        """Upload a native preview and bind its display geometry atomically."""

        upload_trace = load_latency_trace.PhaseTimer(
            "viewer.upload", document_id=document.document_id
        )
        # Previews already contain final display codes. Explicit identity levels
        # make pyqtgraph rescale every RGB pixel again during GUI-thread paint.
        self.image_item.setImage(preview, autoLevels=False, levels=None)
        upload_trace.checkpoint("pyqtgraph_setImage_returned")
        self.image_item.setRect(self._presentation_rect(document))
        upload_trace.checkpoint("setRect_returned")
        load_latency_trace.mark("image_item_upload_returned", document_id=document.document_id)

    def _ensure_display_preview(self) -> None:
        document = self._document
        if document is None or document.source is None or document.preview is None:
            self._cancel_display_preview()
            return
        if not is_display_gain_capable(document):
            self._cancel_display_preview()
            self._displayed_gain = None
            return

        gain = self._display_gain_state.gain
        if gain == 1.0:
            self._cancel_display_preview()
            if self._displayed_preview is not document.preview:
                self._upload_preview(document.preview, document)
                self._displayed_preview = document.preview
            self._displayed_gain = 1.0
            return
        if self._displayed_gain == gain:
            return
        if not self.isVisible():
            self._cancel_display_preview()
            return

        source = document.source
        canonical_preview = document.preview
        identity = (id(document), id(source), id(canonical_preview), document.generation, gain)
        if (
            self._display_preview_request_identity == identity
            and self._display_preview_worker is not None
        ):
            return

        self._cancel_display_preview()
        request_serial = self._display_preview_request_serial
        profile = document.raw_profile
        if isinstance(profile, RawProfile):
            worker = TaskWorker(
                render_raw_preview,
                source,
                document_id=document.document_id,
                generation=document.generation,
                channel_layout=document.channel_layout,
                bit_depth=document.bit_depth,
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
                canonical_preview=canonical_preview,
                gain=gain,
            )
        worker.signals.succeeded.connect(
            lambda task_id, document_id, generation, result: self._display_preview_succeeded(
                task_id,
                document_id,
                generation,
                result,
                request_serial=request_serial,
                expected_document=document,
                expected_source=source,
                expected_preview=canonical_preview,
                expected_gain=gain,
            )
        )
        worker.signals.finished.connect(self._display_preview_finished)
        self._display_preview_worker = worker
        self._display_preview_request_identity = identity
        _display_preview_thread_pool().start(worker)

    def _display_preview_succeeded(
        self,
        task_id: str,
        document_id: object,
        generation: int,
        result: object,
        *,
        request_serial: int,
        expected_document: ImageDocument,
        expected_source: Any,
        expected_preview: Any,
        expected_gain: float,
    ) -> None:
        worker = self._display_preview_worker
        document = self._document
        if (
            worker is None
            or worker.task_id != task_id
            or request_serial != self._display_preview_request_serial
            or document is not expected_document
            or document_id != expected_document.document_id
            or generation != expected_document.generation
            or document.source is not expected_source
            or document.preview is not expected_preview
            or self._display_gain_state.gain != expected_gain
            or not self.isVisible()
        ):
            return
        if not isinstance(result, np.ndarray) or result.dtype != np.uint8:
            return
        if not isinstance(expected_preview, np.ndarray) or result.shape != expected_preview.shape:
            return
        self._upload_preview(result, expected_document)
        self._displayed_preview = result
        self._displayed_gain = expected_gain

    def _display_preview_finished(self, task_id: str) -> None:
        worker = self._display_preview_worker
        if worker is not None and worker.task_id == task_id:
            self._display_preview_worker = None
            self._display_preview_request_identity = None
            if not self._graphics_resources_disposed:
                self.display_preview_settled.emit()

    def _cancel_display_preview(self) -> None:
        self._display_preview_request_serial += 1
        worker = self._display_preview_worker
        if worker is not None:
            worker.cancel()
        self._display_preview_worker = None
        self._display_preview_request_identity = None

    def _release_derived_display_preview(self) -> None:
        document = self._document
        if (
            document is None
            or document.preview is None
            or not is_display_gain_capable(document)
            or self._displayed_preview is document.preview
        ):
            return
        self._upload_preview(document.preview, document)
        self._displayed_preview = document.preview
        self._displayed_gain = 1.0

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        self._watch_screen_signal()
        self._geometry_timer.start(0)
        self._ensure_display_preview()

    def hideEvent(self, event: QHideEvent) -> None:  # noqa: N802
        self._cancel_display_preview()
        self._release_derived_display_preview()
        super().hideEvent(event)

    def shutdown(self) -> None:
        """Release pyqtgraph resources at the owning-window lifecycle boundary."""

        self._cancel_display_preview()
        self._loading_timer.stop()
        self._geometry_timer.stop()
        if self._watched_window is not None:
            with suppress(RuntimeError, TypeError):
                self._watched_window.screenChanged.disconnect(self._on_screen_changed)
            self._watched_window = None
        if self._graphics_resources_disposed:
            return
        self.set_memo_regions(())
        self._graphics_resources_disposed = True

        with suppress(RuntimeError, TypeError):
            self._display_gain_state.gain_changed.disconnect(self._display_gain_changed)
        viewport = self._graphics.viewport()
        viewport.removeEventFilter(self)
        with suppress(RuntimeError, TypeError):
            self._graphics.scene().sigMouseMoved.disconnect(self._on_scene_mouse_moved)
        signal_callbacks = (
            (self.view_box.roi_dragged, self._on_roi_dragged),
            (self.view_box.line_dragged, self._on_line_dragged),
            (self.view_box.roi_reset_requested, self._reset_overlays),
            (self.view_box.sigRangeChanged, self._update_zoom),
            (self.view_box.sigRangeChanged, self._position_loading_item),
            (self.view_box.wheel_zoom_started, self._clear_physical_target),
            (self._geometry_timer.timeout, self._settle_physical_zoom),  # type: ignore[attr-defined]
        )
        for signal, callback in signal_callbacks:
            with suppress(RuntimeError, TypeError):
                signal.disconnect(callback)
        self.view_box.close()
        self._graphics.removeItem(self.view_box)
        self._graphics.close()
        self._graphics.deleteLater()

    def _position_loading_item(self, *_args: object) -> None:
        x_range, y_range = self.view_box.viewRange()
        self._loading_item.setPos(
            (x_range[0] + x_range[1]) / 2.0,
            (y_range[0] + y_range[1]) / 2.0,
        )

    def begin_layout_refit(self) -> None:
        """Suspend resize-range restoration until a grid layout has settled."""

        self.view_box.preserve_scale_on_resize = False

    def end_layout_refit(self) -> None:
        self.view_box.preserve_scale_on_resize = True

    def fit_image(self) -> None:
        if self._document is None or self._document.preview is None:
            return
        self._physical_zoom_target = None
        self._fit_mode = True
        height, width = self._reference_shape(self._document)
        self.view_box.setRange(QRectF(0, 0, width, height), padding=0.02)

    def zoom_100_percent(self) -> None:
        if self._document is None or self._document.preview is None:
            return
        height, width = self._reference_shape(self._document)
        self.set_physical_zoom(100.0, (width / 2.0, height / 2.0))

    def fit_roi(self, bounds: RoiBounds) -> None:
        """Frame a reference-space ROI with context via canonical physical zoom."""
        if self._document is None or self._document.preview is None:
            return
        percent = self.measure_physical_zoom().percent
        if percent is None:
            return
        ranges = self.view_box.viewRange()
        range_width = ranges[0][1] - ranges[0][0]
        range_height = ranges[1][1] - ranges[1][0]
        factor = min(range_width / (bounds.width * 1.4), range_height / (bounds.height * 1.4))
        height, width = self._reference_shape(self._document)
        half_width, half_height = range_width / factor / 2, range_height / factor / 2
        # Near image edges shift the context instead of centering on black space.
        center_x = min(max(bounds.x + bounds.width / 2, half_width), width - half_width)
        center_y = min(max(bounds.y + bounds.height / 2, half_height), height - half_height)
        if half_width * 2 >= width:
            center_x = width / 2
        if half_height * 2 >= height:
            center_y = height / 2
        self.set_physical_zoom(percent * factor, (center_x, center_y))

    def zoom_by(self, factor: float) -> None:
        if self._document is not None and factor > 0:
            self._clear_physical_target()
            self.view_box.scaleBy((factor, factor))

    def show_cursor(self, x: int, y: int) -> None:
        self._vertical_cursor.setPos(x + 0.5)
        self._horizontal_cursor.setPos(y + 0.5)
        self._vertical_cursor.show()
        self._horizontal_cursor.show()

    def hide_cursor(self) -> None:
        self._vertical_cursor.hide()
        self._horizontal_cursor.hide()

    def enable_cursor(self, enabled: bool = True) -> None:
        self._cursor_enabled = enabled
        if not enabled:
            self.hide_cursor()

    def set_interaction_mode(self, mode: str) -> None:
        if mode not in ("cursor", "roi", "line"):
            raise ValueError("unsupported interaction mode")
        self.view_box.interaction_mode = mode

    @property
    def roi_enabled(self) -> bool:
        return self._roi_enabled

    def set_memo_regions(self, regions: tuple[tuple[str, RoiBounds, bool], ...]) -> None:
        """Passive reference-space bookmarks; never change the analysis ROI/range."""
        if regions == self._memo_regions:
            return
        for rectangle, label in self._memo_items:
            self.view_box.removeItem(rectangle)
            self.view_box.removeItem(label)
            label.deleteLater()
        self._memo_items.clear()
        self._memo_regions = regions
        for text, bounds, selected in regions:
            rectangle = QGraphicsRectItem(QRectF(bounds.x, bounds.y, bounds.width, bounds.height))
            color = "#ffe08a" if selected else "#86c9d7"
            pen = QPen(QColor(color))
            pen.setCosmetic(True)
            pen.setWidthF(2.0 if selected else 1.0)
            rectangle.setPen(pen)
            rectangle.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            rectangle.setZValue(18)
            label = pg.TextItem(
                text=text, color=color, anchor=(0, 0), fill=pg.mkBrush(21, 27, 34, 225)
            )
            label.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            label.setZValue(22)
            label.setPos(bounds.x, bounds.y)
            self.view_box.addItem(rectangle, ignoreBounds=True)
            self.view_box.addItem(label, ignoreBounds=True)
            self._memo_items.append((rectangle, label))

    def enable_roi(self, enabled: bool = True) -> None:
        self._roi_enabled = enabled
        if not enabled:
            self._roi.hide()

    def set_roi_bounds(self, bounds: RoiBounds | None) -> None:
        document = self._document
        if bounds is None or document is None:
            self._roi_enabled = False
            self._roi.hide()
            return
        clipped = clamp_roi(
            self._reference_shape(document),
            bounds.x,
            bounds.y,
            bounds.width,
            bounds.height,
        )
        self._roi_enabled = True
        self._roi.setRect(
            QRectF(
                float(clipped.x),
                float(clipped.y),
                float(clipped.width),
                float(clipped.height),
            )
        )
        self._roi.show()

    def clear_roi(self) -> None:
        had_roi = self._roi_enabled
        self._roi_enabled = False
        self._roi.hide()
        if had_roi:
            self.roi_cleared.emit()

    def current_roi_bounds(self) -> RoiBounds | None:
        document = self._document
        if not self._roi_enabled or document is None:
            return None
        rect = self._roi.rect()
        left = floor(float(rect.x()))
        top = floor(float(rect.y()))
        right = ceil(float(rect.x() + rect.width()))
        bottom = ceil(float(rect.y() + rect.height()))
        try:
            return clamp_roi(
                self._reference_shape(document),
                left,
                top,
                right - left,
                bottom - top,
            )
        except ValueError:
            return None

    @property
    def line_selection(self) -> LineSelection | None:
        return self._line_selection

    def set_line_selection(self, selection: LineSelection | None) -> None:
        document = self._document
        if selection is None or document is None:
            self._line_selection = None
            self._line_item.hide()
            return
        selected = clamp_line(
            self._reference_shape(document),
            selection.x1,
            selection.y1,
            selection.x2,
            selection.y2,
        )
        self._line_selection = selected
        assert selected.y2 is not None
        self._line_item.setData(
            [selected.x1 + 0.5, selected.x2 + 0.5],
            [selected.y1 + 0.5, selected.y2 + 0.5],
        )
        self._line_item.show()

    def clear_line(self) -> None:
        had_line = self._line_selection is not None
        self._line_selection = None
        self._line_item.hide()
        if had_line:
            self.line_cleared.emit()

    def _reset_overlays(self) -> None:
        self.clear_roi()
        self.clear_line()

    def _on_roi_dragged(self, points: object, finished: bool) -> None:
        document = self._document
        if document is None or not isinstance(points, tuple) or len(points) != 2:
            return
        start, end = points
        if not isinstance(start, QPointF) or not isinstance(end, QPointF):
            return
        left = floor(min(start.x(), end.x()))
        top = floor(min(start.y(), end.y()))
        right = ceil(max(start.x(), end.x()))
        bottom = ceil(max(start.y(), end.y()))
        try:
            bounds = clamp_roi(
                self._reference_shape(document),
                left,
                top,
                right - left,
                bottom - top,
            )
        except ValueError:
            return
        self.set_roi_bounds(bounds)
        if finished:
            self.roi_changed.emit(bounds)

    def _on_line_dragged(self, points: object, finished: bool) -> None:
        document = self._document
        if document is None or not isinstance(points, tuple) or len(points) != 2:
            return
        start, end = points
        if not isinstance(start, QPointF) or not isinstance(end, QPointF):
            return
        try:
            selection = clamp_line(
                self._reference_shape(document),
                floor(start.x()),
                floor(start.y()),
                floor(end.x()),
                floor(end.y()),
            )
        except ValueError:
            return
        self.set_line_selection(selection)
        if finished:
            self.line_changed.emit(selection)

    def _on_scene_mouse_moved(self, position: QPointF | Any) -> None:
        document = self._document
        if document is None or not self._cursor_enabled:
            return
        point = self.view_box.mapSceneToView(position)
        x, y = floor(point.x()), floor(point.y())
        rows, columns = self._reference_shape(document)
        if x < 0 or y < 0 or x >= columns or y >= rows:
            self.hide_cursor()
            return
        lookup_at_reference = getattr(document, "sample_lookup_at_reference", None)
        lookup = (
            lookup_at_reference(x, y) if callable(lookup_at_reference) else document.pixel_at(x, y)
        )
        value = None if lookup is None else getattr(lookup, "value", lookup)
        self.show_cursor(x, y)
        self.cursor_moved.emit(x, y, value)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        sequence: QKeySequence | None = None
        if event.modifiers() == Qt.KeyboardModifier.NoModifier and event.key() == Qt.Key.Key_PageUp:
            sequence = QKeySequence(Qt.Key.Key_PageUp)
        elif (
            event.modifiers() == Qt.KeyboardModifier.NoModifier
            and event.key() == Qt.Key.Key_PageDown
        ):
            sequence = QKeySequence(Qt.Key.Key_PageDown)
        if sequence is not None:
            shortcut = next(
                (
                    item
                    for item in self.window().findChildren(QShortcut)
                    if item.isEnabled() and item.key() == sequence
                ),
                None,
            )
            if shortcut is not None:
                shortcut.activated.emit()
                event.accept()
                return
        super().keyPressEvent(event)

    def _notify_first_frame_painted(self) -> None:
        """Run after viewport paint returns, never during the paint event."""

        identity = self._paint_pending_identity
        self._paint_pending_identity = None
        document = self._document
        if (
            identity is None
            or self._graphics_resources_disposed
            or document is None
            or document.preview is None
            or self._pending_document is not None
            or not self.isVisible()
            or identity != (document.document_id, document.generation, id(document.preview))
        ):
            return
        if self._paint_notified_identity == identity:
            return
        self._paint_notified_identity = identity
        load_latency_trace.mark(
            "first_viewport_paint_event_processed",
            document_id=document.document_id,
            once=True,
        )
        self.first_frame_painted.emit(document.document_id)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched is self._graphics.viewport():
            geometry_events = {QEvent.Type.Resize, QEvent.Type.Show}
            for name in ("DevicePixelRatioChange", "DpiChange", "ScreenChangeInternal"):
                event_kind = getattr(QEvent.Type, name, None)
                if event_kind is not None:
                    geometry_events.add(event_kind)
            if event.type() in geometry_events and not self._graphics_resources_disposed:
                if (
                    event.type() not in (QEvent.Type.Resize, QEvent.Type.Show)
                    and not self._fit_mode
                    and self._physical_zoom_target is None
                ):
                    self._screen_recalibration_target = self._last_valid_physical_zoom
                self._geometry_timer.start(0)
            if event.type() == QEvent.Type.MouseButtonPress:
                self.activated.emit(self)
            elif event.type() == QEvent.Type.Paint:
                document = self._document
                if (
                    document is not None
                    and document.preview is not None
                    and self._pending_document is None
                    and self.isVisible()
                    and not self._graphics_resources_disposed
                ):
                    identity = (
                        document.document_id,
                        document.generation,
                        id(document.preview),
                    )
                    if (
                        identity != self._paint_notified_identity
                        and identity != self._paint_pending_identity
                    ):
                        self._paint_pending_identity = identity
                        load_latency_trace.mark(
                            "viewport_paint_event_entered",
                            document_id=document.document_id,
                            once=True,
                        )
                        QTimer.singleShot(0, self._notify_first_frame_painted)
        return super().eventFilter(watched, event)

    def _update_zoom(self, *_args: object) -> None:
        percent = self.zoom_percent
        self.header.set_zoom(percent)
        if percent is not None:
            self._last_valid_physical_zoom = percent
            self.zoom_changed.emit(percent)
