"""Downstream-owned, non-modal one-pair IQA Analysis Window.

Pure presentation surface: a private adapter will provide validated AnalysisResult
objects and optional disk Open/Save callbacks. No reference-private implementation,
Base modifications, network access, background worker or inferred metric formula.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
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
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QColor,
    QIcon,
    QImage,
    QKeyEvent,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QShowEvent,
    QStandardItemModel,
    QTransform,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDockWidget,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QRubberBand,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pixelscope.ui.design_tokens import TOKENS
from pixelscope.ui.plots_dock_title import PlotsDockTitleBar
from pixelscope_enterprise.iqa.analysis_model import (
    AnalysisResult,
    AttributeDisplay,
    LoadedAnalysis,
    Roi,
    clipped_cells,
    colorize_spatial_rgba,
    map_polarity_legend,
    roi_statistics,
    spatial_display_half_range,
)
from pixelscope_enterprise.iqa.attribute_chart import (
    ATTRIBUTE_ROLE,
    CHART_MEASUREMENT_ROLE,
    DISPLAY_RANGE_ROLE,
    ChartMeasurement,
    RelativeDifferenceDelegate,
)
from pixelscope_enterprise.iqa.dock_lifecycle import IqaDockLifecycle
from pixelscope_enterprise.iqa.html_report import report_folder, write_html_report
from pixelscope_enterprise.iqa.insights import rank_top_differences
from pixelscope_enterprise.iqa.measurement_export import write_measurements_csv
from pixelscope_enterprise.iqa.spatial_candidates import (
    SpatialCandidate,
    find_spatial_candidates,
)
from pixelscope_enterprise.iqa.spatial_dock import SpatialCandidatesPanel
from pixelscope_enterprise.iqa.visual_export import (
    ExportScope,
    export_folder,
    write_visual_pngs,
)

ResultLoader = Callable[[Path], LoadedAnalysis]
ResultSaver = Callable[[AnalysisResult, dict[str, object], Path], None]
IqaSettingsFactory = Callable[[], QSettings]


def default_iqa_settings() -> QSettings:
    """Preserve the legacy IQA namespace without changing QApplication identity."""
    return QSettings("PixelScope", "EnterpriseIqa")


@dataclass
class _ResultViewState:
    attribute_id: str
    roi: Roi | None = None
    ranges: dict[str, float] = field(default_factory=dict)  # by unit, not by attribute
    scale: float | None = None
    center_x: float | None = None
    center_y: float | None = None
    display_gain: float = 1.0
    chart_scope: str = "full_pair"
    scope_user_override: bool = False


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
        self.viewport().setCursor(Qt.CursorShape.CrossCursor if selecting else self._normal_cursor)

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
        elif event_type == QEvent.Type.FocusOut and (watched is self or watched is self.viewport()):
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


def _analysis_action_icon(kind: str) -> QIcon:
    """Paint three stable, high-contrast 20px Qt toolbar glyphs without theme files."""

    image = QPixmap(20, 20)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(QColor(TOKENS.text_primary), 2)
    pen.setCosmetic(True)
    painter.setPen(pen)
    if kind == "fit":
        for x, y, dx, dy in ((3, 3, 5, 5), (17, 3, -5, 5), (3, 17, 5, -5), (17, 17, -5, -5)):
            painter.drawLine(x, y, x + dx, y)
            painter.drawLine(x, y, x, y + dy)
    elif kind == "hotspot":
        painter.drawRect(3, 3, 14, 14)
        painter.drawEllipse(7, 7, 6, 6)
        painter.drawLine(10, 1, 10, 5)
        painter.drawLine(10, 15, 10, 19)
        painter.drawLine(1, 10, 5, 10)
        painter.drawLine(15, 10, 19, 10)
    elif kind == "swap":
        painter.drawLine(3, 6, 17, 6)
        painter.drawLine(17, 6, 13, 2)
        painter.drawLine(17, 6, 13, 10)
        painter.drawLine(17, 14, 3, 14)
        painter.drawLine(3, 14, 7, 10)
        painter.drawLine(3, 14, 7, 18)
    else:
        painter.drawRect(4, 4, 12, 12)
        painter.drawLine(7, 7, 13, 13)
        painter.drawLine(13, 7, 7, 13)
    painter.end()
    return QIcon(image)


_INSIGHT_COLORS = {
    "a": ("#e5857d", "A"),
    "b": ("#79afe6", "B"),
    "signed": ("#b99bdc", "±"),
    "empty": (TOKENS.border, "—"),
}


def _blend_insight_color(base: str, tint: str, strength: float) -> str:
    """Subtle semantic tint over the shared MAIN panel background."""

    original = QColor(base)
    highlight = QColor(tint)
    return QColor(
        round(original.red() * (1.0 - strength) + highlight.red() * strength),
        round(original.green() * (1.0 - strength) + highlight.green() * strength),
        round(original.blue() * (1.0 - strength) + highlight.blue() * strength),
    ).name()


def _insight_badge_icon(tone: str) -> QIcon:
    """Small letter-marked swatch: color is never the only direction cue."""

    color, glyph = _INSIGHT_COLORS[tone]
    pixmap = QPixmap(22, 22)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    painter.drawRoundedRect(QRect(1, 1, 20, 20), 6, 6)
    font = painter.font()
    font.setBold(True)
    font.setPixelSize(12)
    painter.setFont(font)
    painter.setPen(QColor("#182028"))
    painter.drawText(QRect(1, 1, 20, 20), Qt.AlignmentFlag.AlignCenter, glyph)
    painter.end()
    return QIcon(pixmap)


def _style_insight_card(card: QPushButton, tone: str) -> None:
    """Keep a calm semantic accent, with a distinct selected/hover state."""

    color, _ = _INSIGHT_COLORS[tone]
    base = TOKENS.raised_background
    quiet = _blend_insight_color(base, color, 0.14)
    hover = _blend_insight_color(base, color, 0.22)
    selected = _blend_insight_color(base, color, 0.30)
    card.setProperty("insightTone", tone)
    card.setStyleSheet(
        f"QPushButton {{ background-color: {quiet}; color: {TOKENS.text_primary}; "
        f"border: 1px solid {TOKENS.border}; border-left: 4px solid {color}; "
        "border-radius: 9px; padding: 6px 9px; text-align: left; }"
        f"QPushButton:hover {{ background-color: {hover}; border-color: {color}; }}"
        f"QPushButton:checked {{ background-color: {selected}; "
        f"border: 2px solid {color}; border-left: 5px solid {color}; font-weight: 700; }}"
        f"QPushButton:disabled {{ background-color: {base}; "
        f"border-color: {TOKENS.border}; color: {TOKENS.text_disabled}; }}"
    )
    card.setIcon(_insight_badge_icon(tone) if tone != "empty" else QIcon())


class _EnterpriseSpatialDockTitle(PlotsDockTitleBar):
    """Reuse MAIN Plots title controls without entering its reset-key registry."""

    _known_geometry_settings: set[str] = set()


class AnalysisWindow(QMainWindow):
    """One independent, non-modal window; may show with no loaded Result."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        settings_factory: IqaSettingsFactory | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings_factory = settings_factory or default_iqa_settings
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
        self._scene_result_id: str | None = None
        self._map_item: QGraphicsPixmapItem | None = None
        self._map_placeholder: QGraphicsTextItem | None = None
        self._pane_labels: list[QLabel] = []
        self._pane_wrappers: list[QWidget] = []
        self._sources_swapped = False
        self._group_tables: dict[str, QTableWidget] = {}
        self._range_editors: dict[str, QDoubleSpinBox] = {}
        self._group_sections: dict[str, QWidget] = {}
        self._group_units: list[str] = []
        self._top3_attribute_ids: list[str] = []
        self._source_result_id: str | None = None
        self._source_pixmaps: tuple[QPixmap | None, QPixmap | None] = (None, None)
        self._fit_pending_result_id: str | None = None
        self._fit_attempts_remaining = 8
        self._spatial_cache: dict[tuple[str, str, int], tuple[SpatialCandidate, ...]] = {}
        self._spatial_displayed: tuple[str, str, int] | None = None
        self._spatial_pending: tuple[str, str, int] | None = None
        self._spatial_future: Future[tuple[SpatialCandidate, ...]] | None = None
        self._spatial_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="iqa-roi")
        self._spatial_timer = QTimer(self)
        self._spatial_timer.setInterval(35)
        self._spatial_timer.timeout.connect(  # type: ignore[attr-defined]
            self._finish_spatial_if_ready
        )
        self._candidate_overlay_items: list[list[tuple[QGraphicsRectItem, QGraphicsTextItem]]] = []

        # Retain Qt menu parents and submenu actions with direct Python refs.
        # Avoid borrowing temporary QAction.menu() wrappers in native Qt tests.
        self.file_menu = self.menuBar().addMenu("File")
        file_menu = self.file_menu
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
        self.export_menu = QMenu("Export Result", file_menu)
        self.export_menu.setObjectName("enterpriseIqaExportResultMenu")
        file_menu.addMenu(self.export_menu)
        self.export_menu_action = self.export_menu.menuAction()
        self.export_menu_action.setEnabled(False)
        self.export_action = self.export_menu.addAction("Measurements (CSV)...")
        self.export_action.setObjectName("enterpriseIqaExportMeasurementsCsv")
        self.export_action.setEnabled(False)
        self.export_action.setToolTip(
            "Export full-pair comparison and grid-derived ROI estimates as CSV; "
            "not a reloadable saved IQA result"
        )
        self.export_action.triggered.connect(  # type: ignore[attr-defined]
            self._export_csv_from_dialog
        )
        self.image_export_action = self.export_menu.addAction("Images (PNG)...")
        self.image_export_action.setObjectName("enterpriseIqaExportImagesPng")
        self.image_export_action.setEnabled(False)
        self.image_export_action.setToolTip(
            "Export decoded source A/B and the selected spatial Map at original-pixel "
            "coordinates; this is not a reloadable IQA result."
        )
        self.image_export_action.triggered.connect(  # type: ignore[attr-defined]
            self._export_png_from_dialog
        )
        self.report_export_action = self.export_menu.addAction("Report (HTML)...")
        self.report_export_action.setObjectName("enterpriseIqaExportReportHtml")
        self.report_export_action.setEnabled(False)
        self.report_export_action.setToolTip(
            "Export an offline HTML report with separately labelled A/B/Map PNGs; "
            "not a reloadable IQA result."
        )
        self.report_export_action.triggered.connect(  # type: ignore[attr-defined]
            self._export_html_from_dialog
        )
        view_menu = self.menuBar().addMenu("View")
        self.clear_roi_action = view_menu.addAction("Clear ROI")
        self.clear_roi_action.setObjectName("enterpriseIqaClearRoi")
        # MAIN uses Esc for ROI; also accept Shift+Esc as a documented alias.
        self.clear_roi_action.setShortcuts([QKeySequence("Esc"), QKeySequence("Shift+Esc")])
        self.clear_roi_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        self.clear_roi_action.setEnabled(False)
        self.clear_roi_action.triggered.connect(self._clear_roi)  # type: ignore[attr-defined]
        self.swap_sources_action = view_menu.addAction("Swap A/B positions")
        self.swap_sources_action.setObjectName("enterpriseIqaSwapSources")
        # T is free in the generic MAIN keymap; WindowShortcut scopes the
        # single key to the independent Analysis Window.
        self.swap_sources_action.setShortcuts([QKeySequence("T"), QKeySequence("Alt+X")])
        self.swap_sources_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        self.swap_sources_action.triggered.connect(  # type: ignore[attr-defined]
            self._swap_sources
        )

        # Native window toolbar: actions are shared with View menu, so tooltips,
        # enablement, mouse and scoped keyboard activation cannot diverge.
        self.fit_action = view_menu.addAction("Fit pair")
        self.fit_action.setObjectName("enterpriseIqaFitAction")
        self.fit_action.setShortcut(QKeySequence("Ctrl+0"))
        self.fit_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        self.fit_action.setEnabled(False)
        self.fit_action.triggered.connect(self._fit_pair)  # type: ignore[attr-defined]
        self.fit_action.setIcon(_analysis_action_icon("fit"))
        self.fit_action.setToolTip("Fit all three panes to the source image (Ctrl+0)")
        self.swap_sources_action.setIcon(_analysis_action_icon("swap"))
        self.swap_sources_action.setToolTip(
            "Swap the visual positions of A and B; measurement identity is unchanged " "(T, Alt+X)"
        )
        self.clear_roi_action.setIcon(_analysis_action_icon("clear"))
        self.hotspot_overlay_action = view_menu.addAction("Show Hotspot Markers")
        self.hotspot_overlay_action.setObjectName("enterpriseIqaShowHotspotBoxes")
        self.hotspot_overlay_action.setIcon(_analysis_action_icon("hotspot"))
        self.hotspot_overlay_action.setCheckable(True)
        self.hotspot_overlay_action.setChecked(False)
        self.hotspot_overlay_action.setShortcut(QKeySequence("Alt+H"))
        self.hotspot_overlay_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        self.hotspot_overlay_action.setToolTip(
            "Toggle numbered hotspot markers on A/B/Map (Alt+H). "
            "Separate from the Hotspot Candidates View panel."
        )
        self.hotspot_overlay_action.toggled.connect(  # type: ignore[attr-defined]
            self._hotspot_overlay_toggled
        )
        self.clear_roi_action.setToolTip("Clear only the current ROI (Esc, Shift+Esc)")

        self.iqa_toolbar = QToolBar("IQA analysis tools", self)
        self.iqa_toolbar.setObjectName("enterpriseIqaToolbar")
        self.iqa_toolbar.setMovable(False)
        self.iqa_toolbar.setFloatable(False)
        self.iqa_toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.iqa_toolbar)

        def action_button(action: QAction) -> QToolButton:
            button = QToolButton(self.iqa_toolbar)
            button.setDefaultAction(action)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            self.iqa_toolbar.addWidget(button)
            return button

        self.fit_button = action_button(self.fit_action)
        self.swap_button = action_button(self.swap_sources_action)
        self.iqa_toolbar.addSeparator()
        self.clear_roi_tool_button = action_button(self.clear_roi_action)
        self.iqa_toolbar.addSeparator()
        self.iqa_toolbar.addAction(self.hotspot_overlay_action)

        root_split = QSplitter(Qt.Orientation.Horizontal, self)
        root_split.setObjectName("enterpriseIqaRootSplitter")
        image_split = QSplitter(Qt.Orientation.Horizontal, root_split)
        image_split.setObjectName("enterpriseIqaImageSplitter")
        self._image_split = image_split
        for title in ("Image A", "Image B", "Relative Spatial Map"):
            wrapper = QWidget(image_split)
            self._pane_wrappers.append(wrapper)
            column = QVBoxLayout(wrapper)
            column.setContentsMargins(2, 2, 2, 2)
            caption = QLabel(title, wrapper)
            caption.setObjectName("enterpriseIqaPaneCaption" + title.replace(" ", ""))
            caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
            caption.setWordWrap(True)
            self._pane_labels.append(caption)
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
        self._set_pane_order()
        inspector = QWidget(root_split)
        inspector.setObjectName("enterpriseIqaInspector")
        inspector.setMinimumWidth(385)
        inspector_layout = QVBoxLayout(inspector)
        self.result_combo = QComboBox(inspector)
        self.result_combo.setObjectName("enterpriseIqaResultSelector")
        self.result_combo.currentIndexChanged.connect(  # type: ignore[attr-defined]
            self._on_result_selected
        )
        # A compact single-line control bar; value provenance belongs in
        # tooltips/Details, while per-bar endpoints identify quality direction.
        scope_toolbar = QHBoxLayout()
        scope_toolbar.setContentsMargins(0, 0, 0, 0)
        scope_toolbar.setSpacing(5)
        scope_toolbar.addWidget(QLabel("Scope", inspector))
        self.chart_scope_combo = QComboBox(inspector)
        self.chart_scope_combo.setObjectName("enterpriseIqaChartScope")
        self.chart_scope_combo.addItem("Full", "full_pair")
        self.chart_scope_combo.addItem("ROI · grid", "roi_grid")
        self.chart_scope_combo.setToolTip(
            "Full: original whole-pair measurements. ROI: signed, masked, "
            "area-weighted GRID estimates (not validated local quality scores)."
        )
        self.chart_scope_combo.currentIndexChanged.connect(  # type: ignore[attr-defined]
            self._on_chart_scope_changed
        )
        scope_toolbar.addWidget(self.chart_scope_combo, 1)
        scope_toolbar.addWidget(QLabel("Map gain", inspector))
        self.gain_editor = QDoubleSpinBox(inspector)
        self.gain_editor.setObjectName("enterpriseIqaDisplayGain")
        self.gain_editor.setDecimals(1)
        self.gain_editor.setRange(0.5, 10.0)
        self.gain_editor.setSingleStep(0.5)
        self.gain_editor.setValue(1.0)
        self.gain_editor.setPrefix("×")
        self.gain_editor.setToolTip(
            "Visual Map contrast only: color fraction = Grid × Gain / Unit Range. "
            "Full-pair bar and ROI values are unchanged."
        )
        self.gain_editor.valueChanged.connect(self._update_gain)  # type: ignore[attr-defined]
        scope_toolbar.addWidget(self.gain_editor)
        inspector_layout.addLayout(scope_toolbar)

        # Source-coordinate ROI identity remains a single fixed-height row.
        roi_toolbar = QHBoxLayout()
        roi_toolbar.setContentsMargins(0, 0, 0, 0)
        self.roi_brief_label = QLabel("ROI: none", inspector)
        self.roi_brief_label.setObjectName("enterpriseIqaRoiBrief")
        self.roi_brief_label.setToolTip("Source-pixel ROI coordinates (x, y, width, height).")
        roi_toolbar.addWidget(self.roi_brief_label, 1)
        self.clear_roi_button = QPushButton("Clear", inspector)
        self.clear_roi_button.setObjectName("enterpriseIqaClearRoiButton")
        self.clear_roi_button.setToolTip("Clear only the current ROI (Esc / Shift+Esc)")
        self.clear_roi_button.setEnabled(False)
        self.clear_roi_button.clicked.connect(self._clear_roi)  # type: ignore[attr-defined]
        roi_toolbar.addWidget(self.clear_roi_button)
        inspector_layout.addLayout(roi_toolbar)

        # Own each tab's scroll area under a stable QTabWidget parent. Only
        # Attributes is visible by default; Details stays accessible without
        # reserving height on short/FHD workspaces or changing scientific scope.
        self.inspector_tabs = QTabWidget(inspector)
        self.inspector_tabs.setObjectName("enterpriseIqaInspectorTabs")
        self.inspector_tabs.setDocumentMode(True)
        self.inspector_tabs.setMinimumHeight(140)
        self.attribute_table = QTableWidget(0, 2, inspector)  # first active unit alias
        self.attribute_table.hide()
        self.range_editor = QDoubleSpinBox(inspector)  # first active unit alias
        self.range_editor.hide()
        self.group_scroll = QScrollArea(self.inspector_tabs)
        self.group_scroll.setObjectName("enterpriseIqaGroupScroll")
        self.group_scroll.setWidgetResizable(True)
        self.group_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.group_content = QWidget()
        self._groups_layout = QVBoxLayout(self.group_content)
        self._groups_layout.setContentsMargins(0, 2, 0, 2)
        self._groups_layout.setSpacing(7)
        self.group_scroll.setWidget(self.group_content)
        self.inspector_tabs.addTab(self.group_scroll, "Attributes")
        self.details_scroll = QScrollArea(self.inspector_tabs)
        self.details_scroll.setObjectName("enterpriseIqaInspectorDetails")
        self.details_scroll.setWidgetResizable(True)
        self.details_scroll.setFrameShape(QFrame.Shape.NoFrame)
        details_content = QWidget()
        details_layout = QVBoxLayout(details_content)
        details_layout.setContentsMargins(0, 2, 0, 2)
        details_layout.setSpacing(5)
        self.details_scroll.setWidget(details_content)
        self.inspector_tabs.addTab(self.details_scroll, "Details")
        self.inspector_tabs.setCurrentIndex(0)
        inspector_layout.addWidget(self.inspector_tabs, 1)
        self.detail_context = QLabel("DETAILS · select an attribute", details_content)
        self.detail_context.setObjectName("enterpriseIqaDetailContext")
        details_layout.addWidget(self.detail_context)
        self.official_label = QLabel("Full-pair comparison: —", inspector)
        self.official_label.setWordWrap(True)
        official_card = QFrame(inspector)
        official_card.setObjectName("enterpriseIqaOfficialCard")
        official_card.setFrameShape(QFrame.Shape.StyledPanel)
        official_layout = QVBoxLayout(official_card)
        official_layout.setContentsMargins(9, 6, 9, 6)
        official_layout.setSpacing(4)
        official_layout.addWidget(QLabel("FULL-PAIR COMPARISON", official_card))
        official_description = QLabel(
            "Verified A/B difference for the entire image pair. "
            "Not calculated from the selected ROI or Map grid.",
            official_card,
        )
        official_description.setObjectName("enterpriseIqaOfficialExplanation")
        official_description.setWordWrap(True)
        official_layout.addWidget(official_description)
        official_layout.addWidget(self.official_label)
        details_layout.addWidget(official_card, 1)
        self.roi_label = QLabel("ROI: none", inspector)
        self.roi_label.setWordWrap(True)
        roi_card = QFrame(inspector)
        roi_card.setObjectName("enterpriseIqaRoiCard")
        roi_card.setFrameShape(QFrame.Shape.StyledPanel)
        roi_layout = QVBoxLayout(roi_card)
        roi_layout.setContentsMargins(9, 6, 9, 6)
        roi_layout.setSpacing(4)
        roi_layout.addWidget(QLabel("ROI ANALYSIS · SOURCE PIXELS", roi_card))
        roi_description = QLabel(
            "Selected rectangle in original-image pixels. GRID-DERIVED mean "
            "estimates local differences; it is not a full-pair measurement. "
            "Coverage is the ROI area supported by valid Map cells.",
            roi_card,
        )
        roi_description.setObjectName("enterpriseIqaRoiExplanation")
        roi_description.setWordWrap(True)
        roi_layout.addWidget(roi_description)
        roi_layout.addWidget(self.roi_label)
        details_layout.addWidget(roi_card, 2)
        self.clamp_label = QLabel("Map: unavailable", inspector)
        self.clamp_label.setWordWrap(True)
        map_card = QFrame(inspector)
        map_card.setObjectName("enterpriseIqaMapCard")
        map_card.setFrameShape(QFrame.Shape.StyledPanel)
        map_layout = QVBoxLayout(map_card)
        map_layout.setContentsMargins(9, 6, 9, 6)
        map_layout.setSpacing(4)
        map_layout.addWidget(QLabel("SPATIAL MAP · CELL STATISTICS", map_card))
        map_description = QLabel(
            "Colors show signed grid-cell differences at Unit Range ±R and Map Gain ×G. "
            "Invalid cells are transparent; clipped cells reach the end color.",
            map_card,
        )
        map_description.setObjectName("enterpriseIqaMapExplanation")
        map_description.setWordWrap(True)
        map_layout.addWidget(map_description)
        map_layout.addWidget(self.clamp_label)
        details_layout.addWidget(map_card, 2)
        root_split.addWidget(image_split)
        root_split.addWidget(inspector)
        root_split.setStretchFactor(0, 3)
        root_split.setStretchFactor(1, 1)
        central = QWidget(self)
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(6, 5, 6, 5)
        header = QHBoxLayout()
        workspace_heading = QLabel("IQA  /  PAIR ANALYSIS", central)
        workspace_heading.setObjectName("enterpriseIqaWorkspaceTitle")
        header.addWidget(workspace_heading)
        header.addWidget(QLabel("Result:", central))
        # Keep the same combo and its original result-selected behavior.
        header.addWidget(self.result_combo, 1)
        self.pair_summary = QLabel("No result loaded", central)
        self.pair_summary.setObjectName("enterpriseIqaPairSummary")
        self.pair_summary.setMinimumWidth(230)
        header.addWidget(self.pair_summary, 2)
        self.roi_hint = QLabel("Shift+drag ROI  •  Esc clears", central)
        self.roi_hint.setObjectName("enterpriseIqaRoiHint")
        header.addWidget(self.roi_hint)
        central_layout.addLayout(header)
        # One compact, first-screen overview; cards select the official metric,
        # they NEVER replace the detailed unit-group chart or source evidence.
        top3_frame = QFrame(central)
        top3_frame.setObjectName("enterpriseIqaTop3Frame")
        top3_layout = QVBoxLayout(top3_frame)
        top3_layout.setContentsMargins(7, 5, 7, 5)
        top3_layout.setSpacing(4)
        self.top3_title = QLabel("TOP 3   ·   FULL-PAIR dB", top3_frame)
        self.top3_title.setObjectName("enterpriseIqaTop3Title")
        top3_layout.addWidget(self.top3_title)
        top3_row = QHBoxLayout()
        top3_row.setSpacing(7)
        self.top3_buttons: list[QPushButton] = []
        for index in range(3):
            card = QPushButton(f"#{index + 1}  —", top3_frame)
            card.setObjectName("enterpriseIqaTop3Card")
            card.setMinimumHeight(60)
            card.setIconSize(QSize(22, 22))
            _style_insight_card(card, "empty")
            card.setCheckable(True)
            card.setEnabled(False)
            card.clicked.connect(  # type: ignore[attr-defined]
                lambda _checked=False, n=index: self._activate_top_card(n)
            )
            self.top3_buttons.append(card)
            top3_row.addWidget(card, 1)
        top3_layout.addLayout(top3_row)
        central_layout.addWidget(top3_frame)
        central_layout.addWidget(root_split, 1)
        self.setCentralWidget(central)

        # Own QMainWindow dock manager: never attach this dock to PixelScope MAIN.
        self.spatial_dock = QDockWidget("Hotspot Candidates View", self)
        self.spatial_dock.setObjectName("enterpriseIqaSpatialCandidatesDock")
        self.spatial_dock.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea | Qt.DockWidgetArea.TopDockWidgetArea
        )
        self.spatial_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.spatial_panel = SpatialCandidatesPanel(self.spatial_dock)
        self.spatial_dock.setWidget(self.spatial_panel)
        # Exactly the native Plot workspace controls: float/dock, maximize or
        # restore to the active screen work area, and hide. Drawn Qt icons do
        # not depend on an OS-specific floating QDockWidget title decoration.
        self.spatial_dock_title = _EnterpriseSpatialDockTitle(
            self.spatial_dock,
            title="Hotspot Candidates View",
            geometry_setting="ui/enterprise_iqa_spatial_floating_geometry",
        )
        self.spatial_dock.setTitleBarWidget(self.spatial_dock_title)
        self._spatial_dock_chrome = IqaDockLifecycle(
            self.spatial_dock,
            title_bar=self.spatial_dock_title,
        )
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.spatial_dock)
        view_menu.addSeparator()
        self.hotspot_candidates_action = self.spatial_dock.toggleViewAction()
        self.hotspot_candidates_action.setText("Hotspot Candidates View")
        self.hotspot_candidates_action.setShortcut(QKeySequence("Alt+Shift+H"))
        self.hotspot_candidates_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        self.hotspot_candidates_action.setToolTip(
            "Show/hide the Hotspot Candidates View (Alt+Shift+H). "
            "Candidates are computed only when the panel or markers are requested."
        )
        view_menu.addAction(self.hotspot_candidates_action)
        self.spatial_panel.candidate_clicked.connect(self._select_spatial_candidate)
        self.spatial_panel.stride_changed.connect(self._request_spatial_candidates)
        self.spatial_dock.visibilityChanged.connect(  # type: ignore[attr-defined]
            self._spatial_dock_visibility_changed
        )
        # Restore location/size but NOT visibility. The candidates panel is
        # explicitly opt-in on every new Analysis Window; an old persisted
        # visible dock must not trigger a scan or surprise the operator.
        dock_state = self._settings_factory().value("analysis_window_spatial_dock_state")
        if isinstance(dock_state, QByteArray | bytes):
            self.restoreState(dock_state)
        self.spatial_dock.hide()
        # Read the same reusable design tokens as the public PixelScope host.
        # No private stylesheet or global palette mutation when hosted by MAIN.
        self.setStyleSheet(
            f"QLabel#enterpriseIqaWorkspaceTitle {{ color: {TOKENS.text_primary}; "
            "font-weight: 700; }"
            f"QLabel#enterpriseIqaDetailContext, "
            f"QLabel#enterpriseIqaOfficialExplanation, QLabel#enterpriseIqaRoiExplanation, "
            f"QLabel#enterpriseIqaMapExplanation {{ color: {TOKENS.text_secondary}; }}"
            f"QFrame#enterpriseIqaOfficialCard, "
            f"QFrame#enterpriseIqaRoiCard, QFrame#enterpriseIqaMapCard {{ "
            f"background: {TOKENS.raised_background}; border: 1px solid {TOKENS.border}; }}"
            f"QFrame#enterpriseIqaTop3Frame {{ background: {TOKENS.raised_background}; "
            f"border: 1px solid {TOKENS.border}; border-radius: 9px; }}"
            f"QLabel#enterpriseIqaTop3Title {{ color: {TOKENS.text_secondary}; "
            "font-weight: 700; }"
        )
        self.statusBar().showMessage(
            "Shift+drag ROI · T swaps A/B · Map Gain changes visualization only."
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

        # H1 legacy states used attribute-id ranges; H2 added display_gain.
        # Chart scope is a user-only state field and defaults to Full pair
        # for all earlier saved snapshots, even if they contain an active ROI.
        fields = set(raw)
        basic_fields = {"attribute_id", "roi", "ranges", "viewport"}
        legacy = fields == basic_fields
        with_gain = basic_fields | {"display_gain"}
        with_scope = with_gain | {"chart_scope", "scope_user_override"}
        if fields not in (basic_fields, with_gain, with_scope):
            raise ValueError("invalid analysis_state fields")
        scope = raw["chart_scope"] if fields == with_scope else "full_pair"
        override = raw["scope_user_override"] if fields == with_scope else False
        if (
            not isinstance(scope, str)
            or scope not in ("full_pair", "roi_grid")
            or not isinstance(override, bool)
        ):
            raise ValueError("invalid chart scope or user override")
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
        units = {item.unit for item in result.attributes}
        lookup = {item.attribute_id: item.unit for item in result.attributes}
        ranges: dict[str, float] = {}
        legacy_ranges: dict[str, float] = {}
        for key, value in raw_ranges.items():
            if not isinstance(key, str) or key not in (lookup if legacy else units):
                raise ValueError("range refers to missing attribute or unit")
            limit = finite_number(value)
            if not 0.001 <= limit <= 1_000_000.0:
                raise ValueError("saved range outside UI limits")
            if legacy:
                legacy_ranges[key] = limit
            else:
                if limit < 0.5 or abs(limit * 2 - round(limit * 2)) > 1e-7:
                    raise ValueError("saved unit range must be a positive 0.5 step")
                ranges[key] = limit
        if legacy:
            # Deterministic migration: the selected metric's old per-attr
            # setting takes precedence for its unit; other units use their
            # first matching metric in producer order.
            for attr in result.attributes:
                if attr.attribute_id in legacy_ranges and attr.unit not in ranges:
                    value = legacy_ranges[attr.attribute_id]
                    ranges[attr.unit] = max(0.5, float(np.ceil(value * 2) / 2))
            chosen_unit = lookup[attribute_id]
            if attribute_id in legacy_ranges:
                value = legacy_ranges[attribute_id]
                ranges[chosen_unit] = max(0.5, float(np.ceil(value * 2) / 2))
        gain = 1.0 if legacy else finite_number(raw["display_gain"])
        if not 0.5 <= gain <= 10.0 or abs(gain * 2 - round(gain * 2)) > 1e-7:
            raise ValueError("saved display gain must be a positive 0.5 step")

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
            # Normalize legacy fractional saved ROIs outward onto covered pixels.
            # Source coordinates are an integer-pixel selection, never subpixel.
            left, top = int(np.floor(x)), int(np.floor(y))
            right, bottom = int(np.ceil(x + width)), int(np.ceil(y + height))
            roi = (left, top, right - left, bottom - top)

        if scope == "roi_grid" and roi is None:
            raise ValueError("ROI chart scope requires a saved ROI")
        viewport = raw["viewport"]
        if not isinstance(viewport, dict) or set(viewport) != {"scale", "center_x", "center_y"}:
            raise ValueError("invalid saved viewport")
        zoom = viewport["scale"]
        x_center = viewport["center_x"]
        y_center = viewport["center_y"]
        if zoom is None and x_center is None and y_center is None:
            return _ResultViewState(
                attribute_id,
                roi,
                ranges,
                display_gain=gain,
                chart_scope=scope,
                scope_user_override=override,
            )
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
        return _ResultViewState(
            attribute_id, roi, ranges, scale, center_x, center_y, gain, scope, override
        )

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
            # Prefer a first view with both official summary and spatial
            # evidence; never silently rank unrelated Attribute units.
            first_view = next(
                (
                    item
                    for item in result.attributes
                    if item.spatial is not None and item.official_value is not None
                ),
                result.attributes[0],
            )
            self._states[result.result_id] = _ResultViewState(first_view.attribute_id)
        self._active_id = result.result_id
        self.result_combo.blockSignals(True)
        self.result_combo.setCurrentIndex(self.result_combo.findData(result.result_id))
        self.result_combo.blockSignals(False)
        self.setWindowTitle(f"IQA Analysis — {result.result_id}")
        self.pair_summary.setText(
            f"A: {result.source_a_label}  /  B: {result.source_b_label}  "
            f"• {result.image_width}×{result.image_height}"
        )
        self.pair_summary.setToolTip(
            f"Source A: {result.source_a_label}\nSource B: {result.source_b_label}"
        )
        self.fit_action.setEnabled(True)
        self.save_action.setEnabled(self._saver is not None)
        self.export_menu_action.setEnabled(True)
        self.export_action.setEnabled(True)
        self._populate_attributes()
        self._sync_chart_scope()
        self._refresh_all_group_bars()
        self._update_top_cards()
        self.gain_editor.setEnabled(True)
        self._render_result()
        self.statusBar().showMessage(
            "Full-pair comparison and GRID-derived ROI estimates are distinct. "
            "Regional signed estimates never imply a verified quality winner."
        )

    def _update_top_cards(self) -> None:
        """Refresh a guarded OFFICIAL-only first insight for the current pair."""

        if self._active_id is None:
            return
        result = self._results[self._active_id]
        ranked = rank_top_differences(result)
        self._top3_attribute_ids = [item.attribute_id for item in ranked]
        unknown_gate = any(
            attr.unit == "dB" and attr.summary_signal_gate is None for attr in result.attributes
        )
        self.top3_title.setText(
            "TOP 3   ·   VERIFIED FULL-PAIR dB"
            if ranked
            else "TOP 3   ·   NO QUALIFYING dB"
            if not unknown_gate
            else "TOP 3   ·   SIGNAL PENDING"
        )
        for index, card in enumerate(self.top3_buttons):
            if index >= len(ranked):
                card.setText(f"#{index + 1}  —")
                _style_insight_card(card, "empty")
                card.setToolTip(
                    "Requires eligible full-pair dB, |difference| > 0.3 dB, "
                    "and at least one original-relative signal above -50 dB."
                )
                card.setEnabled(False)
                card.setChecked(False)
                continue
            item = ranked[index]
            tone = ("a" if item.delta_db > 0 else "b") if item.quality_oriented else "signed"
            _style_insight_card(card, tone)
            conclusion = (
                ("A better" if item.delta_db > 0 else "B better")
                if item.quality_oriented
                else "signed only · no winner"
            )
            rank_symbol = "★ 1" if index == 0 else str(index + 1)
            card.setText(
                f"{rank_symbol}   {item.label}\n" f"{item.delta_db:+.3f} dB  ·  {conclusion}"
            )
            card.setToolTip(
                f"Rank {index + 1} of verified global |dB| differences: "
                f"{item.label} {item.delta_db:+.4f} dB (full pair). "
                "Card selection opens its spatial evidence, not an ROI quality score."
            )
            card.setEnabled(True)
        self._sync_top_cards()

    def _sync_top_cards(self) -> None:
        state = self._state()
        for index, card in enumerate(self.top3_buttons):
            card.setChecked(
                state is not None
                and index < len(self._top3_attribute_ids)
                and state.attribute_id == self._top3_attribute_ids[index]
            )

    def _activate_top_card(self, index: int) -> None:
        if index >= len(self._top3_attribute_ids):
            return
        state = self._state()
        if state is None:
            return
        state.attribute_id = self._top3_attribute_ids[index]
        self._select_active_attribute()
        self._render_result()

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
            "ranges": dict(state.ranges),  # stable unit names, not attribute IDs
            "display_gain": state.display_gain,
            "chart_scope": state.chart_scope,
            "scope_user_override": state.scope_user_override,
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

    @staticmethod
    def _unit_default_range(result: AnalysisResult, unit: str) -> float:
        """Only use declared adapter visualization defaults, never grid min/max."""

        declared = [
            attr.chart_axis_range or attr.fixed_range
            for attr in result.attributes
            if attr.unit == unit
        ]
        return max(0.5, float(np.ceil(max(declared) * 2.0) / 2.0))

    def _populate_attributes(self) -> None:
        result = self._results[self._active_id]  # type: ignore[index]
        state = self._state()
        self._switching = True
        # QScrollArea owns the groups; clear stale widgets on a result change.
        while self._groups_layout.count():
            layout_item = self._groups_layout.takeAt(0)
            section = layout_item.widget() if layout_item is not None else None
            if section is not None:
                section.hide()
                section.deleteLater()
        self._group_sections = {}
        self._group_tables = {}
        self._range_editors = {}
        groups: dict[str, list[AttributeDisplay]] = {}
        for attr in result.attributes:
            groups.setdefault(attr.unit, []).append(attr)
        self._group_units = list(groups)
        for unit, attrs in groups.items():
            section = QFrame(self.group_content)
            section.setObjectName("enterpriseIqaUnitSection")
            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(3, 3, 3, 3)
            section_layout.setSpacing(3)
            top = QHBoxLayout()
            top.addWidget(QLabel(f"{unit}  ·  {len(attrs)} attributes", section), 1)
            top.addWidget(QLabel("Range ±", section))
            editor = QDoubleSpinBox(section)
            editor.setObjectName("enterpriseIqaUnitRange")
            editor.setDecimals(1)
            editor.setRange(0.5, 1_000_000.0)
            editor.setSingleStep(0.5)
            editor.setSuffix(f" {unit}")
            editor.setToolTip(
                "One symmetric numeric range for ALL bars of this unit, "
                "and the selected Map of this unit."
            )
            default = self._unit_default_range(result, unit)
            limit = state.ranges.get(unit, default) if state is not None else default
            editor.setValue(limit)
            editor.valueChanged.connect(  # type: ignore[attr-defined]
                lambda value, unit=unit: self._update_group_range(unit, value)
            )
            top.addWidget(editor)
            section_layout.addLayout(top)

            table = QTableWidget(len(attrs), 2, section)
            table.setObjectName("enterpriseIqaAttributes")
            table.setHorizontalHeaderLabels(["Metric / family", "Full-pair comparison"])
            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
            table.setColumnWidth(0, 142)
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            table.setItemDelegateForColumn(1, RelativeDifferenceDelegate(table))
            table.setAlternatingRowColors(True)
            table.verticalHeader().hide()
            table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            table.setFixedHeight(27 + 32 * len(attrs))
            for row, attr in enumerate(attrs):
                table.setRowHeight(row, 32)
                for col, content in enumerate((f"{attr.label}\n{attr.group}", "")):
                    item = QTableWidgetItem(content)
                    item.setData(Qt.ItemDataRole.UserRole, attr.attribute_id)
                    item.setData(ATTRIBUTE_ROLE, attr)
                    item.setData(DISPLAY_RANGE_ROLE, limit)
                    item.setToolTip(
                        f"{attr.label} · {attr.group} · {unit}; "
                        f"full-pair value {attr.official_availability}; group scale ±{limit:g}"
                    )
                    table.setItem(row, col, item)
            table.itemSelectionChanged.connect(  # type: ignore[attr-defined]
                lambda unit=unit: self._on_group_attribute_selected(unit)
            )
            section_layout.addWidget(table)
            self._groups_layout.addWidget(section)
            self._group_sections[unit] = section
            self._group_tables[unit] = table
            self._range_editors[unit] = editor

        self._groups_layout.addStretch(1)
        # Compatibility accessors for first-unit consumers; actual state is
        # always by unit, never by whichever table currently has selection.
        first_unit = self._group_units[0]
        self.attribute_table = self._group_tables[first_unit]
        self.range_editor = self._range_editors[first_unit]
        self.gain_editor.blockSignals(True)
        self.gain_editor.setValue(state.display_gain if state is not None else 1.0)
        self.gain_editor.blockSignals(False)
        self._switching = False
        self._select_active_attribute()

    def _select_active_attribute(self) -> None:
        state = self._state()
        if state is None or self._active_id is None:
            return
        selected = self._results[self._active_id].attribute(state.attribute_id)
        self._switching = True
        for unit, table in self._group_tables.items():
            if unit == selected.unit:
                for row in range(table.rowCount()):
                    if table.item(row, 0).data(Qt.ItemDataRole.UserRole) == selected.attribute_id:
                        table.selectRow(row)
                        break
            else:
                table.clearSelection()
        self._switching = False

    def _on_group_attribute_selected(self, unit: str) -> None:
        if self._switching or self._active_id is None:
            return
        table = self._group_tables.get(unit)
        if table is None:
            return
        selected_rows = table.selectionModel().selectedRows()
        if len(selected_rows) != 1:
            return
        item = table.item(selected_rows[0].row(), 0)
        state = self._state()
        if item is None or state is None:
            return
        attribute_id = str(item.data(Qt.ItemDataRole.UserRole))
        if attribute_id == state.attribute_id:
            return
        state.attribute_id = attribute_id
        self._select_active_attribute()
        self._render_result()

    def _on_attribute_selected(self) -> None:
        """Legacy first-group selection callback kept for compatibility."""

        if self._group_units:
            self._on_group_attribute_selected(self._group_units[0])

    def _sync_chart_scope(self) -> None:
        """Mirror per-result selection, disabling ROI mode without geometry."""

        state = self._state()
        roi_ready = state is not None and state.roi is not None
        combo_model = self.chart_scope_combo.model()
        if isinstance(combo_model, QStandardItemModel):
            roi_option = combo_model.item(1)
            if roi_option is not None:
                roi_option.setEnabled(roi_ready)
        scope = state.chart_scope if state is not None else "full_pair"
        if not roi_ready:
            scope = "full_pair"
        index = self.chart_scope_combo.findData(scope)
        self.chart_scope_combo.blockSignals(True)
        self.chart_scope_combo.setCurrentIndex(max(index, 0))
        self.chart_scope_combo.blockSignals(False)
        # Scope changes must not shift the chart geometry or reserve
        # explanatory lines above the actual Attribute measurements.

    def _on_chart_scope_changed(self, _index: int) -> None:
        state = self._state()
        if state is None:
            return
        requested = self.chart_scope_combo.currentData()
        if requested not in ("full_pair", "roi_grid"):
            return
        if requested == "roi_grid" and state.roi is None:
            self._sync_chart_scope()
            return
        # A manual Full-pair choice wins over later ROI drag gestures.
        state.chart_scope = requested
        state.scope_user_override = True
        self._sync_chart_scope()
        self._refresh_all_group_bars()

    def _refresh_all_group_bars(self) -> None:
        for unit in self._group_tables:
            self._refresh_group_bars(unit)

    def _refresh_group_bars(self, unit: str) -> None:
        state = self._state()
        if state is None or self._active_id is None:
            return
        table = self._group_tables.get(unit)
        if table is None:
            return
        limit = self._display_range(
            next(a for a in self._results[self._active_id].attributes if a.unit == unit), state
        )
        is_roi = state.chart_scope == "roi_grid" and state.roi is not None
        table.setHorizontalHeaderLabels(["Metric / family", "ROI Δ (grid)" if is_roi else "Pair Δ"])
        for row in range(table.rowCount()):
            cell = table.item(row, 1)
            if cell is None:
                continue
            cell.setData(DISPLAY_RANGE_ROLE, limit)
            attr = cell.data(ATTRIBUTE_ROLE)
            if not isinstance(attr, AttributeDisplay):
                continue
            if is_roi:
                roi = state.roi
                assert roi is not None
                if attr.spatial is None:
                    measurement = ChartMeasurement(None, "missing", 0.0)
                else:
                    stats = roi_statistics(attr.spatial, roi)
                    measurement = ChartMeasurement(
                        stats.mean,
                        "available" if stats.mean is not None else "missing",
                        stats.valid_coverage,
                    )
                cell.setData(CHART_MEASUREMENT_ROLE, measurement)
                cell.setToolTip(
                    f"{attr.label}: GRID-DERIVED ROI estimate from source-coordinate "
                    f"mask/area; valid coverage {measurement.valid_coverage:.1%}; "
                    "signed local evidence, no regional quality winner."
                )
            else:
                cell.setData(CHART_MEASUREMENT_ROLE, None)
                cell.setToolTip(
                    f"{attr.label}: full-pair producer comparison "
                    f"({attr.official_availability}); display range ±{limit:g} {unit}."
                )
        table.viewport().update()

    def _update_group_range(self, unit: str, value: float) -> None:
        state = self._state()
        if state is None or unit not in self._group_tables or value <= 0:
            return
        value = max(0.5, min(1_000_000.0, round(value * 2) / 2))
        editor = self._range_editors[unit]
        if editor.value() != value:
            editor.blockSignals(True)
            editor.setValue(value)
            editor.blockSignals(False)
        state.ranges[unit] = value
        self._refresh_group_bars(unit)
        attr = self._attribute()
        if attr is not None and attr.unit == unit:
            self._render_result()

    def _update_gain(self, value: float) -> None:
        state = self._state()
        if state is None or value <= 0:
            return
        value = max(0.5, min(10.0, round(value * 2) / 2))
        if self.gain_editor.value() != value:
            self.gain_editor.blockSignals(True)
            self.gain_editor.setValue(value)
            self.gain_editor.blockSignals(False)
        state.display_gain = value
        # Only selected Map raster/clipping changes; NO Bar value/ROI mutation.
        self._render_result()

    def _render_empty(self) -> None:
        self.image_export_action.setEnabled(False)
        self.report_export_action.setEnabled(False)
        for view, name in zip(self._views, ("Image A", "Image B", "Map"), strict=True):
            scene = QGraphicsScene(view)
            scene.addText(f"{name}\nNo result loaded")
            view.setScene(scene)
        self.official_label.setText("Full-pair comparison: —")
        self.detail_context.setText("DETAILS · select an attribute")
        self.roi_label.setText("ROI: none")
        self.roi_brief_label.setText("ROI: none")
        self._sync_chart_scope()
        self.range_editor.setEnabled(False)
        self.gain_editor.setEnabled(False)
        self.clamp_label.setText("Map: unavailable")
        self.pair_summary.setText("No result loaded")
        self.fit_action.setEnabled(False)

    def _render_result(self) -> None:
        if self._active_id is None:
            self._render_empty()
            return
        result = self._results[self._active_id]
        state = self._state()
        attr = self._attribute()
        if state is None or attr is None:
            return
        limit = self._display_range(attr, state)
        self._refresh_group_bars(attr.unit)
        # Unit controls are always visible; gain changes only the current Map.
        editor = self._range_editors.get(attr.unit)
        if editor is not None and editor.value() != limit:
            editor.blockSignals(True)
            editor.setValue(limit)
            editor.blockSignals(False)

        # Attribute and color-range changes do not rebuild three Qt scenes.
        # Recreate only when the actual result identity changes.
        new_result = self._scene_result_id != result.result_id
        if new_result:
            if self._source_result_id != result.result_id:
                images: list[QPixmap | None] = []
                for source in (result.source_a, result.source_b):
                    image = (
                        QImage(str(source)) if source is not None and source.is_file() else QImage()
                    )
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
            self._candidate_overlay_items = []
            for i, view in enumerate(self._views):
                view._muted = True
                old_scene = view.scene()
                scene = QGraphicsScene(view)
                scene.setSceneRect(QRectF(0, 0, result.image_width, result.image_height))
                scene.setBackgroundBrush(QColor(TOKENS.workspace_background))
                if i < 2:
                    pixmap = self._source_pixmaps[i]
                    if pixmap is None:
                        note = scene.addText(
                            "Source unavailable\nNumeric/spatial analysis retained"
                        )
                        note.setDefaultTextColor(QColor(TOKENS.text_secondary))
                        note.setFlag(
                            QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True
                        )
                        note.setPos(result.image_width * 0.03, result.image_height * 0.03)
                    else:
                        scene.addPixmap(pixmap)
                else:
                    # Persistent Map layer; only its pixels/declared grid transform
                    # change when the selected Attribute or display range changes.
                    self._map_item = scene.addPixmap(QPixmap())
                    self._map_item.setTransformationMode(Qt.TransformationMode.FastTransformation)
                    self._map_placeholder = scene.addText("Spatial map unavailable")
                    self._map_placeholder.setDefaultTextColor(QColor(TOKENS.text_secondary))
                    self._map_placeholder.setFlag(
                        QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True
                    )
                    self._map_placeholder.setPos(
                        result.image_width * 0.03, result.image_height * 0.03
                    )
                    # Block grid: never interpolate cell values into fake 4K detail.
                    view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
                roi_pen = QPen(QColor(255, 205, 0), 2)
                roi_pen.setCosmetic(True)
                overlay = scene.addRect(QRectF(), roi_pen)
                overlay.setZValue(100)
                overlay.setVisible(False)
                self._roi_items.append(overlay)
                proposal_layers: list[tuple[QGraphicsRectItem, QGraphicsTextItem]] = []
                for number, tone in enumerate(("#e0a84f", "#4aa3df", "#aeb4bc"), start=1):
                    pen = QPen(QColor(tone), 2)
                    pen.setCosmetic(True)
                    hotspot = scene.addRect(QRectF(), pen)
                    hotspot.setZValue(80)
                    hotspot.hide()
                    annotation = scene.addText(f"ROI #{number}")
                    annotation.setDefaultTextColor(QColor(tone))
                    annotation.setFlag(
                        QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True
                    )
                    annotation.setZValue(81)
                    annotation.hide()
                    proposal_layers.append((hotspot, annotation))
                self._candidate_overlay_items.append(proposal_layers)
                view.setScene(scene)
                if old_scene is not None:
                    old_scene.deleteLater()
            self._scene_result_id = result.result_id
            self._rendering = False
            for view in self._views:
                view._muted = False

        self._refresh_map(attr, limit)
        self.image_export_action.setEnabled(
            attr.spatial is not None or any(image is not None for image in self._source_pixmaps)
        )
        self.report_export_action.setEnabled(self.image_export_action.isEnabled())
        self._pane_labels[0].setText(f"IMAGE A  ·  {result.source_a_label}")
        self._pane_labels[1].setText(f"IMAGE B  ·  {result.source_b_label}")
        if attr.spatial is None:
            self._pane_labels[2].setText(f"RELATIVE MAP  ·  {attr.label}  ·  unavailable")
        else:
            grid = attr.spatial
            self._pane_labels[2].setText(
                f"RELATIVE MAP  ·  {attr.label}  ·  "
                f"{grid.block_width:g}×{grid.block_height:g} px cells"
            )
        if new_result:
            self._draw_roi(state.roi)
            if (
                state.scale is not None
                and state.center_x is not None
                and state.center_y is not None
            ):
                self._fit_pending_result_id = None
                for view in self._views:
                    view.apply_navigation(state.scale, state.center_x, state.center_y)
            else:
                self._fit_attempts_remaining = 8
                self._fit_pending_result_id = result.result_id
                self._queue_initial_fit()
        else:
            # The selected map may become absent. Keep A/B item identity, viewport,
            # ROI geometry, and active keyboard selection stable.
            if len(self._roi_items) == 3:
                self._roi_items[2].setVisible(state.roi is not None and attr.spatial is not None)
        self._render_inspector(attr, limit)
        self._sync_top_cards()
        self._request_spatial_candidates()
        self._sync_spatial_selection()

    def _refresh_map(self, attr: AttributeDisplay, limit: float) -> None:
        """Update one persistent map pixmap and its validity placeholder."""

        if self._map_item is None or self._map_placeholder is None:
            return
        state = self._state()
        effective = spatial_display_half_range(
            limit, state.display_gain if state is not None else 1.0
        )
        pixmap = _map_pixmap(attr, effective)
        grid = attr.spatial
        available = pixmap is not None and grid is not None
        if available and pixmap is not None and grid is not None:
            self._map_item.setPixmap(pixmap)
            self._map_item.setPos(grid.origin_x, grid.origin_y)
            self._map_item.setTransform(QTransform().scale(grid.block_width, grid.block_height))
        else:
            self._map_item.setPixmap(QPixmap())
        self._map_item.setVisible(available)
        self._map_placeholder.setVisible(not available)

    def _spatial_key(self) -> tuple[str, str, int] | None:
        state = self._state()
        if state is None or self._active_id is None:
            return None
        return (
            self._active_id,
            state.attribute_id,
            int(self.spatial_panel.stride_selector.currentData()),
        )

    def _spatial_dock_visibility_changed(self, visible: bool) -> None:
        if visible:
            # Re-dock a saved floating window from a disconnected monitor.
            dock = self.spatial_dock
            if dock.isFloating() and not any(
                dock.frameGeometry().intersects(screen.availableGeometry())
                for screen in QApplication.screens()
            ):
                dock.setFloating(False)
                self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
            QTimer.singleShot(0, self._settle_dock_initial_height)
            self._request_spatial_candidates()
        else:
            self._draw_candidate_overlays()

    def _hotspot_overlay_toggled(self, enabled: bool) -> None:
        self._draw_candidate_overlays()
        if enabled:
            # Marker-only workflow lazily computes without opening the panel.
            self._request_spatial_candidates()

    def _request_spatial_candidates(self, _stride: int = 128) -> None:
        """Always synchronize scene overlays before the visibility-gated scan."""

        # Neither a hidden panel nor inactive markers should scan on startup.
        # Previously computed overlays must still be invalidated on Attribute
        # changes even while both user-controlled surfaces remain hidden.
        self._draw_candidate_overlays()
        if not self.isVisible() or (
            self.spatial_dock.isHidden() and not self.hotspot_overlay_action.isChecked()
        ):
            return
        key = self._spatial_key()
        attr = self._attribute()
        if key is None or attr is None:
            return
        if self._spatial_displayed == key:
            return
        if self._spatial_pending is not None and self._spatial_pending != key:
            # Cancel/forget the old task even when the new key is cached.
            self._spatial_timer.stop()
            previous = self._spatial_future
            if previous is not None and not previous.done():
                previous.cancel()
            self._spatial_future = None
            self._spatial_pending = None
        if key in self._spatial_cache:
            self._present_spatial_candidates(key, self._spatial_cache[key])
            return
        if self._spatial_pending == key:
            return
        previous = self._spatial_future
        if previous is not None and not previous.done():
            previous.cancel()
        self._spatial_pending = key
        self._spatial_displayed = None
        self.spatial_panel.set_busy(f"Locating local differences · {attr.label}…")
        self._draw_candidate_overlays()
        if attr.spatial is None:
            self._present_spatial_candidates(key, ())
            return
        self._spatial_future = self._spatial_executor.submit(
            find_spatial_candidates, attr, stride=key[2]
        )
        self._spatial_timer.start()

    def _finish_spatial_if_ready(self) -> None:
        future = self._spatial_future
        key = self._spatial_pending
        if future is None or key is None or not future.done():
            return
        self._spatial_timer.stop()
        self._spatial_future = None
        self._spatial_pending = None
        if key != self._spatial_key():
            return
        try:
            candidates = future.result()
        except (ValueError, RuntimeError):
            self.spatial_panel.set_unavailable(
                "Spatial scan unavailable: unsupported geometry or resource budget."
            )
            self._draw_candidate_overlays()
            return
        self._spatial_cache[key] = candidates
        self._present_spatial_candidates(key, candidates)

    def _present_spatial_candidates(
        self, key: tuple[str, str, int], candidates: tuple[SpatialCandidate, ...]
    ) -> None:
        if key != self._spatial_key():
            return
        attr = self._attribute()
        if attr is None:
            return
        self._spatial_pending = None
        self._spatial_timer.stop()
        self._spatial_displayed = key
        self.spatial_panel.populate(candidates, self._source_pixmaps, attr.unit)
        self._sync_spatial_selection()
        self._draw_candidate_overlays()

    def _select_spatial_candidate(self, index: int) -> None:
        key = self._spatial_key()
        if key is None or self._spatial_displayed != key:
            return
        candidates = self._spatial_cache.get(key, ())
        if index < 0 or index >= len(candidates):
            return
        candidate = candidates[index]
        self._set_roi(*candidate.roi)
        # One pixel-consistent zoom for all A/Map/B panes, centered on ROI.
        available_width = min(view.viewport().width() for view in self._views)
        available_height = min(view.viewport().height() for view in self._views)
        zoom = max(
            1e-8,
            min(
                32.0,
                0.88 * min(available_width / candidate.width, available_height / candidate.height),
            ),
        )
        state = self._state()
        if state is not None:
            state.scale = zoom
            state.center_x = candidate.x + candidate.width / 2
            state.center_y = candidate.y + candidate.height / 2
            self._fit_pending_result_id = None
            for view in self._views:
                view.apply_navigation(zoom, state.center_x, state.center_y)
        self._draw_candidate_overlays()

    def _sync_spatial_selection(self) -> None:
        """A card is checked only when its ROI matches the current source ROI.

        No index is persisted across stride changes: candidates can have a
        different position/order even when their visual rank is unchanged.
        Manual ROI editing and Clear ROI use this same reconciliation.
        """

        key = self._spatial_key()
        candidates = (
            self._spatial_cache.get(key, ())
            if key is not None and key == self._spatial_displayed
            else ()
        )
        roi = self.current_roi
        index = (
            next(
                (i for i, candidate in enumerate(candidates) if roi == candidate.roi),
                None,
            )
            if roi is not None
            else None
        )
        self.spatial_panel.mark_selected(index)

    def _draw_candidate_overlays(self, _checked: bool = False) -> None:
        key = self._spatial_key() if hasattr(self, "spatial_panel") else None
        candidates = (
            self._spatial_cache.get(key, ())
            if key is not None and key == self._spatial_displayed
            else ()
        )
        attr = self._attribute()
        show = (
            self.hotspot_overlay_action.isChecked()
            if hasattr(self, "hotspot_overlay_action")
            else False
        )
        for i, layers in enumerate(self._candidate_overlay_items):
            has_source = (
                self._source_pixmaps[i] is not None
                if i < 2
                else attr is not None and attr.spatial is not None
            )
            for number, (rect_item, text_item) in enumerate(layers):
                visible = show and has_source and number < len(candidates)
                rect_item.setVisible(False)
                text_item.setVisible(False)
                if visible:
                    candidate = candidates[number]
                    rect_item.setRect(QRectF(*candidate.roi))
                    text_item.setPos(candidate.x + 3, candidate.y + 3)
                    rect_item.setVisible(True)
                    text_item.setVisible(True)

    def _shutdown_spatial_worker(self) -> None:
        self._spatial_timer.stop()
        pending = self._spatial_future
        self._spatial_pending = None
        self._spatial_future = None
        if pending is not None:
            pending.cancel()
        self._spatial_executor.shutdown(wait=False, cancel_futures=True)

    def _fit_pair(self) -> None:
        """Explicitly reset all three linked views to a post-layout full fit."""

        state = self._state()
        if state is None or self._active_id is None:
            return
        state.scale = state.center_x = state.center_y = None
        self._fit_attempts_remaining = 8
        self._fit_pending_result_id = self._active_id
        self._queue_initial_fit()

    def _set_pane_order(self) -> None:
        """Reorder only visual containers, keeping the A/B science immutable."""

        indices = (1, 2, 0) if self._sources_swapped else (0, 2, 1)
        for visual_index, semantic_index in enumerate(indices):
            self._image_split.insertWidget(visual_index, self._pane_wrappers[semantic_index])

    def _swap_sources(self) -> None:
        """Toggle A/Map/B placement without mutating A/B data or zoom state."""

        state = self._state()
        self._remember_navigation()
        self._rendering = True
        for view in self._views:
            view._muted = True
        try:
            self._sources_swapped = not self._sources_swapped
            self._set_pane_order()
        finally:
            for view in self._views:
                view._muted = False
            self._rendering = False
        if (
            state is not None
            and state.scale is not None
            and state.center_x is not None
            and state.center_y is not None
        ):
            for view in self._views:
                view.apply_navigation(state.scale, state.center_x, state.center_y)

    def _display_range(self, attr: AttributeDisplay, state: _ResultViewState) -> float:
        """Use one range when the adapter declared comparable official units."""

        if self._active_id is None:
            return attr.chart_axis_range or attr.fixed_range
        result = self._results[self._active_id]
        return state.ranges.get(attr.unit, self._unit_default_range(result, attr.unit))

    def _render_inspector(self, attr: AttributeDisplay, limit: float) -> None:
        self.detail_context.setText(f"DETAILS · {attr.label}  ({attr.unit})")
        if attr.official_value is None:
            text = attr.official_availability.upper() + " (not zero)"
        else:
            text = f"{attr.official_value:+.4f} {attr.unit} ({attr.official_availability})"
        orientation = "+A / −B quality" if attr.quality_oriented else "neutral / no winner inferred"
        self.official_label.setText(f"Full-pair comparison: {text}\n{orientation}")
        roi = self.current_roi
        if roi is None:
            self.roi_brief_label.setText("ROI: none")
            self.roi_label.setText("ROI: none\nShift+drag on A, Map or B · Esc clears")
        else:
            x, y, width, height = roi
            self.roi_brief_label.setText(
                f"ROI: ({int(x)}, {int(y)})  ·  {int(width)}×{int(height)} px"
            )
            description = (
                f"ROI source (x, y, w, h): "
                f"({int(x)}, {int(y)}, {int(width)}, {int(height)}) px\n"
                f"Selected source area: {int(width * height):,} px²"
            )
            if attr.spatial is None:
                self.roi_label.setText(
                    description + "\nGRID-DERIVED spatial statistics unavailable"
                )
            else:
                stats = roi_statistics(attr.spatial, roi)
                value = "missing" if stats.mean is None else f"{stats.mean:+.4f} {attr.unit}"
                self.roi_label.setText(
                    f"{description}\nGrid-derived ROI estimate: {value} (not full-pair)\n"
                    f"Grid valid area: {stats.valid_area:,.0f} / "
                    f"{stats.roi_area:,.0f} px²  ·  {stats.valid_coverage:.1%} coverage"
                )
        if attr.spatial is None:
            self.clamp_label.setText("Map missing (not zero)")
        else:
            grid = attr.spatial
            state = self._state()
            gain = state.display_gain if state is not None else 1.0
            clipped, total = clipped_cells(grid, spatial_display_half_range(limit, gain))
            pct = 0.0 if total == 0 else (clipped / total)
            invalid = grid.values.size - total
            self.clamp_label.setText(
                f"Group ±{limit:g} {attr.unit} · Map gain ×{gain:g}\n"
                f"{map_polarity_legend(attr)}\n"
                f"Cells: {grid.rows}×{grid.columns} • "
                f"{grid.block_width:g}×{grid.block_height:g} source px, nearest\n"
                f"Invalid: {invalid} transparent cells (not zero)\n"
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
        if state is not None:
            state.chart_scope = "full_pair"
        if state is not None:
            # A cleared ROI is a fresh interaction cycle. Never retain the
            # previous manual Full override into a brand-new ROI selection.
            state.scope_user_override = False
        self._sync_chart_scope()
        self._refresh_all_group_bars()
        self._draw_roi(None)
        self._sync_spatial_selection()
        attr = self._attribute()
        if attr is not None and state is not None:
            self._render_inspector(attr, self._display_range(attr, state))

    def _set_roi(self, x: float, y: float, w: float, h: float) -> None:
        if self._active_id is None:
            return
        result = self._results[self._active_id]
        # A dragged source ROI includes every touched integer pixel. Round the
        # start down and exclusive end up; preserve clipped image boundaries.
        left = max(0, min(int(np.floor(x)), result.image_width))
        top = max(0, min(int(np.floor(y)), result.image_height))
        right = max(left, min(int(np.ceil(x + w)), result.image_width))
        bottom = max(top, min(int(np.ceil(y + h)), result.image_height))
        if right <= left or bottom <= top:
            return
        state = self._state()
        if state is None:
            return
        first_roi = state.roi is None
        state.roi = (left, top, right - left, bottom - top)
        if first_roi and not state.scope_user_override:
            state.chart_scope = "roi_grid"
        self._sync_chart_scope()
        self._refresh_all_group_bars()
        self._draw_roi(state.roi)
        self._sync_spatial_selection()
        attr = self._attribute()
        if attr is not None:
            self._render_inspector(attr, self._display_range(attr, state))

    def _update_range(self, value: float) -> None:
        """Compatibility entrypoint for an explicit selected-unit range edit."""

        attr = self._attribute()
        if attr is not None:
            self._update_group_range(attr.unit, value)

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
        # Startup presents only A/B/Map. The optional candidates dock and
        # worker are activated by View > Hotspot Candidates View or by markers.
        self._queue_initial_fit()
        self._request_spatial_candidates()

    def _settle_dock_initial_height(self) -> None:
        if (
            not self.isVisible()
            or self.height() > 850
            or self.spatial_dock.isHidden()
            or self.spatial_dock.isFloating()
        ):
            return
        if self.inspector_tabs.height() < 380:
            # Request a compact first FHD dock while allowing operators to
            # enlarge it later; exact Inspector height depends on Qt layout minima.
            self.resizeDocks([self.spatial_dock], [175], Qt.Orientation.Vertical)

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

    def _export_csv_from_dialog(self) -> None:
        """Export scientific measurements, not a portable result or pair score for an ROI."""

        if self._active_id is None:
            return
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export IQA measurements CSV",
            "",
            "CSV files (*.csv)",
        )
        if not filename:
            return
        destination = Path(filename)
        if not destination.suffix:
            destination = destination.with_suffix(".csv")
        try:
            write_measurements_csv(
                self._results[self._active_id],
                self.current_roi,
                destination,
            )
        except (OSError, ValueError):
            self.statusBar().showMessage("CSV export failed; the IQA result was not changed.")
            return
        self.statusBar().showMessage(
            "CSV exported: full-pair values and grid-derived ROI estimates remain distinct."
        )

    def _export_png_from_dialog(self) -> None:
        """Export labelled source-pixel images, never a viewport screenshot."""

        if self._active_id is None:
            return
        result = self._results[self._active_id]
        attribute, state = self._attribute(), self._state()
        if attribute is None or state is None:
            return
        if attribute.spatial is None and not any(
            image is not None for image in self._source_pixmaps
        ):
            self.statusBar().showMessage("PNG export unavailable: no source RGB or spatial Map.")
            return
        scope: ExportScope = "full"
        if state.roi is not None:
            choices = ["Full image", "Active ROI", "Both"]
            selected, accepted = QInputDialog.getItem(
                self, "Export IQA images", "Source-pixel coverage", choices, 2, False
            )
            if not accepted:
                return
            if selected == "Full image":
                scope = "full"
            elif selected == "Active ROI":
                scope = "roi"
            else:
                scope = "both"
        parent = QFileDialog.getExistingDirectory(
            self, "Choose parent folder for a new IQA image export"
        )
        if not parent:
            return
        destination = export_folder(Path(parent), result.result_id)
        images = tuple(
            pixmap.toImage() if pixmap is not None else None for pixmap in self._source_pixmaps
        )
        try:
            write_visual_pngs(
                result,
                attribute,
                (images[0], images[1]),
                destination,
                scope=scope,
                roi=state.roi,
                display_range=self._display_range(attribute, state),
                display_gain=state.display_gain,
            )
        except (OSError, ValueError, KeyError):
            self.statusBar().showMessage(
                "PNG export failed or destination already exists; IQA result unchanged."
            )
            return
        self.statusBar().showMessage(
            "PNG images and export_info.json saved; map colors are display-only."
        )

    def _export_html_from_dialog(self) -> None:
        """Export offline HTML with fixed local PNG assets; never a portable result."""

        if self._active_id is None:
            return
        result = self._results[self._active_id]
        attribute, state = self._attribute(), self._state()
        if attribute is None or state is None:
            return
        if attribute.spatial is None and not any(
            image is not None for image in self._source_pixmaps
        ):
            self.statusBar().showMessage("HTML report unavailable: no source RGB or spatial Map.")
            return

        scope: ExportScope = "full"
        if state.roi is not None:
            choices = ["Full image", "Active ROI", "Both"]
            selected, accepted = QInputDialog.getItem(
                self, "Export IQA HTML report", "Source-pixel coverage", choices, 2, False
            )
            if not accepted:
                return
            if selected == "Full image":
                scope = "full"
            elif selected == "Active ROI":
                scope = "roi"
            else:
                scope = "both"
        parent = QFileDialog.getExistingDirectory(
            self, "Choose parent folder for a new offline IQA HTML report"
        )
        if not parent:
            return
        destination = report_folder(Path(parent), result.result_id)
        images = tuple(
            pixmap.toImage() if pixmap is not None else None for pixmap in self._source_pixmaps
        )
        try:
            write_html_report(
                result,
                attribute,
                (images[0], images[1]),
                destination,
                scope=scope,
                roi=state.roi,
                display_range=self._display_range(attribute, state),
                display_gain=state.display_gain,
            )
        except (OSError, ValueError, KeyError, TypeError):
            self.statusBar().showMessage(
                "HTML report failed or destination exists; IQA result unchanged."
            )
            return
        self.statusBar().showMessage(
            "Offline HTML report exported: index.html plus local PNG/JSON assets."
        )

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
        self._spatial_timer.stop()
        self._spatial_displayed = None
        pending = self._spatial_future
        if pending is not None and not pending.done():
            pending.cancel()
        self._spatial_future = None
        self._spatial_pending = None
        self._settings_factory().setValue("analysis_window_spatial_dock_state", self.saveState())
        for view in self._views:
            view.cancel_roi_drag()
            view._set_roi_cursor(False)
        self._remember_navigation()
        self._settings_factory().setValue("analysis_window_geometry", self.saveGeometry())
        super().closeEvent(event)


class AnalysisWindowManager:
    """Own exactly one independent AnalysisWindow; no Base or worker ownership."""

    def __init__(
        self,
        *,
        settings_factory: IqaSettingsFactory | None = None,
        load: ResultLoader | None = None,
        save: ResultSaver | None = None,
    ) -> None:
        self._window: AnalysisWindow | None = None
        self._settings_factory = settings_factory or default_iqa_settings
        self._load = load
        self._save = save
        self._closed = False

    @property
    def window(self) -> AnalysisWindow | None:
        return self._window

    def show(self, result: AnalysisResult | None = None) -> AnalysisWindow:
        if self._closed:
            raise RuntimeError("analysis manager is shut down")
        if self._window is None:
            self._window = AnalysisWindow(settings_factory=self._settings_factory)
            self._window.install_file_handlers(load=self._load, save=self._save)
            self._place_first_window(self._window, self._settings_factory)
        if result is not None:
            self._window.present_result(result)
        self._window.show()
        self._window.raise_()
        return self._window

    @staticmethod
    def _place_first_window(
        window: AnalysisWindow,
        settings_factory: IqaSettingsFactory = default_iqa_settings,
    ) -> None:
        screens = QApplication.screens()
        if not screens:
            return
        stored = settings_factory().value("analysis_window_geometry")
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
            window._shutdown_spatial_worker()
            window._spatial_dock_chrome.quiesce_pending_callbacks()
            window.spatial_dock_title.quiesce_pending_callbacks()
            window.close()
            # Normalize native floating dock before Qt destroys the owner;
            # the Plot workspace uses the same bounded shutdown sequence.
            if window.spatial_dock.isFloating():
                if window.spatial_dock.isMaximized():
                    window.spatial_dock.showNormal()
                window.spatial_dock.hide()
                window.addDockWidget(
                    window.spatial_dock_title.shutdown_dock_area(),
                    window.spatial_dock,
                )
                window.spatial_dock.setFloating(False)
            window.deleteLater()
