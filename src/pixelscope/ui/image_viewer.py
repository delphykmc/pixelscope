from __future__ import annotations

from math import ceil, cos, floor, radians, sin
from typing import Any

import pyqtgraph as pg
from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QResizeEvent
from PySide6.QtWidgets import QGraphicsItem, QVBoxLayout, QWidget

from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineSelection, clamp_line
from pixelscope.core.roi import RoiBounds, clamp_roi
from pixelscope.ui.design_tokens import tile_style
from pixelscope.ui.tile_header import TileHeader


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
    """ViewBox that reserves Ctrl+left-drag for rectangular ROI creation."""

    roi_dragged = Signal(object, bool)
    line_dragged = Signal(object, bool)
    roi_reset_requested = Signal()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.interaction_mode = "cursor"

    @staticmethod
    def gesture_for_modifiers(modifiers: Qt.KeyboardModifier) -> str | None:
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            return "roi"
        if modifiers & Qt.KeyboardModifier.AltModifier:
            return "line"
        return None

    def mouseDragEvent(self, event: Any, axis: int | None = None) -> None:  # noqa: N802
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

    def mouseClickEvent(self, event: Any) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and event.double():
            self.roi_reset_requested.emit()
            event.accept()
            return
        super().mouseClickEvent(event)


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

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ImageViewer")
        self._document: ImageDocument | None = None
        self._pending_document: ImageDocument | None = None
        self._displayed_preview: object | None = None
        self._slot = 1
        self._role = ""
        self._cursor_enabled = True
        self._active = False
        self._resize_scale: float | None = None
        self._resize_center: tuple[float, float] | None = None
        self._layout_refit_pending = False
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(40)
        self._resize_timer.timeout.connect(self._restore_scale_after_resize)  # type: ignore[attr-defined]
        self.header = TileHeader()
        self.header.focus_requested.connect(lambda: self.focus_requested.emit(self))
        self.header.navigation_requested.connect(self.navigation_requested)
        self._graphics = pg.GraphicsLayoutWidget()
        self._graphics.viewport().installEventFilter(self)
        self.view_box = RoiViewBox(lockAspect=True, enableMenu=False)
        self._graphics.addItem(self.view_box)
        self.view_box.setMouseMode(pg.ViewBox.PanMode)
        self.view_box.invertY(True)
        self.image_item = pg.ImageItem(axisOrder="row-major")
        self.view_box.addItem(self.image_item)
        self._loading_item = LoadingSpinnerItem()
        self._loading_item.setZValue(100)
        self._loading_item.hide()
        self.view_box.addItem(self._loading_item, ignoreBounds=True)
        self._loading_timer = QTimer(self)
        self._loading_timer.setInterval(80)
        self._loading_timer.timeout.connect(self._loading_item.advance_frame)  # type: ignore[attr-defined]
        self._roi = pg.RectROI(
            (0, 0),
            (1, 1),
            movable=False,
            pen=pg.mkPen("#ffd54f", width=2),
            hoverPen=pg.mkPen("#ffffff", width=2),
        )
        self._roi.setZValue(20)
        self._roi.hide()
        self._roi_enabled = False
        self.view_box.addItem(self._roi)
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
        self.set_active(False)

    @property
    def document(self) -> ImageDocument | None:
        return self._document

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
        self._active = active
        self.setStyleSheet(tile_style(active))
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

    @property
    def zoom_percent(self) -> float | None:
        if self._document is None or self._document.preview is None:
            return None
        pixel_size = self.view_box.viewPixelSize()
        if not pixel_size or pixel_size[0] <= 0:
            return None
        return 100.0 / float(pixel_size[0])

    def set_document(self, document: ImageDocument | None, fit: bool = True) -> None:
        previous = self._document
        if document is None:
            self._document = None
            self._pending_document = None
            self._displayed_preview = None
            self.image_item.clear()
            self._loading_item.hide()
            self._loading_timer.stop()
            self.header.clear()
            self.hide_cursor()
            self._roi.hide()
            self._line_item.hide()
            self.header.set_document(None, self._slot, self._role)
            return
        if document.preview is None:
            self._pending_document = document
            if previous is None or previous.preview is None:
                self._document = None
                self.image_item.clear()
                self._displayed_preview = None
            self._position_loading_item()
            self._loading_item.setVisible(document.loading_state != "error")
            if document.loading_state != "error":
                self._loading_timer.start()
            else:
                self._loading_timer.stop()
            self.header.set_document(document, self._slot, self._role, self.header.text())
            return
        preview_changed = self._displayed_preview is not document.preview
        self._document = document
        self._pending_document = None
        self._loading_item.hide()
        self._loading_timer.stop()
        if preview_changed:
            self.image_item.setImage(document.preview, autoLevels=False, levels=(0, 255))
            self._displayed_preview = document.preview
        self.header.set_document(
            document,
            self._slot,
            self._role,
            self.header.text(),
        )
        if preview_changed and (fit or previous is None or previous.preview is None):
            self.fit_image()

    def _position_loading_item(self, *_args: object) -> None:
        x_range, y_range = self.view_box.viewRange()
        self._loading_item.setPos(
            (x_range[0] + x_range[1]) / 2.0,
            (y_range[0] + y_range[1]) / 2.0,
        )

    def _restore_scale_after_resize(self) -> None:
        scale = self._resize_scale
        center = self._resize_center
        self._resize_scale = None
        self._resize_center = None
        if self._document is None or scale is None or center is None or scale <= 0:
            return
        current_pixel_size = self.view_box.viewPixelSize()
        if not current_pixel_size or current_pixel_size[0] <= 0:
            return
        ratio = scale / float(current_pixel_size[0])
        self.view_box.scaleBy(
            (ratio, ratio),
            center=QPointF(center[0], center[1]),
        )

    def begin_layout_refit(self) -> None:
        """Suspend resize-range restoration until a grid layout has settled."""

        self._layout_refit_pending = True
        self._resize_timer.stop()
        self._resize_scale = None
        self._resize_center = None

    def end_layout_refit(self) -> None:
        self._layout_refit_pending = False
        self._resize_timer.stop()
        self._resize_scale = None
        self._resize_center = None

    def fit_image(self) -> None:
        if self._document is None or self._document.preview is None:
            return
        height, width = self._document.preview.shape[:2]
        self.view_box.setRange(QRectF(0, 0, width, height), padding=0.02)

    def zoom_100_percent(self) -> None:
        if self._document is None or self._document.preview is None:
            return
        height, width = self._document.preview.shape[:2]
        viewport = self._graphics.viewport().size()
        visible_width = min(float(width), float(max(viewport.width(), 1)))
        visible_height = min(float(height), float(max(viewport.height(), 1)))
        center_x, center_y = width / 2.0, height / 2.0
        self.view_box.setRange(
            xRange=(center_x - visible_width / 2, center_x + visible_width / 2),
            yRange=(center_y - visible_height / 2, center_y + visible_height / 2),
            padding=0,
        )

    def zoom_by(self, factor: float) -> None:
        if self._document is not None and factor > 0:
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

    def enable_roi(self, enabled: bool = True) -> None:
        self._roi_enabled = enabled
        if not enabled:
            self._roi.hide()

    def set_roi_bounds(self, bounds: RoiBounds | None) -> None:
        document = self._document
        if bounds is None or document is None or document.source is None:
            self._roi_enabled = False
            self._roi.hide()
            return
        clipped = clamp_roi(
            document.source.shape,
            bounds.x,
            bounds.y,
            bounds.width,
            bounds.height,
        )
        self._roi_enabled = True
        self._roi.setPos((clipped.x, clipped.y))
        self._roi.setSize((clipped.width, clipped.height))
        self._roi.show()

    def clear_roi(self) -> None:
        had_roi = self._roi_enabled
        self._roi_enabled = False
        self._roi.hide()
        if had_roi:
            self.roi_cleared.emit()

    def current_roi_bounds(self) -> RoiBounds | None:
        document = self._document
        if not self._roi_enabled or document is None or document.source is None:
            return None
        position = self._roi.pos()
        size = self._roi.size()
        left = floor(float(position.x()))
        top = floor(float(position.y()))
        right = ceil(float(position.x() + size.x()))
        bottom = ceil(float(position.y() + size.y()))
        try:
            return clamp_roi(
                document.source.shape,
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
        if selection is None or document is None or document.source is None:
            self._line_selection = None
            self._line_item.hide()
            return
        selected = clamp_line(
            document.source.shape,
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
        if (
            document is None
            or document.source is None
            or not isinstance(points, tuple)
            or len(points) != 2
        ):
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
                document.source.shape,
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
        if (
            document is None
            or document.source is None
            or not isinstance(points, tuple)
            or len(points) != 2
        ):
            return
        start, end = points
        if not isinstance(start, QPointF) or not isinstance(end, QPointF):
            return
        try:
            selection = clamp_line(
                document.source.shape,
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
        if document is None or document.source is None or not self._cursor_enabled:
            return
        point = self.view_box.mapSceneToView(position)
        x, y = int(point.x()), int(point.y())
        value = document.pixel_at(x, y)
        if value is None:
            self.hide_cursor()
            return
        self.show_cursor(x, y)
        self.cursor_moved.emit(x, y, value)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched is self._graphics.viewport():
            if event.type() == QEvent.Type.Resize and isinstance(event, QResizeEvent):
                if (
                    not self._layout_refit_pending
                    and self._document is not None
                    and event.oldSize().width() > 0
                ):
                    if self._resize_scale is None:
                        ranges = self.view_box.viewRange()
                        pixel_size = self.view_box.viewPixelSize()
                        self._resize_scale = float(pixel_size[0]) if pixel_size else 0.0
                        self._resize_center = (
                            (ranges[0][0] + ranges[0][1]) / 2.0,
                            (ranges[1][0] + ranges[1][1]) / 2.0,
                        )
                    self._resize_timer.start()
            elif event.type() == QEvent.Type.MouseButtonPress:
                self.activated.emit(self)
        return super().eventFilter(watched, event)

    def _update_zoom(self, *_args: object) -> None:
        percent = self.zoom_percent
        self.header.set_zoom(percent)
        if percent is not None:
            self.zoom_changed.emit(percent)
