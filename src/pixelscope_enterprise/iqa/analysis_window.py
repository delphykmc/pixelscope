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
from PySide6.QtCore import QPoint, QRectF, QSettings, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QCloseEvent,
    QImage,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QTransform,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QMainWindow,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pixelscope_enterprise.iqa.analysis_model import (
    AnalysisResult,
    AttributeDisplay,
    Roi,
    clipped_cells,
    roi_statistics,
)

ResultLoader = Callable[[Path], AnalysisResult]
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
        self.horizontalScrollBar().valueChanged.connect(self._navigation_changed)
        self.verticalScrollBar().valueChanged.connect(self._navigation_changed)

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
        # Shift+drag defines a ROI; the wheel only zooms, never changes MainWindow.
        factor = 1.2 if event.angleDelta().y() > 0 else (1 / 1.2)
        next_scale = self.transform().m11() * factor
        if 0.04 <= next_scale <= 32:
            self.scale(factor, factor)
            self._navigation_changed()
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            self._roi_start = event.pos()
            event.accept()  # type: ignore[attr-defined]
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        start = self._roi_start
        self._roi_start = None
        if start is not None:
            a = self.mapToScene(start)
            b = self.mapToScene(event.pos())
            left, top = min(a.x(), b.x()), min(a.y(), b.y())
            width, height = abs(a.x() - b.x()), abs(a.y() - b.y())
            if width >= 1 and height >= 1:
                self.roi_requested.emit(left, top, width, height)
            event.accept()  # type: ignore[attr-defined]
            return
        super().mouseReleaseEvent(event)


