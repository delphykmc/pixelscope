"""Downstream-owned, non-modal one-pair IQA Analysis Window.

Pure presentation surface: a private adapter will provide validated AnalysisResult
objects and optional disk Open/Save callbacks. No reference-private implementation,
Base modifications, network access, background worker or inferred metric formula.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PySide6.QtCore import (
    QByteArray,
    QEvent,
    QObject,
    QPoint,
    QRect,
    QRectF,
    QSettings,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QCloseEvent,
    QColor,
    QImage,
    QKeyEvent,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QShowEvent,
    QTransform,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QMainWindow,
    QPushButton,
    QRubberBand,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pixelscope_enterprise.iqa.analysis_model import (
    AnalysisResult,
    AttributeDisplay,
    LoadedAnalysis,
    Roi,
    clipped_cells,
    colorize_spatial_rgba,
    map_polarity_legend,
    roi_statistics,
)

ResultLoader = Callable[[Path], LoadedAnalysis]
ResultSaver = Callable[[AnalysisResult, dict[str, object], Path], None]


@dataclass
class _ResultViewState:
    attribute_id: str
    roi: Roi | None = None
    ranges: dict[str, float] = field(default_factory=dict)
    scale: float | None = None
    center_x: float | None = None
    center_y: float | None = None


class _LinkedView(QGraphicsView):
    """Same source-pixel scene coordinates for A, B and spatial map."""

    navigation_changed = Signal(float, float, float)
    roi_requested = Signal(float, float, float, float)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumSize(180, 160)
        self._muted = False
        self._roi_start: QPoint | None = None
        self._rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self.viewport())
        self._rubber_band.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._normal_cursor = self.viewport().cursor()
        self._fit_scale = 1.0
        app = QApplication.instance()
        if app is not None:
            # Shift must work even when the Inspector/sibling currently has focus.
            app.installEventFilter(self)
        self.horizontalScrollBar().valueChanged.connect(  # type: ignore[attr-defined]
            self._navigation_changed
        )
        self.verticalScrollBar().valueChanged.connect(  # type: ignore[attr-defined]
            self._navigation_changed
        )

    def _navigation_changed(self, _value: int = 0) -> None:
        if self._muted or self.scene() is None:
            return
        center = self.mapToScene(self.viewport().rect().center())
        self.navigation_changed.emit(self.transform().m11(), center.x(), center.y())

    def apply_navigation(self, scale: float, center_x: float, center_y: float) -> None:
        if scale <= 0 or not np.isfinite([scale, center_x, center_y]).all():
            return
        self._muted = True
        self.setTransform(QTransform().scale(scale, scale))
        self.centerOn(center_x, center_y)
        self._muted = False

    def wheelEvent(self, event: QWheelEvent) -> None:
        # Minimum zoom is relative to a *post-layout* fit. A 4K fit can be <0.04.
        delta = event.angleDelta().y()
        if delta == 0:
            event.ignore()
            return
        factor = 1.2 ** (delta / 120.0)
        next_scale = self.transform().m11() * factor
        min_scale = max(min(self._fit_scale, self.transform().m11()) / 16.0, 1e-8)
        if min_scale <= next_scale <= 32.0:
            self.scale(factor, factor)
            self._navigation_changed()
        event.accept()

    def _set_roi_cursor(self, selecting: bool) -> None:
        self.viewport().setCursor(
            Qt.CursorShape.CrossCursor if selecting else self._normal_cursor
        )

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        # An application-level key filter avoids depending on which view or
        # Inspector widget currently owns keyboard focus. No keys are consumed.
        event_type = event.type()
        if isinstance(event, QKeyEvent) and event_type in (
            QEvent.Type.KeyPress,
            QEvent.Type.KeyRelease,
        ):
            if event.key() == Qt.Key.Key_Shift:
                selecting = event_type == QEvent.Type.KeyPress
                if selecting and not self.window().isVisible():
                    selecting = False
                self._set_roi_cursor(selecting)
        elif event_type in (QEvent.Type.WindowDeactivate, QEvent.Type.ApplicationDeactivate):
            if watched is self.window() or watched is QApplication.instance():
                self._set_roi_cursor(False)
                self.cancel_roi_drag()
        elif event_type == QEvent.Type.FocusOut and (
            watched is self or watched is self.viewport()
        ):
            self._set_roi_cursor(False)
        return super().eventFilter(watched, event)

    def cancel_roi_drag(self) -> None:
        """Discard the transient rubber band; invalidate its old screen pixels."""

        old_geometry = self._rubber_band.geometry()
        self._roi_start = None
        self._rubber_band.hide()
        self._rubber_band.setGeometry(QRect())
        if self.viewport().isVisible() and not old_geometry.isNull():
            # QRubberBand is a child widget, not a GraphicsScene item. Without
            # invalidating its old pixels Qt may leave ghost outlines until resize.
            self.viewport().repaint()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            position = event.position().toPoint()
            self._set_roi_cursor(True)
            self._roi_start = position
            self._rubber_band.setGeometry(QRect(position, position))
            self._rubber_band.show()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._roi_start is not None:
            self._rubber_band.setGeometry(
                QRect(self._roi_start, event.position().toPoint()).normalized()
            )
            event.accept()
            return
        self._set_roi_cursor(bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        start = self._roi_start
        if start is not None:
            end = event.position().toPoint()
            self.cancel_roi_drag()
            a = self.mapToScene(start)
            b = self.mapToScene(end)
            left, top = min(a.x(), b.x()), min(a.y(), b.y())
            width, height = abs(a.x() - b.x()), abs(a.y() - b.y())
            if width >= 1 and height >= 1:
                self.roi_requested.emit(left, top, width, height)
            event.accept()
            return
        super().mouseReleaseEvent(event)


def _map_pixmap(attribute: AttributeDisplay, half_range: float) -> QPixmap | None:
    """Construct one safe Qt image from the bounded, vectorized signed grid."""

    rgba = colorize_spatial_rgba(attribute, half_range)
    if rgba is None:
        return None
    height, width, _ = rgba.shape
    # QImage can alias buffers; copy the image before numpy memory is released.
    image = QImage(rgba.tobytes(), width, height, width * 4, QImage.Format.Format_RGBA8888).copy()
    return QPixmap.fromImage(image)


class AnalysisWindow(QMainWindow):
    """One independent, non-modal window; may show with no loaded Result."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("enterpriseIqaAnalysisWindow")
        self.setWindowTitle("IQA Analysis")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.resize(1380, 780)
        self._results: dict[str, AnalysisResult] = {}
        self._states: dict[str, _ResultViewState] = {}
        self._active_id: str | None = None
        self._loader: ResultLoader | None = None
        self._saver: ResultSaver | None = None
        self._switching = False
        self._rendering = False
        self._views: list[_LinkedView] = []
        self._roi_items: list[QGraphicsRectItem] = []
        self._source_result_id: str | None = None
        self._source_pixmaps: tuple[QPixmap | None, QPixmap | None] = (None, None)
        self._fit_pending_result_id: str | None = None
        self._fit_attempts_remaining = 8

        file_menu = self.menuBar().addMenu("File")
        self.open_action = file_menu.addAction("Open Result...")
        self.open_action.setObjectName("enterpriseIqaOpenResult")
        self.open_action.setEnabled(False)  # Enabled only with a genuine on-disk reader.
        self.open_action.triggered.connect(  # type: ignore[attr-defined]
            self._open_from_dialog
        )
        self.save_action = file_menu.addAction("Save Result As...")
        self.save_action.setObjectName("enterpriseIqaSaveResult")
        self.save_action.setEnabled(False)  # Not a fake fixture export.
        self.save_action.triggered.connect(  # type: ignore[attr-defined]
            self._save_from_dialog
        )
        self.export_action = file_menu.addAction("Export...")
        self.export_action.setEnabled(False)  # Separate H4 reporting work.
        view_menu = self.menuBar().addMenu("View")
        self.clear_roi_action = view_menu.addAction("Clear ROI")
        self.clear_roi_action.setObjectName("enterpriseIqaClearRoi")
        # MAIN uses Esc for ROI; also accept Shift+Esc as a documented alias.
        self.clear_roi_action.setShortcuts([QKeySequence("Esc"), QKeySequence("Shift+Esc")])
        self.clear_roi_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        self.clear_roi_action.setEnabled(False)
        self.clear_roi_action.triggered.connect(self._clear_roi)  # type: ignore[attr-defined]

        root_split = QSplitter(Qt.Orientation.Horizontal, self)
        root_split.setObjectName("enterpriseIqaRootSplitter")
        image_split = QSplitter(Qt.Orientation.Horizontal, root_split)
        image_split.setObjectName("enterpriseIqaImageSplitter")
        for title in ("Image A", "Image B", "Relative Spatial Map"):
            wrapper = QWidget(image_split)
            column = QVBoxLayout(wrapper)
            column.setContentsMargins(2, 2, 2, 2)
            caption = QLabel(title, wrapper)
            caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
            column.addWidget(caption)
            view = _LinkedView(wrapper)
            view.setObjectName("enterpriseIqaView" + title.replace(" ", ""))
            view.navigation_changed.connect(
                lambda scale, x, y, source=view: self._sync_views(source, scale, x, y)
            )
            view.roi_requested.connect(self._set_roi)
            column.addWidget(view, 1)
            image_split.addWidget(wrapper)
            self._views.append(view)
        inspector = QWidget(root_split)
        inspector.setObjectName("enterpriseIqaInspector")
        inspector.setMinimumWidth(275)
        inspector_layout = QVBoxLayout(inspector)
        inspector_layout.addWidget(QLabel("Result", inspector))
        self.result_combo = QComboBox(inspector)
        self.result_combo.setObjectName("enterpriseIqaResultSelector")
        self.result_combo.currentIndexChanged.connect(  # type: ignore[attr-defined]
            self._on_result_selected
        )
        inspector_layout.addWidget(self.result_combo)
        inspector_layout.addWidget(QLabel("Attributes · supplied order", inspector))
        self.attribute_table = QTableWidget(0, 3, inspector)
        self.attribute_table.setObjectName("enterpriseIqaAttributes")
        self.attribute_table.setHorizontalHeaderLabels(["Attribute", "Official", "Unit"])
        self.attribute_table.horizontalHeader().setStretchLastSection(True)
        self.attribute_table.verticalHeader().hide()
        self.attribute_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.attribute_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.attribute_table.itemSelectionChanged.connect(  # type: ignore[attr-defined]
            self._on_attribute_selected
        )
        inspector_layout.addWidget(self.attribute_table, 2)
        self.official_label = QLabel("Official pair comparison: —", inspector)
        self.official_label.setWordWrap(True)
        inspector_layout.addWidget(self.official_label)
        self.roi_label = QLabel("ROI: none", inspector)
        self.roi_label.setWordWrap(True)
        inspector_layout.addWidget(self.roi_label)
        self.clear_roi_button = QPushButton("Clear ROI (Esc / Shift+Esc)", inspector)
        self.clear_roi_button.setObjectName("enterpriseIqaClearRoiButton")
        self.clear_roi_button.setEnabled(False)
        self.clear_roi_button.clicked.connect(self._clear_roi)  # type: ignore[attr-defined]
        inspector_layout.addWidget(self.clear_roi_button)
        inspector_layout.addWidget(QLabel("Fixed symmetric map range ±", inspector))
        self.range_editor = QDoubleSpinBox(inspector)
        self.range_editor.setObjectName("enterpriseIqaMapRange")
        self.range_editor.setDecimals(3)
        self.range_editor.setRange(0.001, 1_000_000.0)
        self.range_editor.setEnabled(False)
        self.range_editor.valueChanged.connect(  # type: ignore[attr-defined]
            self._update_range
        )
        inspector_layout.addWidget(self.range_editor)
        self.clamp_label = QLabel("Map: unavailable", inspector)
        self.clamp_label.setWordWrap(True)
        inspector_layout.addWidget(self.clamp_label)
        inspector_layout.addStretch(1)
        root_split.addWidget(image_split)
        root_split.addWidget(inspector)
        root_split.setStretchFactor(0, 3)
        root_split.setStretchFactor(1, 1)
        self.setCentralWidget(root_split)
        self.statusBar().showMessage(
            "Shift+drag selects ROI. Esc or Shift+Esc clears it. Missing RGB is optional."
        )
        self._render_empty()

    @property
    def active_result_id(self) -> str | None:
        return self._active_id

    @property
    def current_roi(self) -> Roi | None:
        state = self._state()
        return state.roi if state is not None else None

    def install_file_handlers(
        self, *, load: ResultLoader | None = None, save: ResultSaver | None = None
    ) -> None:
        """Only verified H2 readers/writers enable on-disk actions."""
        self._loader, self._saver = load, save
        self.open_action.setEnabled(load is not None)
        self.save_action.setEnabled(save is not None and self._active_id is not None)

    @staticmethod
    def _validated_saved_state(result: AnalysisResult, raw: dict[str, object]) -> _ResultViewState:
        """Validate the separate user state before mutating any visible UI."""

        if set(raw) != {"attribute_id", "roi", "ranges", "viewport"}:
            raise ValueError("invalid analysis_state fields")
        ids = {attr.attribute_id for attr in result.attributes}
        attribute_id = raw["attribute_id"]
        if not isinstance(attribute_id, str) or attribute_id not in ids:
            raise ValueError("unknown saved attribute")

        def finite_number(value: object) -> float:
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise ValueError("saved state requires JSON numeric values")
            number = float(value)
            if not np.isfinite(number):
                raise ValueError("non-finite saved state")
            return number

        raw_ranges = raw["ranges"]
        if not isinstance(raw_ranges, dict):
            raise ValueError("invalid saved ranges")
        ranges: dict[str, float] = {}
        for key, value in raw_ranges.items():
            if not isinstance(key, str) or key not in ids:
                raise ValueError("range refers to missing attribute")
            limit = finite_number(value)
            if not 0.001 <= limit <= 1_000_000.0:
                raise ValueError("saved range outside UI limits")
            ranges[key] = limit

        roi: Roi | None = None
        raw_roi = raw["roi"]
        if raw_roi is not None:
            if not isinstance(raw_roi, list) or len(raw_roi) != 4:
                raise ValueError("invalid saved ROI")
            x, y, width, height = (finite_number(item) for item in raw_roi)
            if (
                x < 0
                or y < 0
                or width <= 0
                or height <= 0
                or x + width > result.image_width
                or y + height > result.image_height
            ):
                raise ValueError("saved ROI outside source geometry")
            roi = (x, y, width, height)

        viewport = raw["viewport"]
        if not isinstance(viewport, dict) or set(viewport) != {"scale", "center_x", "center_y"}:
            raise ValueError("invalid saved viewport")
        zoom = viewport["scale"]
        x_center = viewport["center_x"]
        y_center = viewport["center_y"]
        if zoom is None and x_center is None and y_center is None:
            return _ResultViewState(attribute_id, roi, ranges)
        scale = finite_number(zoom)
        center_x = finite_number(x_center)
        center_y = finite_number(y_center)
        if not 1e-8 <= scale <= 32.0:
            raise ValueError("invalid saved zoom")
        # A graphics viewport may be larger than the mapped source image. Qt can
        # legitimately expose an off-image center when scrollbars are clamped.
        # Keep finite, bounded overscan; never accept arbitrary remote coordinates.
        max_x_overscan = max(4.0 * result.image_width, 2048.0)
        max_y_overscan = max(4.0 * result.image_height, 2048.0)
        if not (-max_x_overscan <= center_x <= result.image_width + max_x_overscan):
            raise ValueError("saved view center outside bounded source overscan")
        if not (-max_y_overscan <= center_y <= result.image_height + max_y_overscan):
            raise ValueError("saved view center outside bounded source overscan")
        return _ResultViewState(attribute_id, roi, ranges, scale, center_x, center_y)

    def present_result(
        self, result: AnalysisResult, *, analysis_state: dict[str, object] | None = None
    ) -> None:
        """Explicitly open an immutable result; collisions must not replace its payload."""

        existing = self._results.get(result.result_id)
        if existing is not None and existing is not result:
            raise ValueError("conflicting immutable result ID; open a new ID for new payload")
        state = (
            self._validated_saved_state(result, analysis_state)
            if analysis_state is not None
            else None
        )
        self._remember_navigation()
        for view in self._views:
            view.cancel_roi_drag()
        is_new = existing is None
        if is_new:
            self._results[result.result_id] = result
        if state is not None:
            self._states[result.result_id] = state
        if is_new:
            self.result_combo.addItem(result.result_id, result.result_id)
        if result.result_id not in self._states:
            self._states[result.result_id] = _ResultViewState(result.attributes[0].attribute_id)
        self._active_id = result.result_id
        self.result_combo.blockSignals(True)
        self.result_combo.setCurrentIndex(self.result_combo.findData(result.result_id))
        self.result_combo.blockSignals(False)
        self.setWindowTitle(f"IQA Analysis — {result.result_id}")
        self.save_action.setEnabled(self._saver is not None)
        self._populate_attributes()
        self._render_result()
        self.statusBar().showMessage(
            "Official global and grid-derived ROI values are distinct. "
            "Positive = A better only for oriented metrics."
        )

    def _on_result_selected(self, _index: int) -> None:
        result_id = self.result_combo.currentData()
        if isinstance(result_id, str) and result_id in self._results:
            self.present_result(self._results[result_id])

    def current_analysis_state(self) -> dict[str, object]:
        """JSON-compatible user state, never model-produced measurement data."""
        state = self._state()
        if state is None:
            return {}
        self._remember_navigation()
        return {
            "attribute_id": state.attribute_id,
            "roi": list(state.roi) if state.roi is not None else None,
            "ranges": dict(state.ranges),
            "viewport": {
                "scale": state.scale,
                "center_x": state.center_x,
                "center_y": state.center_y,
            },
        }

    def _state(self) -> _ResultViewState | None:
        return self._states.get(self._active_id) if self._active_id is not None else None

    def _attribute(self) -> AttributeDisplay | None:
        state = self._state()
        if state is None or self._active_id is None:
            return None
        return self._results[self._active_id].attribute(state.attribute_id)

    def _populate_attributes(self) -> None:
        result = self._results[self._active_id]  # type: ignore[index]
        state = self._state()
        self._switching = True
        self.attribute_table.setRowCount(len(result.attributes))
        selected = 0
        for row, attr in enumerate(result.attributes):
            if state is not None and attr.attribute_id == state.attribute_id:
                selected = row
            value = "—" if attr.official_value is None else f"{attr.official_value:+.3f}"
            fields = (f"{attr.group} / {attr.label}", value, attr.unit)
            for col, field_text in enumerate(fields):
                item = QTableWidgetItem(field_text)
                item.setData(Qt.ItemDataRole.UserRole, attr.attribute_id)
                self.attribute_table.setItem(row, col, item)
        self.attribute_table.selectRow(selected)
        self._switching = False

    def _on_attribute_selected(self) -> None:
        if self._switching or self._active_id is None:
            return
        row = self.attribute_table.currentRow()
        if row < 0:
            return
        item = self.attribute_table.item(row, 0)
        state = self._state()
        if item is None or state is None:
            return
        state.attribute_id = str(item.data(Qt.ItemDataRole.UserRole))
        self._render_result()

    def _render_empty(self) -> None:
        for view, name in zip(self._views, ("Image A", "Image B", "Map"), strict=True):
            scene = QGraphicsScene(view)
            scene.addText(f"{name}\nNo result loaded")
            view.setScene(scene)
        self.official_label.setText("Official pair comparison: —")
        self.roi_label.setText("ROI: none")
        self.range_editor.setEnabled(False)
        self.clamp_label.setText("Map: unavailable")

    def _render_result(self) -> None:
        if self._active_id is None:
            self._render_empty()
            return
        result = self._results[self._active_id]
        state = self._state()
        attr = self._attribute()
        if state is None or attr is None:
            return
        limit = state.ranges.get(attr.attribute_id, attr.fixed_range)
        self.range_editor.blockSignals(True)
        self.range_editor.setValue(limit)
        self.range_editor.setEnabled(attr.spatial is not None)
        self.range_editor.blockSignals(False)
        # Decode source RGB once per active pair, not on attribute/range/ROI changes.
        if self._source_result_id != result.result_id:
            images: list[QPixmap | None] = []
            for source in (result.source_a, result.source_b):
                image = QImage(str(source)) if source is not None and source.is_file() else QImage()
                if (
                    image.isNull()
                    or image.width() != result.image_width
                    or image.height() != result.image_height
                ):
                    images.append(None)
                else:
                    images.append(QPixmap.fromImage(image))
            self._source_pixmaps = (images[0], images[1])
            self._source_result_id = result.result_id
        self._rendering = True
        self._roi_items = []
        for i, view in enumerate(self._views):
            view._muted = True
            old_scene = view.scene()
            scene = QGraphicsScene(view)
            scene.setSceneRect(QRectF(0, 0, result.image_width, result.image_height))
            scene.setBackgroundBrush(QColor(29, 32, 36))
            if i < 2:
                pixmap = self._source_pixmaps[i]
                if pixmap is None:
                    note = scene.addText("Source unavailable\nNumeric/spatial analysis retained")
                    note.setDefaultTextColor(QColor(240, 240, 240))
                    note.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
                    note.setPos(result.image_width * 0.03, result.image_height * 0.03)
                else:
                    scene.addPixmap(pixmap)
            else:
                pixmap = _map_pixmap(attr, limit)
                grid = attr.spatial
                if pixmap is None or grid is None:
                    note = scene.addText("Spatial map unavailable")
                    note.setDefaultTextColor(QColor(240, 240, 240))
                    note.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
                else:
                    item = scene.addPixmap(pixmap)
                    item.setPos(grid.origin_x, grid.origin_y)
                    item.setTransformationMode(Qt.TransformationMode.FastTransformation)
                    item.setTransform(QTransform().scale(grid.block_width, grid.block_height))
            roi_pen = QPen(QColor(255, 205, 0), 2)
            roi_pen.setCosmetic(True)  # Two visible display pixels, even on fitted 4K imagery.
            overlay = scene.addRect(QRectF(), roi_pen)
            overlay.setZValue(100)
            overlay.setVisible(False)
            self._roi_items.append(overlay)
            view.setScene(scene)
            if old_scene is not None:
                old_scene.deleteLater()
        self._rendering = False
        for view in self._views:
            view._muted = False
        self._draw_roi(state.roi)
        if state.scale is not None and state.center_x is not None and state.center_y is not None:
            self._fit_pending_result_id = None
            for view in self._views:
                view.apply_navigation(state.scale, state.center_x, state.center_y)
        else:
            self._fit_attempts_remaining = 8
            # QWidget/Splitter viewport sizes are not valid before the first show.
            # A pre-show fit can produce a microscopic scale and disable wheel UX.
            self._fit_pending_result_id = result.result_id
            self._queue_initial_fit()
        self._render_inspector(attr, limit)

    def _render_inspector(self, attr: AttributeDisplay, limit: float) -> None:
        if attr.official_value is None:
            text = attr.official_availability.upper() + " (not zero)"
        else:
            text = f"{attr.official_value:+.4f} {attr.unit} ({attr.official_availability})"
        orientation = "+A / −B quality" if attr.quality_oriented else "neutral / no winner inferred"
        self.official_label.setText(f"OFFICIAL full-pair: {text}\n{orientation}")
        roi = self.current_roi
        if roi is None:
            self.roi_label.setText("ROI: none · Shift+drag to inspect · Esc clears")
        else:
            x, y, width, height = roi
            description = (
                f"ROI source (x, y, w, h): ({x:.1f}, {y:.1f}, "
                f"{width:.1f}, {height:.1f}) px\n"
                f"Selected source area: {width * height:,.1f} px²"
            )
            if attr.spatial is None:
                self.roi_label.setText(
                    description + "\\nGRID-DERIVED spatial statistics unavailable"
                )
            else:
                stats = roi_statistics(attr.spatial, roi)
                value = "missing" if stats.mean is None else f"{stats.mean:+.4f} {attr.unit}"
                self.roi_label.setText(
                    f"{description}\\nGRID-DERIVED ROI mean: {value} (NOT official)\\n"
                    f"Grid valid area: {stats.valid_area:,.1f} / "
                    f"{stats.roi_area:,.1f} px² ({stats.valid_coverage:.1%} coverage)"
                )
        if attr.spatial is None:
            self.clamp_label.setText("Map missing (not zero)")
        else:
            clipped, total = clipped_cells(attr.spatial, limit)
            pct = 0.0 if total == 0 else (clipped / total)
            self.clamp_label.setText(
                f"Map scale: −{limit:g} to +{limit:g} {attr.unit}\n"
                f"{map_polarity_legend(attr)}\n"
                f"Clamped: {clipped}/{total} valid cells ({pct:.1%})"
            )

    def _draw_roi(self, roi: Roi | None) -> None:
        """Replace the one live overlay/view and repaint its transient old pixels.

        Qt may retain the old rubber-band/graphics dirty region until a resize.
        Synchronously repaint only on ROI changes (not every pan/zoom/frame).
        """

        rect = QRectF(*roi) if roi is not None else QRectF()
        attr = self._attribute()
        for i, (view, overlay) in enumerate(zip(self._views, self._roi_items, strict=True)):
            # A missing RGB source has no image to spatially annotate. The
            # source-pixel ROI still exists; show it on a populated map only.
            has_image = (
                self._source_pixmaps[i] is not None
                if i < 2
                else attr is not None and attr.spatial is not None
            )
            overlay.setVisible(False)
            overlay.setRect(rect)
            overlay.setVisible(roi is not None and has_image)
            if view.viewport().isVisible():
                view.viewport().repaint()
        enabled = roi is not None
        self.clear_roi_action.setEnabled(enabled)
        self.clear_roi_button.setEnabled(enabled)

    def _clear_roi(self) -> None:
        """Cancel the draft selection and clear only the active result's ROI."""

        for view in self._views:
            view.cancel_roi_drag()
        state = self._state()
        if state is not None:
            state.roi = None
        self._draw_roi(None)
        attr = self._attribute()
        if attr is not None and state is not None:
            self._render_inspector(attr, state.ranges.get(attr.attribute_id, attr.fixed_range))


    def _set_roi(self, x: float, y: float, w: float, h: float) -> None:
        if self._active_id is None:
            return
        result = self._results[self._active_id]
        left = max(0.0, min(x, float(result.image_width)))
        top = max(0.0, min(y, float(result.image_height)))
        right = max(left, min(x + w, float(result.image_width)))
        bottom = max(top, min(y + h, float(result.image_height)))
        if right <= left or bottom <= top:
            return
        state = self._state()
        if state is None:
            return
        state.roi = (left, top, right - left, bottom - top)
        self._draw_roi(state.roi)
        attr = self._attribute()
        if attr is not None:
            self._render_inspector(attr, state.ranges.get(attr.attribute_id, attr.fixed_range))

    def _update_range(self, value: float) -> None:
        state = self._state()
        attr = self._attribute()
        if state is None or attr is None or value <= 0:
            return
        state.ranges[attr.attribute_id] = value
        self._render_result()

    def _sync_views(self, source: _LinkedView, scale: float, x: float, y: float) -> None:
        state = self._state()
        if state is None or self._rendering or self._fit_pending_result_id == self._active_id:
            return
        state.scale, state.center_x, state.center_y = scale, x, y
        for other in self._views:
            if other is not source:
                other.apply_navigation(scale, x, y)

    def _remember_navigation(self) -> None:
        state = self._state()
        if (
            state is None
            or state.scale is not None
            or not self.isVisible()
            or self._fit_pending_result_id == self._active_id
        ):
            return
        view = self._views[0]
        center = view.mapToScene(view.viewport().rect().center())
        state.scale, state.center_x, state.center_y = view.transform().m11(), center.x(), center.y()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._queue_initial_fit()

    def _queue_initial_fit(self) -> None:
        if self.isVisible() and self._fit_pending_result_id is not None:
            # Defer until Qt has assigned real splitter/viewport dimensions.
            QTimer.singleShot(0, self._finish_initial_fit)

    def _finish_initial_fit(self) -> None:
        result_id = self._fit_pending_result_id
        if not self.isVisible() or result_id is None or result_id != self._active_id:
            return
        if any(
            view.viewport().width() < 100 or view.viewport().height() < 100 for view in self._views
        ):
            # The compositor/splitter may deliver child geometry in a later event.
            # Bounded retries; never cache a pre-layout transform or spin forever.
            if self._fit_attempts_remaining > 0:
                self._fit_attempts_remaining -= 1
                QTimer.singleShot(25, self._finish_initial_fit)
            return
        state = self._state()
        if state is None or state.scale is not None:
            self._fit_pending_result_id = None
            return
        result = self._results[result_id]
        self._rendering = True
        for view in self._views:
            view._muted = True
        try:
            first = self._views[0]
            first.fitInView(first.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
            scale = first.transform().m11()
            if not np.isfinite(scale) or scale <= 0:
                return
            # Use the scene's canonical center, not a pre-layout mapToScene
            # coordinate (which can legitimately fall outside the image).
            center_x, center_y = result.image_width / 2.0, result.image_height / 2.0
            state.scale, state.center_x, state.center_y = scale, center_x, center_y
            for view in self._views:
                view._fit_scale = scale
                view.apply_navigation(scale, center_x, center_y)
            self._fit_pending_result_id = None
        finally:
            for view in self._views:
                view._muted = False
            self._rendering = False

    def _open_from_dialog(self) -> None:
        if self._loader is None:
            return
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open saved IQA result", "", "Saved results (*)"
        )
        if not filename:
            return
        try:
            loaded = self._loader(Path(filename))
            if not isinstance(loaded, LoadedAnalysis):
                raise ValueError("reader must return a verified LoadedAnalysis")
            self.present_result(loaded.result, analysis_state=loaded.analysis_state)
        except (OSError, ValueError):
            self.statusBar().showMessage("Result could not be opened or validated.")

    def _save_from_dialog(self) -> None:
        if self._saver is None or self._active_id is None:
            return
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save portable IQA result", "", "Saved results (*)"
        )
        if not filename:
            return
        try:
            self._saver(
                self._results[self._active_id], self.current_analysis_state(), Path(filename)
            )
        except (OSError, ValueError):
            self.statusBar().showMessage("Result could not be saved.")
            return
        self.statusBar().showMessage("Portable result saved by installed writer.")

    def closeEvent(self, event: QCloseEvent) -> None:
        # Closing the analysis window must not cancel jobs or change the host Viewer.
        for view in self._views:
            view.cancel_roi_drag()
            view._set_roi_cursor(False)
        self._remember_navigation()
        QSettings("PixelScope", "EnterpriseIqa").setValue(
            "analysis_window_geometry", self.saveGeometry()
        )
        super().closeEvent(event)


