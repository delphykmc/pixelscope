from __future__ import annotations

from math import ceil, floor
from typing import Any

import pyqtgraph as pg
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineSelection, clamp_line
from pixelscope.core.roi import RoiBounds, clamp_roi


class RoiViewBox(pg.ViewBox):  # type: ignore[misc]
    """ViewBox that reserves Ctrl+left-drag for rectangular ROI creation."""

    roi_dragged = Signal(object, bool)
    line_dragged = Signal(object, bool)
    roi_reset_requested = Signal()

    def mouseDragEvent(self, event: Any, axis: int | None = None) -> None:  # noqa: N802
        if (
            event.button() == Qt.MouseButton.LeftButton
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            start = self.mapSceneToView(event.buttonDownScenePos())
            end = self.mapSceneToView(event.scenePos())
            self.roi_dragged.emit((start, end), bool(event.isFinish()))
            event.accept()
            return
        if (
            event.button() == Qt.MouseButton.LeftButton
            and event.modifiers() & Qt.KeyboardModifier.AltModifier
        ):
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

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._document: ImageDocument | None = None
        self.header = QLabel()
        self.header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.header.setStyleSheet("font-weight: 600; padding: 3px")
        self._graphics = pg.GraphicsLayoutWidget()
        self.view_box = RoiViewBox(lockAspect=True, enableMenu=False)
        self._graphics.addItem(self.view_box)
        self.view_box.setMouseMode(pg.ViewBox.PanMode)
        self.view_box.invertY(True)
        self.image_item = pg.ImageItem(axisOrder="row-major")
        self.view_box.addItem(self.image_item)
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
        self._vertical_cursor = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#f7d154"))
        self._horizontal_cursor = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen("#f7d154"))
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

    @property
    def document(self) -> ImageDocument | None:
        return self._document

    def set_header(self, text: str) -> None:
        self.header.setText(text)

    def set_document(self, document: ImageDocument | None, fit: bool = True) -> None:
        previous = self._document
        self._document = document
        if document is None or document.preview is None:
            self.image_item.clear()
            self.header.clear()
            self.hide_cursor()
            self._roi.hide()
            self._line_item.hide()
            return
        self.image_item.setImage(document.preview, autoLevels=False, levels=(0, 255))
        if fit or previous is None or previous.preview is None:
            self.fit_image()

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

    def show_cursor(self, x: int, y: int) -> None:
        self._vertical_cursor.setPos(x + 0.5)
        self._horizontal_cursor.setPos(y + 0.5)
        self._vertical_cursor.show()
        self._horizontal_cursor.show()

    def hide_cursor(self) -> None:
        self._vertical_cursor.hide()
        self._horizontal_cursor.hide()

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
        selected = clamp_line(document.source.shape, selection.x1, selection.y, selection.x2)
        self._line_selection = selected
        y = selected.y + 0.5
        self._line_item.setData(
            [selected.x1 + 0.5, selected.x2 + 0.5],
            [y, y],
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
            )
        except ValueError:
            return
        self.set_line_selection(selection)
        if finished:
            self.line_changed.emit(selection)

    def _on_scene_mouse_moved(self, position: QPointF | Any) -> None:
        document = self._document
        if document is None or document.source is None:
            return
        point = self.view_box.mapSceneToView(position)
        x, y = int(point.x()), int(point.y())
        value = document.pixel_at(x, y)
        if value is None:
            self.hide_cursor()
            return
        self.show_cursor(x, y)
        self.cursor_moved.emit(x, y, value)