def _map_pixmap(attribute: AttributeDisplay, half_range: float) -> QPixmap | None:
    grid = attribute.spatial
    if grid is None:
        return None
    image = QImage(grid.columns, grid.rows, QImage.Format.Format_ARGB32)
    image.fill(QColor(0, 0, 0, 0))
    # Work at grid resolution rather than allocating a second 4K RGB raster.
    for row in range(grid.rows):
        for col in range(grid.columns):
            if not grid.valid_mask[row, col]:
                continue
            normalized = float(np.clip(grid.values[row, col] / half_range, -1.0, 1.0))
            amount = abs(normalized)
            # A better: red; B better: blue; neutral: light gray. No auto-contrast.
            if normalized >= 0:
                color = QColor(245, int(239 * (1 - amount)), int(239 * (1 - amount)))
            else:
                color = QColor(int(239 * (1 - amount)), int(239 * (1 - amount)), 245)
            image.setPixelColor(col, row, color)
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
        self._roi_items: list[object] = []

        file_menu = self.menuBar().addMenu("File")
        self.open_action = file_menu.addAction("Open Result...")
        self.open_action.setObjectName("enterpriseIqaOpenResult")
        self.open_action.setEnabled(False)  # Enabled only with a genuine on-disk reader.
        self.open_action.triggered.connect(self._open_from_dialog)
        self.save_action = file_menu.addAction("Save Result As...")
        self.save_action.setObjectName("enterpriseIqaSaveResult")
        self.save_action.setEnabled(False)  # Not a fake fixture export.
        self.save_action.triggered.connect(self._save_from_dialog)
        self.export_action = file_menu.addAction("Export...")
        self.export_action.setEnabled(False)  # Separate H4 reporting work.

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
        self.result_combo.currentIndexChanged.connect(self._on_result_selected)
        inspector_layout.addWidget(self.result_combo)
        inspector_layout.addWidget(QLabel("Attributes · supplied order", inspector))
        self.attribute_table = QTableWidget(0, 3, inspector)
        self.attribute_table.setObjectName("enterpriseIqaAttributes")
        self.attribute_table.setHorizontalHeaderLabels(["Attribute", "Official", "Unit"])
        self.attribute_table.horizontalHeader().setStretchLastSection(True)
        self.attribute_table.verticalHeader().hide()
        self.attribute_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.attribute_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.attribute_table.itemSelectionChanged.connect(self._on_attribute_selected)
        inspector_layout.addWidget(self.attribute_table, 2)
        self.official_label = QLabel("Official pair comparison: —", inspector)
        self.official_label.setWordWrap(True)
        inspector_layout.addWidget(self.official_label)
        self.roi_label = QLabel("ROI: none", inspector)
        self.roi_label.setWordWrap(True)
        inspector_layout.addWidget(self.roi_label)
        inspector_layout.addWidget(QLabel("Fixed symmetric map range ±", inspector))
        self.range_editor = QDoubleSpinBox(inspector)
        self.range_editor.setObjectName("enterpriseIqaMapRange")
        self.range_editor.setDecimals(3)
        self.range_editor.setRange(0.001, 1_000_000.0)
        self.range_editor.setEnabled(False)
        self.range_editor.valueChanged.connect(self._update_range)
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
            "Open a saved Result using an installed reader. Shift+drag in any view selects a ROI."
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

    def present_result(self, result: AnalysisResult) -> None:
        """Explicitly switch to a result; never called by implicit job completion."""
        self._remember_navigation()
        is_new = result.result_id not in self._results
        self._results[result.result_id] = result
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
        for view, name in zip(self._views, ("Image A", "Image B", "Map")):
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
        self._rendering = True
        for i, view in enumerate(self._views):
            view._muted = True
            old_scene = view.scene()
            scene = QGraphicsScene(view)
            scene.setSceneRect(QRectF(0, 0, result.image_width, result.image_height))
            scene.setBackgroundBrush(QColor(29, 32, 36))
            if i < 2:
                path = result.source_a if i == 0 else result.source_b
                image = QImage(str(path)) if path is not None and path.is_file() else QImage()
                if (
                    image.isNull()
                    or image.width() != result.image_width
                    or image.height() != result.image_height
                ):
                    note = scene.addText("Source unavailable\nNumeric/spatial analysis retained")
                    note.setDefaultTextColor(QColor(240, 240, 240))
                    note.setPos(20, 20)
                else:
                    scene.addPixmap(QPixmap.fromImage(image))
            else:
                pixmap = _map_pixmap(attr, limit)
                grid = attr.spatial
                if pixmap is None or grid is None:
                    note = scene.addText("Spatial map unavailable")
                    note.setDefaultTextColor(QColor(240, 240, 240))
                else:
                    item = scene.addPixmap(pixmap)
                    item.setPos(grid.origin_x, grid.origin_y)
                    item.setTransformationMode(Qt.TransformationMode.FastTransformation)
                    item.setTransform(
                        QTransform().scale(grid.block_width, grid.block_height)
                    )
            view.setScene(scene)
            if old_scene is not None:
                old_scene.deleteLater()
        self._rendering = False
        for view in self._views:
            view._muted = False
        self._draw_roi(state.roi)
        if state.scale is not None and state.center_x is not None and state.center_y is not None:
            for view in self._views:
                view.apply_navigation(state.scale, state.center_x, state.center_y)
        else:
            view = self._views[0]
            view.fitInView(view.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
            center = view.mapToScene(view.viewport().rect().center())
            for other in self._views[1:]:
                other.apply_navigation(view.transform().m11(), center.x(), center.y())
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
            self.roi_label.setText("ROI: none · Shift+drag to inspect")
        elif attr.spatial is None:
            self.roi_label.setText("ROI selected; local spatial data unavailable")
        else:
            stats = roi_statistics(attr.spatial, roi)
            value = "missing" if stats.mean is None else f"{stats.mean:+.4f} {attr.unit}"
            self.roi_label.setText(
                f"GRID-DERIVED ROI: {value}\n"
                f"Valid area coverage: {stats.valid_coverage:.1%} (not official)"
            )
        if attr.spatial is None:
            self.clamp_label.setText("Map missing (not zero)")
        else:
            clipped, total = clipped_cells(attr.spatial, limit)
            pct = 0.0 if total == 0 else (clipped / total)
            self.clamp_label.setText(
                f"Map scale: −{limit:g} to +{limit:g} {attr.unit}\n"
                f"Clamped: {clipped}/{total} valid cells ({pct:.1%})"
            )

    def _draw_roi(self, roi: Roi | None) -> None:
        if roi is None:
            return
        rect = QRectF(*roi)
        for view in self._views:
            scene = view.scene()
            if scene is None:
                continue
            overlay = scene.addRect(rect, QPen(QColor(255, 205, 0), 2))
            overlay.setZValue(100)

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
        self._render_result()  # Attribute and ROI are retained; visuals stay synchronized.

    def _update_range(self, value: float) -> None:
        state = self._state()
        attr = self._attribute()
        if state is None or attr is None or value <= 0:
            return
        state.ranges[attr.attribute_id] = value
        self._render_result()

    def _sync_views(self, source: _LinkedView, scale: float, x: float, y: float) -> None:
        state = self._state()
        if state is None or self._rendering:
            return
        state.scale, state.center_x, state.center_y = scale, x, y
        for other in self._views:
            if other is not source:
                other.apply_navigation(scale, x, y)

    def _remember_navigation(self) -> None:
        state = self._state()
        if state is None or state.scale is not None:
            return
        view = self._views[0]
        center = view.mapToScene(view.viewport().rect().center())
        state.scale, state.center_x, state.center_y = view.transform().m11(), center.x(), center.y()

    def _open_from_dialog(self) -> None:
        if self._loader is None:
            return
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open saved IQA result", "", "Saved results (*)"
        )
        if not filename:
            return
        try:
            result = self._loader(Path(filename))
        except (OSError, ValueError):
            self.statusBar().showMessage("Result could not be opened or validated.")
            return
        self.present_result(result)

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
        stored = QSettings("PixelScope", "EnterpriseIqa").value(
            "analysis_window_geometry"
        )
        if stored is not None and window.restoreGeometry(stored):
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