class AnalysisWindowManager:
    """Own exactly one independent AnalysisWindow; no Base or worker ownership."""

    def __init__(self) -> None:
        self._window: AnalysisWindow | None = None
        self._closed = False

    @property
    def window(self) -> AnalysisWindow | None:
        return self._window

    def show(self, result: AnalysisResult | None = None) -> AnalysisWindow:
        if self._closed:
            raise RuntimeError("analysis manager is shut down")
        if self._window is None:
            self._window = AnalysisWindow()
            self._place_first_window(self._window)
        if result is not None:
            self._window.present_result(result)
        self._window.show()
        self._window.raise_()
        return self._window

    @staticmethod
    def _place_first_window(window: AnalysisWindow) -> None:
        screens = QApplication.screens()
        if not screens:
            return
        stored = QSettings("PixelScope", "EnterpriseIqa").value("analysis_window_geometry")
        if isinstance(stored, QByteArray | bytes) and window.restoreGeometry(stored):
            geometry = window.frameGeometry()
            if any(
                geometry.intersected(screen.availableGeometry()).width() >= 100
                and geometry.intersected(screen.availableGeometry()).height() >= 100
                for screen in screens
            ):
                return
        primary = QApplication.primaryScreen()
        destination = next((s for s in screens if s != primary), primary or screens[0])
        bounds = destination.availableGeometry()
        width = min(1380, max(600, bounds.width()))
        height = min(780, max(440, bounds.height()))
        window.resize(width, height)
        window.move(
            bounds.x() + max(0, (bounds.width() - width) // 2),
            bounds.y() + max(0, (bounds.height() - height) // 2),
        )

    def shutdown(self) -> None:
        if self._closed:
            return
        self._closed = True
        window, self._window = self._window, None
        if window is not None:
            window.close()
            window.deleteLater()
