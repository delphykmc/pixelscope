from __future__ import annotations

import csv
from contextlib import suppress
from dataclasses import replace
from functools import partial
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import numpy as np
import pyqtgraph as pg
from numpy.typing import NDArray
from PySide6.QtCore import (
    QModelIndex,
    QPersistentModelIndex,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QKeySequence,
    QPainter,
    QPen,
    QShortcut,
    QStandardItemModel,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pixelscope.core.analysis_latency_trace import PhaseTimer as AnalysisPhaseTimer
from pixelscope.core.bayer import analyze_bayer_roi
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.metric_presentation import (
    FOCUSED_METRICS,
    PERCENTILE_METRICS,
    STATISTICS_METRICS,
    StatisticsPivot,
    build_statistics_pivot,
)
from pixelscope.core.review_analysis import (
    AnalysisMeasurementV1,
    AnalysisSeriesV1,
    AnalysisSourceV1,
    PresentedAnalysisTokenV1,
    freeze_series_values,
    measurement,
)
from pixelscope.core.review_analysis_sources import native_profile_signature, snapshot_source
from pixelscope.core.roi import RoiAnalysisResult, RoiBounds, analyze_roi
from pixelscope.core.statistics import ImageStatistics
from pixelscope.ui.design_tokens import TOKENS, channel_button_style
from pixelscope.ui.plot_colors import channel_color, comparison_pen
from pixelscope.ui.plot_text import coordinate_header, middle_elide, plot_number
from pixelscope.ui.responsive_control_layout import ElidingContextLabel, ResponsiveControlLayout
from pixelscope.workers.task_worker import TaskError, TaskWorker
from pixelscope.workers.thread_pools import analysis_thread_pool


class KiloAxisItem(pg.AxisItem):  # type: ignore[misc]
    """Count axis that abbreviates thousands with a K suffix."""

    def tickStrings(  # noqa: N802
        self, values: list[float], scale: float, spacing: float
    ) -> list[str]:
        del scale, spacing
        return [f"{value / 1000:g}K" if abs(value) >= 1000 else f"{value:g}" for value in values]


class ImageGroupSeparatorDelegate(QStyledItemDelegate):
    """Draw a subtle boundary before each new image's channel rows."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._separator_rows: set[int] = set()

    @property
    def separator_rows(self) -> frozenset[int]:
        return frozenset(self._separator_rows)

    def set_separator_rows(self, rows: set[int]) -> None:
        self._separator_rows = set(rows)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        super().paint(painter, option, index)
        if index.row() not in self._separator_rows:
            return
        rect = cast(Any, option).rect
        painter.save()
        painter.setPen(QPen(QColor(TOKENS.border), 2))
        y = rect.top() + 1
        painter.drawLine(rect.left(), y, rect.right(), y)
        painter.restore()


def comparison_labels(documents: list[ImageDocument]) -> list[str]:
    """Return folder-qualified labels so duplicate basenames remain distinct."""

    return [
        f"{document.source_path.parent.name} / {document.display_name}"
        if document.source_path is not None
        else document.display_name
        for document in documents
    ]


def automatic_histogram_spec(
    document: ImageDocument,
    requested_bins: int | None = None,
) -> tuple[int, tuple[float, float] | None]:
    """Select UI histogram bins while preserving the document's native code range."""

    source = document.source
    if source is None:
        raise ValueError("histogram requires a loaded document")
    if requested_bins is not None and requested_bins not in (256, 1024, 4096):
        raise ValueError(f"unsupported histogram bin count: {requested_bins}")
    effective_depth = min(max(document.bit_depth, 1), 16)
    native_bins = 1 << effective_depth
    bins = min(native_bins, 4096) if requested_bins is None else requested_bins
    if np.issubdtype(source.dtype, np.unsignedinteger):
        return bins, (0.0, float(native_bins))
    if np.issubdtype(source.dtype, np.signedinteger):
        limit = 1 << (effective_depth - 1)
        return bins, (float(-limit), float(limit))
    return bins, None


def histogram_display_values(
    counts: NDArray[np.generic],
    mode: str,
) -> NDArray[np.float64]:
    """Transform histogram counts for display without changing cached raw counts."""

    values = counts.astype(np.float64, copy=False)
    if mode == "Normalized":
        total = float(np.sum(values))
        return values / total if total > 0 else values
    if mode == "Log count":
        return np.asarray(
            np.log10(values + 1.0),
            dtype=np.float64,
        )
    return values


class ComparisonAnalysisPanel(QWidget):
    """Row-oriented per-channel statistics and channel-faithful histograms."""

    _COLUMNS = (
        "Id",
        "Ch",
        "Min",
        "Max",
        "Mean",
        "Std",
        "P1",
        "P50",
        "P99",
    )
    scope_changed = Signal()
    roi_apply_requested = Signal(object)
    roi_clear_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._documents: list[ImageDocument] = []
        self._bounds: RoiBounds | None = None
        self._active_roi_bounds: RoiBounds | None = None
        self._worker: TaskWorker | None = None
        self._request_signature: tuple[object, ...] = ()
        self._completed_signature: tuple[object, ...] = ()
        self._analysis_request_id = str(uuid4())
        self._analysis_request_epoch = 0
        self._presented_analysis_token: PresentedAnalysisTokenV1 | None = None
        self._presented_histogram_token: PresentedAnalysisTokenV1 | None = None
        self._histogram_presentation_epoch = 0
        self._histogram_presentation_signature: tuple[object, ...] = ()
        self._token_request_signature: tuple[object, ...] = ()
        # W09 may inject durable Review keys. Until then these are provisional
        # Review-local UUIDs, never runtime document IDs or display aliases.
        self._analysis_source_keys: dict[str, str] = {}
        self._histogram_specs: list[tuple[int, tuple[float, float] | None]] = []
        self.last_results: tuple[RoiAnalysisResult, ...] = ()
        self._pivot: StatisticsPivot | None = None
        self._pool = analysis_thread_pool()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(140)
        self._refresh_timer.timeout.connect(self.refresh)  # type: ignore[attr-defined]

        self.status = QLabel("No images selected")
        self.busy = QProgressBar()
        self.busy.setRange(0, 0)
        self.busy.setTextVisible(False)
        self.busy.setFixedHeight(4)
        self.busy.hide()
        self.activity = QWidget()
        activity_layout = QVBoxLayout(self.activity)
        activity_layout.setContentsMargins(0, 0, 0, 0)
        activity_layout.setSpacing(1)
        # Reserve the status/progress rail permanently. QProgressBar may be
        # hidden when idle, but must never resize the statistics table above.
        self.status.setFixedHeight(self.status.sizeHint().height())
        self.activity.setFixedHeight(self.status.height() + self.busy.height() + 1)
        activity_layout.addWidget(self.status)
        activity_layout.addWidget(self.busy)
        activity_layout.addStretch(1)

        self.roi_label = ElidingContextLabel("")
        self.roi_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.roi_x_input = QSpinBox()
        self.roi_y_input = QSpinBox()
        self.roi_width_input = QSpinBox()
        self.roi_height_input = QSpinBox()
        for name, control in (
            ("X", self.roi_x_input),
            ("Y", self.roi_y_input),
            ("W", self.roi_width_input),
            ("H", self.roi_height_input),
        ):
            control.setRange(0 if name in ("X", "Y") else 1, 2_147_483_647)
            control.setFixedWidth(72)
            control.setAccelerated(True)
            control.setKeyboardTracking(False)
            control.setAccessibleName(f"ROI {name}")
            line_edit = control.lineEdit()
            if line_edit is not None:
                line_edit.returnPressed.connect(self._request_roi_apply)  # type: ignore[attr-defined]
        self.roi_apply_button = QPushButton("Apply")
        self.roi_apply_button.setToolTip("Apply X/Y/W/H as the shared ROI")
        self.roi_apply_button.setFixedWidth(64)
        self.roi_apply_button.clicked.connect(self._request_roi_apply)  # type: ignore[attr-defined]
        self.roi_clear_button = QPushButton("Clear")
        self.roi_clear_button.setToolTip("Clear the shared ROI (Esc)")
        self.roi_clear_button.setFixedWidth(64)
        self.roi_clear_button.clicked.connect(self.roi_clear_requested.emit)  # type: ignore[attr-defined]
        self.roi_editor = QWidget()
        self.roi_editor.setMinimumWidth(0)
        self.roi_editor.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        roi_editor_layout = ResponsiveControlLayout(
            self.roi_editor,
            spacing=TOKENS.spacing_xs,
        )
        self.roi_coordinate_labels: dict[str, QLabel] = {}
        for index, (name, control) in enumerate(
            (
                ("X", self.roi_x_input),
                ("Y", self.roi_y_input),
                ("W", self.roi_width_input),
                ("H", self.roi_height_input),
            )
        ):
            compact_row = 0 if index < 2 else 1
            label = QLabel(name)
            self.roi_coordinate_labels[name] = label
            roi_editor_layout.add_control(label, compact_row=compact_row)
            roi_editor_layout.add_control(control, compact_row=compact_row)
        roi_editor_layout.add_control(self.roi_apply_button, compact_row=0)
        roi_editor_layout.add_control(self.roi_clear_button, compact_row=1)
        self.region_scope = QComboBox()
        self.region_scope.addItems(("Full image", "Active ROI"))
        self.set_roi_available(False)
        self.region_scope.setFixedWidth(120)
        self.region_scope.currentIndexChanged.connect(  # type: ignore[attr-defined]
            lambda: self.scope_changed.emit()
        )
        self.channel_buttons: dict[str, QToolButton] = {}

        self.region_group = QGroupBox("1. Region")
        self.region_layout = QGridLayout(self.region_group)
        self.region_layout.setContentsMargins(10, 8, 10, 8)
        self.region_layout.setHorizontalSpacing(TOKENS.spacing_md)
        self.region_layout.setVerticalSpacing(TOKENS.spacing_sm)
        self.scope_label = QLabel("Scope")
        self.scope_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.region_layout.addWidget(self.scope_label, 0, 0)
        self.region_layout.addWidget(
            self.region_scope,
            0,
            1,
            alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )
        self.region_layout.addWidget(self.roi_label, 0, 2)
        self.region_layout.addWidget(self.roi_editor, 1, 0, 1, 3)
        self.region_layout.setColumnStretch(1, 1)
        self.region_layout.setColumnStretch(2, 1)
        self._sync_roi_editor()
        histogram_channel_label = QLabel("Channels")
        for name, color in (("R", "#ff3b30"), ("G", "#24b34b"), ("B", "#2684ff")):
            button = QToolButton()
            button.setText(name)
            button.setCheckable(True)
            button.setChecked(True)
            button.setStyleSheet(channel_button_style(color))
            button.toggled.connect(  # type: ignore[attr-defined]
                self._channels_changed
            )
            self.channel_buttons[name] = button

        self.image_summary = QTableWidget(0, 4)
        self.image_summary.setHorizontalHeaderLabels(("Id", "Image", "Bit depth", "Pixels"))
        summary_vertical_header = self.image_summary.verticalHeader()
        summary_vertical_header.hide()
        summary_vertical_header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.image_summary.setWordWrap(False)
        self.image_summary.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.image_summary.setAlternatingRowColors(True)
        self.image_summary.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.image_summary.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.image_summary.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        summary_header = self.image_summary.horizontalHeader()
        summary_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        summary_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        summary_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        summary_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.image_summary.setColumnWidth(0, 38)

        self.image_summary_group = QGroupBox("2. Images")
        image_summary_layout = QVBoxLayout(self.image_summary_group)
        image_summary_layout.setContentsMargins(6, 6, 6, 6)
        image_summary_layout.addWidget(self.image_summary)

        self.table = QTableWidget(0, len(self._COLUMNS))
        self.table.setHorizontalHeaderLabels(self._COLUMNS)
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setMinimumSectionSize(38)
        self.table.setColumnWidth(0, 38)
        self.table.setColumnWidth(1, 38)
        self.statistics_delegate = ImageGroupSeparatorDelegate(self.table)
        self.table.setItemDelegate(self.statistics_delegate)
        copy_shortcut = QShortcut(QKeySequence.StandardKey.Copy, self.table)
        copy_shortcut.activated.connect(  # type: ignore[attr-defined]
            self.copy_selection
        )

        self.statistics_group = QGroupBox("3. Channel statistics")
        statistics_layout = QVBoxLayout(self.statistics_group)
        statistics_layout.setContentsMargins(6, 6, 6, 6)
        statistics_layout.setSpacing(4)
        self.statistics_view = QComboBox()
        self.statistics_view.addItems(("Raw", "Pivot"))
        self.pivot_channel = QComboBox()
        self.pivot_channel.addItem("All")
        self.pivot_metrics = QComboBox()
        self.pivot_metrics.addItems(("Mean / Std / P99", "All metrics", "Percentiles"))
        self.pivot_reference = QComboBox()
        self.pivot_reference.addItem("No reference", None)
        self.pivot_reference.setToolTip(
            "Statistics-only Reference. Independent of W05 Primary and Difference A/B roles."
        )
        self.pivot_delta = QComboBox()
        self.pivot_delta.addItems(("Values", "Absolute Δ", "Relative Δ (%)"))
        self.pivot_delta.setToolTip("Delta = Target - Reference; relative = Δ / |Reference| × 100")
        self.pivot_export_button = QPushButton("Export Pivot CSV…")
        self.pivot_export_button.setToolTip(
            "High-precision typed Pivot CSV; existing Raw Statistics CSV is unchanged"
        )
        self.pivot_table = QTableWidget(0, 0)
        self.pivot_table.verticalHeader().hide()
        self.pivot_table.setWordWrap(False)
        self.pivot_table.setAlternatingRowColors(True)
        self.pivot_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.pivot_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self.pivot_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.pivot_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.pivot_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.pivot_table.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self.pivot_export_button.setEnabled(False)
        pivot_copy_shortcut = QShortcut(QKeySequence.StandardKey.Copy, self.pivot_table)
        pivot_copy_shortcut.activated.connect(self.copy_selection)  # type: ignore[attr-defined]

        statistics_controls_widget = QWidget()
        statistics_controls = ResponsiveControlLayout(
            statistics_controls_widget, spacing=TOKENS.spacing_xs
        )
        for row_index, title, combo in (
            (0, "View", self.statistics_view),
            (0, "Channel", self.pivot_channel),
            (0, "Metrics", self.pivot_metrics),
            (1, "Pivot reference", self.pivot_reference),
            (1, "Delta", self.pivot_delta),
        ):
            statistics_controls.add_control(QLabel(title), compact_row=row_index)
            statistics_controls.add_control(combo, compact_row=row_index)
            combo.setMinimumWidth(0)
            combo.setMaximumWidth(170)
        statistics_controls.add_control(self.pivot_export_button, compact_row=1)
        statistics_layout.addWidget(statistics_controls_widget)
        self.statistics_stack = QStackedWidget()
        self.statistics_stack.addWidget(self.table)
        self.statistics_stack.addWidget(self.pivot_table)
        statistics_layout.addWidget(self.statistics_stack, 1)
        self.statistics_view.currentIndexChanged.connect(self._statistics_view_changed)  # type: ignore[attr-defined]
        for combo in (
            self.pivot_channel,
            self.pivot_metrics,
            self.pivot_reference,
            self.pivot_delta,
        ):
            combo.currentIndexChanged.connect(self._refresh_pivot)  # type: ignore[attr-defined]
        self.pivot_export_button.clicked.connect(self._prompt_pivot_export)  # type: ignore[attr-defined]

        self.histogram_grid = QWidget()
        self.histogram_layout = QGridLayout(self.histogram_grid)
        self.histogram_layout.setContentsMargins(0, 0, 0, 0)
        self.histogram_layout.setSpacing(3)
        self.plots: list[pg.PlotWidget] = []
        self.legends: list[pg.LegendItem] = []
        self._histogram_series: list[
            list[tuple[int, str, NDArray[np.float64], NDArray[np.float64]]]
        ] = [[] for _index in range(6)]
        self._histogram_hover_lines: list[pg.InfiniteLine | None] = [None] * 6
        self._histogram_hover_texts: list[pg.TextItem | None] = [None] * 6
        self._histogram_mouse_callbacks: list[Any] = []
        self._histogram_resources_disposed = False
        self._arranged_histogram_count = 0
        self._semantics_delegate: Any | None = None
        self.workflow_histogram_hint_controller: Any | None = None
        for plot_index in range(6):
            plot = pg.PlotWidget(
                parent=self.histogram_grid,
                axisItems={"left": KiloAxisItem(orientation="left")},
            )
            plot.setLabel("left", "Count")
            plot.setLabel("bottom", "Pixel value")
            plot.showGrid(x=True, y=True, alpha=0.25)
            plot.getViewBox().setDefaultPadding(0.08)
            # Auto-sized tick labels can change PlotItem geometry on the next
            # Paint. Fix axis gutters before any data or tick text arrives.
            plot.getPlotItem().getAxis("left").setWidth(82)
            plot.getPlotItem().getAxis("bottom").setHeight(40)
            plot.setMinimumHeight(190)
            legend = plot.addLegend(offset=(-8, 8))
            self.plots.append(plot)
            self.legends.append(legend)
            callback = partial(self._on_histogram_mouse_moved, plot_index)
            self._histogram_mouse_callbacks.append(callback)
            plot.scene().sigMouseMoved.connect(callback)
            self._set_plot_axes_visible(plot, False)
            plot.hide()
        # Compatibility aliases for callers that inspect the first histogram pane.
        self.plot = self.plots[0]
        self.legend = self.legends[0]
        self.histogram_mode = QComboBox()
        self.histogram_mode.addItems(("Separate", "Overlay"))
        self.histogram_units = QComboBox()
        self.histogram_units.addItems(("Count", "Normalized", "Log count"))
        self.histogram_range = QComboBox()
        self.histogram_range.addItems(("Native range", "Normalized 0–1"))
        self.histogram_bins = QComboBox()
        self.histogram_bins.addItems(("Auto", "256", "1024", "4096"))
        self.histogram_context = ElidingContextLabel()
        # ResponsiveControlLayout excludes hidden controls from row sizing.
        # Keep this row and its height reserved before the first result.
        self.histogram_context.setFixedHeight(self.histogram_context.fontMetrics().height() + 4)
        histogram_controls_widget = QWidget()
        histogram_controls = ResponsiveControlLayout(
            histogram_controls_widget, spacing=TOKENS.spacing_sm
        )
        for compact_row, label_text, combo in (
            (0, "View", self.histogram_mode),
            (0, "Y", self.histogram_units),
            (1, "X", self.histogram_range),
            (1, "Bins", self.histogram_bins),
        ):
            histogram_controls.add_control(QLabel(label_text), compact_row=compact_row)
            histogram_controls.add_control(combo, compact_row=compact_row)
            combo.setMaximumWidth(170)
            combo.setMinimumWidth(0)
            combo.setSizePolicy(
                QSizePolicy.Policy.Ignored,
                QSizePolicy.Policy.Fixed,
            )
        histogram_controls.add_control(histogram_channel_label, compact_row=1)
        for button in self.channel_buttons.values():
            histogram_controls.add_control(button, compact_row=1)
        histogram_controls.add_context(self.histogram_context, compact_row=2)
        for combo in (self.histogram_mode, self.histogram_units, self.histogram_range):
            combo.currentIndexChanged.connect(  # type: ignore[attr-defined]
                self._histogram_options_changed
            )
        self.histogram_bins.currentIndexChanged.connect(  # type: ignore[attr-defined]
            self._histogram_bins_changed
        )
        self.histogram_panel = QWidget()
        histogram_panel_layout = QVBoxLayout(self.histogram_panel)
        histogram_panel_layout.setContentsMargins(4, 4, 4, 4)
        histogram_panel_layout.setSpacing(TOKENS.spacing_xs)
        histogram_panel_layout.addWidget(histogram_controls_widget)
        histogram_scroll = QScrollArea()
        histogram_scroll.setWidgetResizable(True)
        histogram_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        histogram_scroll.setWidget(self.histogram_grid)
        histogram_panel_layout.addWidget(histogram_scroll, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)
        layout.addWidget(self.region_group)
        layout.addWidget(self.image_summary_group)
        layout.addWidget(self.statistics_group, 1)
        layout.addWidget(self.activity)

    @staticmethod
    def _analysis_request_signature(
        documents: list[ImageDocument],
        bounds: RoiBounds | None,
        histogram_specs: list[tuple[int, tuple[float, float] | None]],
    ) -> tuple[object, ...]:
        return (
            tuple(
                (
                    document.document_id,
                    document.generation,
                    id(document.source),
                    document.channel_layout,
                    getattr(document.raw_profile, "bayer_pattern", None),
                )
                for document in documents
            ),
            bounds,
            tuple(histogram_specs),
        )

    def bind_review_source_keys(self, mapping: dict[str, str]) -> None:
        """W09 handoff: map runtime IDs to durable keys without changing numerics.

        The owner supplies only verified document_id -> Review UUID mappings.
        No source registration, alias resolver or new QObject hook is created.
        """
        if any(not key or not value for key, value in mapping.items()):
            raise ValueError("invalid Review source mapping")
        self._analysis_source_keys.update(mapping)
        # Explicit rebind affects identity only, not native data or requests.
        self._presented_analysis_token = self._analysis_render_token()
        self._presented_histogram_token = self._histogram_live_token()
        self._refresh_pivot()

    def source_key_for_document(self, document_id: str) -> str:
        return self._analysis_source_keys.setdefault(document_id, str(uuid4()))

    @staticmethod
    def _review_profile_signature(document: ImageDocument) -> str:
        """Use the same path-free interpretation identity in all W02 producers."""
        return native_profile_signature(document)

    def _analysis_live_token(self) -> PresentedAnalysisTokenV1 | None:
        if (
            not self.last_results
            or self._completed_signature != self._request_signature
            or self._refresh_timer.isActive()
            or self._worker is not None
            or len(self.last_results) != len(self._documents)
        ):
            return None
        if self._request_signature != self._analysis_request_signature(
            self._documents, self._bounds, self._histogram_specs
        ):
            return None
        roi = self._bounds
        if (roi is None) != (self.region_scope.currentText() != "Active ROI"):
            return None
        if any(
            r.bounds != (roi or RoiBounds(0, 0, d.reference_shape[1], d.reference_shape[0]))
            for d, r in zip(self._documents, self.last_results, strict=True)
        ):
            return None
        return PresentedAnalysisTokenV1(
            feature="statistics",
            request_id=self._analysis_request_id,
            request_epoch=self._analysis_request_epoch,
            source_documents=tuple((d.document_id, d.generation) for d in self._documents),
            source_keys=tuple(self.source_key_for_document(d.document_id) for d in self._documents),
            roi_ref=None if roi is None else (roi.x, roi.y, roi.width, roi.height),
            channel="All",
            domain="native",
            profile_signatures=tuple(self._review_profile_signature(d) for d in self._documents),
            difference_cache_key=None,
        )

    def _analysis_render_token(self) -> PresentedAnalysisTokenV1 | None:
        # During the succeeded signal the TaskWorker has not yet emitted
        # finished; tolerate it ONLY for token publication, never for capture.
        worker = self._worker
        self._worker = None
        try:
            return self._analysis_live_token()
        finally:
            self._worker = worker

    def get_presented_analysis_token(self) -> PresentedAnalysisTokenV1 | None:
        """Result token published only by a completed render (W00 M1)."""
        return self._presented_analysis_token

    def get_current_analysis_token(self) -> PresentedAnalysisTokenV1 | None:
        """Revalidate live request and producer data against the published token."""
        return self._analysis_live_token()

    def read_presented_analysis(
        self,
    ) -> tuple[
        tuple[AnalysisSourceV1, ...],
        tuple[AnalysisMeasurementV1, ...],
        tuple[tuple[str, str], ...],
    ]:
        if self.get_current_analysis_token() != self.get_presented_analysis_token():
            raise ValueError("analysis is no longer current")
        token = self.get_presented_analysis_token()
        if token is None:
            raise ValueError("no presented analysis")
        sources: list[AnalysisSourceV1] = []
        values: list[AnalysisMeasurementV1] = []
        for document, result, key in zip(
            self._documents, self.last_results, token.source_keys, strict=True
        ):
            if document.source is None:
                raise ValueError("unloaded analysis source")
            sources.append(snapshot_source(document, key))
            for index, (channel, stats) in enumerate(
                zip(result.channel_names, result.channel_statistics, strict=True)
            ):
                count = (
                    result.channel_sample_counts[index]
                    if result.channel_sample_counts
                    else result.pixel_count
                )
                fields = (
                    ("Min", stats.minimum),
                    ("Max", stats.maximum),
                    ("Mean", stats.mean),
                    ("Std", stats.standard_deviation),
                    ("P1", stats.percentiles[1.0]),
                    ("P50", stats.percentiles[50.0]),
                    ("P99", stats.percentiles[99.0]),
                )
                values.extend(
                    measurement(key, channel, name, value, count) for name, value in fields
                )
        return tuple(sources), tuple(values), (("scope", "roi" if token.roi_ref else "full"),)

    def _histogram_ui_signature(self) -> tuple[object, ...]:
        return (
            self.histogram_range.currentText(),
            self.histogram_units.currentText(),
            self.region_scope.currentText(),
            tuple(
                sorted((name, button.isChecked()) for name, button in self.channel_buttons.items())
            ),
        )

    def _histogram_live_token(self) -> PresentedAnalysisTokenV1 | None:
        stats = self._analysis_live_token()
        if (
            stats is None
            or not any(self._histogram_series)
            or self._histogram_presentation_signature != self._histogram_ui_signature()
        ):
            return None
        return replace(
            stats,
            feature="histogram",
            request_epoch=stats.request_epoch + self._histogram_presentation_epoch,
        )

    def get_presented_histogram_token(self) -> PresentedAnalysisTokenV1 | None:
        return self._presented_histogram_token

    def get_current_histogram_token(self) -> PresentedAnalysisTokenV1 | None:
        return self._histogram_live_token()

    def read_presented_histogram(
        self,
    ) -> tuple[
        tuple[AnalysisSourceV1, ...],
        tuple[AnalysisMeasurementV1, ...],
        tuple[tuple[str, str], ...],
    ]:
        if (
            self.get_current_histogram_token() is None
            or self.get_current_histogram_token() != self.get_presented_histogram_token()
        ):
            raise ValueError("histogram presentation is stale")
        sources = tuple(
            snapshot_source(document, self.source_key_for_document(document.document_id))
            for document in self._documents
        )
        presentation = (
            (
                "histogram_x",
                "normalized"
                if self.histogram_range.currentText() == "Normalized 0–1"
                else "native",
            ),
            (
                "histogram_y",
                (
                    "normalized"
                    if self.histogram_units.currentText() == "Normalized"
                    else "log-count"
                    if self.histogram_units.currentText() == "Log count"
                    else "count"
                ),
            ),
        )
        return sources, (), presentation

    def read_presented_histogram_series(self) -> tuple[AnalysisSeriesV1, ...]:
        if self.get_current_histogram_token() != self.get_presented_histogram_token():
            raise ValueError("histogram request changed")
        presented: set[tuple[int, str]] = {
            (image_index, channel)
            for group in self._histogram_series
            for image_index, channel, _x, _y in group
        }
        series: list[AnalysisSeriesV1] = []
        for image_index, (document, result) in enumerate(
            zip(self._documents, self.last_results, strict=True)
        ):
            source_key = self.source_key_for_document(document.document_id)
            for channel_index, channel in enumerate(result.histogram.channel_names):
                if (image_index, channel) not in presented:
                    continue
                counts = result.histogram.counts[channel_index]
                values, states = freeze_series_values(counts)
                count = (
                    result.channel_sample_counts[channel_index]
                    if result.channel_sample_counts
                    else result.pixel_count
                )
                series.append(
                    AnalysisSeriesV1(
                        source_key=source_key,
                        channel=channel,
                        kind="histogram",
                        coordinates=tuple(float(v) for v in result.histogram.edges),
                        values=values,
                        value_states=states,
                        sample_count=count,
                        definition_revision="native-bin-counts-v1",
                    )
                )
        if not series:
            raise ValueError("no presented histogram series")
        return tuple(series)

    def set_semantics_delegate(self, delegate: Any | None) -> None:
        """Select an optional analysis strategy without replacing instance methods."""

        self._semantics_delegate = delegate

    def install_empty_hint(self, controller: Any) -> None:
        self.workflow_histogram_hint_controller = controller
        self.workflow_histogram_hint = controller.label
        self._sync_empty_hint()

    def _sync_empty_hint(self) -> None:
        hint = self.workflow_histogram_hint_controller
        if hint is None:
            return
        if self.last_results or self._documents:
            hint.hide()
        else:
            hint.show()

    def set_documents(
        self,
        documents: list[ImageDocument],
        bounds: RoiBounds | None,
        region_name: str | None = None,
    ) -> None:
        if self._semantics_delegate is not None:
            self._semantics_delegate.set_analysis_documents(documents, bounds, region_name)
            return
        self.set_documents_default(documents, bounds, region_name)

    def set_documents_default(
        self,
        documents: list[ImageDocument],
        bounds: RoiBounds | None,
        region_name: str | None = None,
    ) -> None:
        ready_documents = [document for document in documents if document.source is not None]
        if not ready_documents:
            self.clear()
            return
        requested_bins = self._selected_histogram_bins()
        histogram_specs = [
            automatic_histogram_spec(document, requested_bins) for document in ready_documents
        ]
        signature = self._analysis_request_signature(ready_documents, bounds, histogram_specs)

        self._documents = ready_documents
        self._bounds = bounds
        self.region_scope.blockSignals(True)
        self.region_scope.setCurrentText(
            region_name or ("Active ROI" if bounds is not None else "Full image")
        )
        self.region_scope.blockSignals(False)
        if bounds is not None:
            self.set_active_roi(bounds)
        else:
            self._sync_roi_editor()
        self._update_region_label()

        same_request = signature == self._request_signature
        same_request_active = self._refresh_timer.isActive() or (
            self._worker is not None and not self._worker.is_cancelled
        )
        if same_request and (same_request_active or signature == self._completed_signature):
            return

        if self._worker is not None:
            self._worker.cancel()
        self._request_signature = signature
        self._analysis_request_epoch += 1
        self._analysis_request_id = str(uuid4())
        self._token_request_signature = signature
        self._presented_analysis_token = None
        self._presented_histogram_token = None
        self._completed_signature = ()
        self._histogram_specs = histogram_specs
        self._invalidate_histogram_presentation()
        self._set_activity("Preparing analysis...", busy=True)
        self._sync_empty_hint()
        self._refresh_timer.start()

    def clear(self) -> None:
        self._refresh_timer.stop()
        if self._worker is not None:
            self._worker.cancel()
        self._worker = None
        self._documents = []
        self._bounds = None
        self._active_roi_bounds = None
        self._request_signature = ()
        self._completed_signature = ()
        self._presented_analysis_token = None
        self._presented_histogram_token = None
        self._token_request_signature = ()
        self._analysis_request_epoch += 1
        self._histogram_specs = []
        self.last_results = ()
        self.image_summary.setRowCount(0)
        self.table.setRowCount(0)
        self._clear_pivot()
        self.statistics_delegate.set_separator_rows(set())
        self._clear_histogram_plots()
        self.roi_label.clear()
        self._sync_roi_editor()
        self.histogram_context.clear()
        self._set_activity("No images selected", busy=False)
        self._sync_empty_hint()

    def refresh(self) -> None:
        if self._semantics_delegate is not None:
            self._semantics_delegate.refresh_analysis()
            return
        self.refresh_default()

    def refresh_default(self) -> None:
        if self._histogram_resources_disposed:
            return
        documents = self._documents
        if not documents:
            self.clear()
            return
        bounds = self._bounds
        requested_bins = self._selected_histogram_bins()
        histogram_specs = [
            automatic_histogram_spec(document, requested_bins) for document in documents
        ]
        signature = self._analysis_request_signature(documents, bounds, histogram_specs)
        self._histogram_specs = histogram_specs

        if signature == self._request_signature:
            if self._worker is not None and not self._worker.is_cancelled:
                return
            if signature == self._completed_signature:
                return
        else:
            if self._worker is not None:
                self._worker.cancel()
            self._request_signature = signature
            self._analysis_request_epoch += 1
            self._analysis_request_id = str(uuid4())
            self._token_request_signature = signature
            self._presented_analysis_token = None
            self._presented_histogram_token = None
            self._completed_signature = ()
            self._invalidate_histogram_presentation()

        sources = [
            (
                document.source[..., :3]
                if document.source is not None
                and document.source.ndim == 3
                and document.source.shape[-1] == 4
                else document.source
            )
            for document in documents
        ]
        assert all(source is not None for source in sources)
        active_bounds = [
            bounds or RoiBounds(0, 0, source.shape[1], source.shape[0])
            for source in sources
            if source is not None
        ]
        cache_keys: list[tuple[object, ...]] = [
            (
                "comparison",
                selected_bounds,
                bins,
                value_range,
                document.generation,
                document.channel_layout,
                getattr(document.raw_profile, "bayer_pattern", None),
            )
            for document, selected_bounds, (bins, value_range) in zip(
                documents, active_bounds, histogram_specs, strict=True
            )
        ]
        cached_results = [
            document.statistics_cache.get(key)
            for document, key in zip(documents, cache_keys, strict=True)
        ]
        typed_cached = tuple(
            result for result in cached_results if isinstance(result, RoiAnalysisResult)
        )
        if len(typed_cached) == len(cached_results):
            self.last_results = typed_cached
            self._completed_signature = signature
            self._render(typed_cached, histogram_specs)
            return

        def calculate() -> tuple[RoiAnalysisResult, ...]:
            timer = AnalysisPhaseTimer("histogram.worker.compute", documents=len(documents))
            results: list[RoiAnalysisResult] = []
            for document, source, selected_bounds, spec, cached in zip(
                documents,
                sources,
                active_bounds,
                histogram_specs,
                cached_results,
                strict=True,
            ):
                assert source is not None
                if isinstance(cached, RoiAnalysisResult):
                    results.append(cached)
                else:
                    bins, value_range = spec
                    bayer_pattern = getattr(document.raw_profile, "bayer_pattern", None)
                    if document.channel_layout == "BAYER" and isinstance(bayer_pattern, str):
                        results.append(
                            analyze_bayer_roi(
                                source,
                                selected_bounds,
                                bayer_pattern,
                                bins,
                                value_range,
                            )
                        )
                    else:
                        results.append(
                            analyze_roi(
                                source,
                                selected_bounds,
                                bins,
                                value_range,
                            )
                        )
            timer.finish()
            return tuple(results)

        self._set_activity("Calculating...", busy=True)
        worker = TaskWorker(calculate)
        worker.signals.succeeded.connect(
            lambda task_id, _document_id, _generation, result: self._on_result(
                signature, cache_keys, histogram_specs, result, task_id=task_id
            )
        )
        worker.signals.failed.connect(self._on_error)
        worker.signals.finished.connect(self._on_finished)
        self._worker = worker
        self._pool.start(worker)

    def _on_result(
        self,
        signature: tuple[object, ...],
        cache_keys: list[tuple[object, ...]],
        histogram_specs: list[tuple[int, tuple[float, float] | None]],
        result: object,
        *,
        task_id: str | None = None,
    ) -> None:
        if self._histogram_resources_disposed:
            return
        if task_id is not None and (
            self._worker is None or self._worker.task_id != task_id or self._worker.is_cancelled
        ):
            return
        if signature != self._request_signature or not isinstance(result, tuple):
            return
        if len(result) != len(self._documents) or not all(
            isinstance(item, RoiAnalysisResult) for item in result
        ):
            return
        typed_result = tuple(result)
        for document, key, item in zip(self._documents, cache_keys, typed_result, strict=True):
            document.statistics_cache[key] = item
        self.last_results = typed_result
        self._completed_signature = signature
        self._render(typed_result, histogram_specs)

    def _on_error(
        self,
        _task_id: str,
        _document_id: str | None,
        _generation: int,
        error: TaskError,
    ) -> None:
        if self._histogram_resources_disposed:
            return
        self._set_activity(f"Error: {error.message}", busy=False)

    def _on_finished(self, task_id: str) -> None:
        if self._worker is not None and self._worker.task_id == task_id:
            self._worker = None
            self._refresh_pivot()

    def _channels_changed(self, _checked: bool) -> None:
        if self.last_results and self._histogram_specs:
            self._render(self.last_results, self._histogram_specs)

    def _histogram_options_changed(self, _index: int) -> None:
        if self.last_results and self._histogram_specs:
            self._render(self.last_results, self._histogram_specs)

    def _histogram_bins_changed(self, _index: int) -> None:
        if not self._documents:
            return
        histogram_specs = [
            automatic_histogram_spec(document, self._selected_histogram_bins())
            for document in self._documents
        ]
        signature = self._analysis_request_signature(
            self._documents,
            self._bounds,
            histogram_specs,
        )
        if self._worker is not None:
            self._worker.cancel()
        self._request_signature = signature
        self._completed_signature = ()
        self._histogram_specs = histogram_specs
        self._invalidate_histogram_presentation()
        self._set_activity("Preparing histogram...", busy=True)
        self._refresh_timer.start()

    def _selected_histogram_bins(self) -> int | None:
        text = self.histogram_bins.currentText()
        return None if text == "Auto" else int(text)

    def set_roi_available(self, available: bool) -> None:
        model = self.region_scope.model()
        if isinstance(model, QStandardItemModel):
            active_roi_index = self.region_scope.findText("Active ROI")
            active_roi_item = model.item(active_roi_index)
            if active_roi_item is not None:
                active_roi_item.setEnabled(available)
        if not available and self.region_scope.currentText() == "Active ROI":
            self.region_scope.blockSignals(True)
            self.region_scope.setCurrentText("Full image")
            self.region_scope.blockSignals(False)

    def set_active_roi(self, bounds: RoiBounds | None) -> None:
        """Mirror the application-owned shared ROI into the numeric editor."""

        self._active_roi_bounds = bounds
        self.set_roi_available(bounds is not None)
        self._sync_roi_editor()

    def _sync_roi_editor(self) -> None:
        bounds = self._active_roi_bounds
        if bounds is None and self._documents:
            height, width = self._documents[0].reference_shape
            if height > 0 and width > 0:
                bounds = RoiBounds(0, 0, width, height)
        values = (
            (bounds.x, bounds.y, bounds.width, bounds.height)
            if bounds is not None
            else (0, 0, 1, 1)
        )
        controls = (
            self.roi_x_input,
            self.roi_y_input,
            self.roi_width_input,
            self.roi_height_input,
        )
        for control, value in zip(controls, values, strict=True):
            control.blockSignals(True)
            control.setValue(value)
            control.blockSignals(False)
            control.setEnabled(bool(self._documents))
        self.roi_apply_button.setEnabled(bool(self._documents))
        self.roi_clear_button.setEnabled(self._active_roi_bounds is not None)

    def _request_roi_apply(self) -> None:
        if not self._documents:
            return
        self.roi_apply_requested.emit(
            RoiBounds(
                self.roi_x_input.value(),
                self.roi_y_input.value(),
                self.roi_width_input.value(),
                self.roi_height_input.value(),
            )
        )

    def _update_region_label(self) -> None:
        bounds = self._bounds
        if bounds is None:
            if not self._documents or self._documents[0].source is None:
                self.roi_label.clear()
                return
            height, width = self._documents[0].reference_shape
            bounds = RoiBounds(0, 0, width, height)
        text = f"x={bounds.x}, y={bounds.y}, width={bounds.width}, height={bounds.height}"
        self.roi_label.setText(text)

    @staticmethod
    def _format_bounds(bounds: RoiBounds) -> str:
        return f"x={bounds.x}, y={bounds.y}, " f"width={bounds.width}, height={bounds.height}"

    def _update_histogram_context(self, results: tuple[RoiAnalysisResult, ...]) -> None:
        if not results:
            self.histogram_context.clear()
            return
        bounds = tuple(result.bounds for result in results)
        if all(item == bounds[0] for item in bounds[1:]):
            text = self._format_bounds(bounds[0])
        else:
            details = " · ".join(
                f"{index}: {self._format_bounds(item)}"
                for index, item in enumerate(bounds, start=1)
            )
            text = f"Per-image bounds · {details}"
        self.histogram_context.setText(text)

    def _invalidate_histogram_presentation(self) -> None:
        # The previous graph stays visible (with the explicit busy indicator)
        # until the new analysis has finished. Clearing here causes a blank
        # frame and a scrollbar/layout jump while the worker is running.
        self.last_results = ()
        self._clear_pivot()
        if self.histogram_context.text() and not self.histogram_context.text().startswith(
            "Previous result · "
        ):
            self.histogram_context.setText(f"Previous result · {self.histogram_context.text()}")
        # The preserved curves are a previous-result preview, not current
        # source data. Disable hover readouts until the replacement arrives.
        self._histogram_series = [[] for _index in range(6)]
        for line, hint in zip(
            self._histogram_hover_lines, self._histogram_hover_texts, strict=True
        ):
            if line is not None:
                line.hide()
            if hint is not None:
                hint.hide()

    def _set_activity(self, text: str, *, busy: bool) -> None:
        self.status.setText(text)
        self.busy.setVisible(busy)
        # Keep the reserved rail in the layout when status becomes empty.
        self.activity.setVisible(True)

    def _render(
        self,
        results: tuple[RoiAnalysisResult, ...],
        histogram_specs: list[tuple[int, tuple[float, float] | None]],
    ) -> None:
        timer = AnalysisPhaseTimer("histogram.gui.render", documents=len(results))
        hint = self.workflow_histogram_hint_controller
        if hint is not None:
            hint.hide()
        self._update_histogram_context(results)
        labels = comparison_labels(self._documents)
        self.image_summary.setRowCount(len(results))
        for image_index, (document, result) in enumerate(
            zip(self._documents, results, strict=True)
        ):
            shape = document.shape
            file_format = (
                document.source_path or Path(document.display_name)
            ).suffix.upper().lstrip(".") or document.channel_layout
            metadata = (
                f"{labels[image_index]}\n{shape[1]} x {shape[0]} - {file_format} - "
                f"{document.bit_depth}-bit\n{document.source_path or document.display_name}"
            )
            summary_values = (
                str(image_index + 1),
                labels[image_index],
                f"{document.bit_depth}-bit",
                f"{result.pixel_count:,}",
            )
            for column, value in enumerate(summary_values):
                item = QTableWidgetItem(value)
                alignment = (
                    Qt.AlignmentFlag.AlignLeft
                    if column == 1
                    else Qt.AlignmentFlag.AlignCenter
                    if column == 2
                    else Qt.AlignmentFlag.AlignRight
                )
                item.setTextAlignment(alignment | Qt.AlignmentFlag.AlignVCenter)
                item.setToolTip(metadata)
                self.image_summary.setItem(image_index, column, item)
        self.image_summary.resizeRowsToContents()
        summary_height = self.image_summary.horizontalHeader().height() + 2
        for row in range(self.image_summary.rowCount()):
            summary_height += self.image_summary.rowHeight(row)
        self.image_summary.setFixedHeight(summary_height)

        rows: list[tuple[int, str, ImageStatistics]] = []
        for image_index, result in enumerate(results):
            rows.extend(
                (image_index, name, statistics)
                for name, statistics in zip(
                    result.channel_names,
                    result.channel_statistics,
                    strict=True,
                )
                if name != "A"
            )
        separator_rows = {
            row_index
            for row_index in range(1, len(rows))
            if rows[row_index][0] != rows[row_index - 1][0]
        }
        self.statistics_delegate.set_separator_rows(separator_rows)
        self.table.setRowCount(len(rows))
        for row, (image_index, channel_name, statistics) in enumerate(rows):
            document = self._documents[image_index]
            shape = document.shape
            file_format = (
                document.source_path or Path(document.display_name)
            ).suffix.upper().lstrip(".") or document.channel_layout
            metadata = (
                f"{labels[image_index]}\n{shape[1]}×{shape[0]} · {file_format} · "
                f"{document.bit_depth}-bit\n{document.source_path or document.display_name}"
            )
            table_values = (
                str(image_index + 1),
                channel_name,
                f"{statistics.minimum:.6g}",
                f"{statistics.maximum:.6g}",
                f"{statistics.mean:.6g}",
                f"{statistics.standard_deviation:.6g}",
                f"{statistics.percentiles[1.0]:.6g}",
                f"{statistics.percentiles[50.0]:.6g}",
                f"{statistics.percentiles[99.0]:.6g}",
            )
            for column, value in enumerate(table_values):
                item = QTableWidgetItem(value)
                alignment = (
                    Qt.AlignmentFlag.AlignCenter
                    if column in (0, 1)
                    else Qt.AlignmentFlag.AlignRight
                )
                item.setTextAlignment(alignment | Qt.AlignmentFlag.AlignVCenter)
                item.setToolTip(metadata)
                self.table.setItem(row, column, item)

        # Update charts atomically. The previous plot remains painted until
        # the new curves, axes and range are ready; Qt schedules one repaint.
        self.histogram_grid.setUpdatesEnabled(False)
        try:
            overlay = self.histogram_mode.currentText() == "Overlay"
            # Stage histogram widgets hidden while installing curves, labels and
            # axes. Exposing an empty PlotWidget before axis sizing and auto-range
            # produces a transient oversized plot on the first Qt paint.
            visible_plot_count = 1 if overlay else len(results)
            self._arrange_histogram_plots(visible_plot_count)
            for plot, legend in zip(self.plots, self.legends, strict=True):
                plot.clear()
                legend.clear()
            self._histogram_series = [[] for _index in range(6)]
            for plot_index in range(min(6, 1 if overlay else len(results))):
                self._create_histogram_hover(plot_index)
            plotted_channels: set[str] = set()
            for image_index, (document, result) in enumerate(
                zip(self._documents, results, strict=True)
            ):
                plot = self.plots[0 if overlay else image_index]
                edges = result.histogram.edges
                for counts, channel_name in zip(
                    result.histogram.counts,
                    result.histogram.channel_names,
                    strict=True,
                ):
                    control_name = self._channel_control_name(channel_name)
                    if (
                        control_name in self.channel_buttons
                        and not self.channel_buttons[control_name].isChecked()
                    ):
                        continue
                    if channel_name == "A":
                        continue
                    fill_color = QColor(channel_color(channel_name))
                    fill_color.setAlpha(52 if overlay else 78)
                    y_mode = self.histogram_units.currentText()
                    y_values = histogram_display_values(counts, y_mode)
                    x_values = edges
                    if self.histogram_range.currentText() == "Normalized 0–1":
                        span = float(edges[-1] - edges[0])
                        if span > 0:
                            x_values = (edges - edges[0]) / span
                    short_name = document.display_name
                    if len(short_name) > 24:
                        short_name = f"{short_name[:11]}…{short_name[-10:]}"
                    legend_name = (
                        f"{image_index + 1} · {short_name} · {channel_name}"
                        if overlay
                        else channel_name
                    )
                    plot.plot(
                        x_values,
                        y_values,
                        stepMode="center",
                        fillLevel=0.0,
                        brush=pg.mkBrush(fill_color),
                        pen=comparison_pen(channel_name, 0, width=0.7),
                        name=legend_name,
                        antialias=True,
                    )
                    self._histogram_series[0 if overlay else image_index].append(
                        (image_index, channel_name, x_values, y_values)
                    )
                    plotted_channels.add(channel_name)
                title = (
                    f"{document.source_path.parent.name} / {document.display_name}"
                    if document.source_path is not None
                    else document.display_name
                )
                if not overlay:
                    plot.setTitle(middle_elide(f"{image_index + 1} · {title}"))
                self._set_plot_axes_visible(plot, True)
                y_mode = self.histogram_units.currentText()
                plot.setLabel(
                    "left",
                    "Normalized"
                    if y_mode == "Normalized"
                    else "Log count"
                    if y_mode == "Log count"
                    else "Count",
                )
                plot.setLabel(
                    "bottom",
                    "Normalized code"
                    if self.histogram_range.currentText() == "Normalized 0–1"
                    else "Pixel value",
                )
                plot.getViewBox().autoRange(padding=0.08)
            if overlay:
                self.plots[0].setTitle(f"Overlay · {len(results)} images")
                self.plots[0].getViewBox().autoRange(padding=0.08)
            # Reveal only fully configured plots. Axis labels and ticks affect
            # PlotItem geometry, so they must be in place before the first show.
            for plot in self.plots[: min(6, visible_plot_count)]:
                plot.show()
        finally:
            self.histogram_grid.setUpdatesEnabled(True)
        self.table.resizeRowsToContents()
        self.table.viewport().update()
        self._set_activity("", busy=False)
        timer.finish()
        # Native YUV delegates may set _request_signature directly. Detect that
        # producer transition here without editing the app-owned YUV adapter.
        if self._token_request_signature != self._completed_signature:
            self._analysis_request_epoch += 1
            self._analysis_request_id = str(uuid4())
            self._token_request_signature = self._completed_signature
        # On worker completion this may still see an active worker; publish the
        # immutable identity from the completed signature, then export capture
        # checks completion/worker state again before and after extraction.
        self._presented_analysis_token = self._analysis_render_token()
        self._histogram_presentation_epoch += 1
        self._histogram_presentation_signature = self._histogram_ui_signature()
        stats = self._presented_analysis_token
        self._presented_histogram_token = (
            replace(
                stats,
                feature="histogram",
                request_epoch=stats.request_epoch + self._histogram_presentation_epoch,
            )
            if stats is not None and any(self._histogram_series)
            else None
        )
        self._refresh_pivot()

    def _create_histogram_hover(self, plot_index: int) -> None:
        plot = self.plots[plot_index]
        line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#d0d0d0", width=0.7))
        hint = pg.TextItem(
            anchor=(0, 1),
            fill=pg.mkBrush(24, 24, 24, 225),
            border=pg.mkPen("#808080", width=0.7),
        )
        line.setZValue(20)
        hint.setZValue(21)
        plot.addItem(line, ignoreBounds=True)
        plot.addItem(hint, ignoreBounds=True)
        line.hide()
        hint.hide()
        self._histogram_hover_lines[plot_index] = line
        self._histogram_hover_texts[plot_index] = hint

    def _on_histogram_mouse_moved(self, plot_index: int, position: object) -> None:
        plot = self.plots[plot_index]
        line = self._histogram_hover_lines[plot_index]
        hint = self._histogram_hover_texts[plot_index]
        series = self._histogram_series[plot_index]
        if (
            line is None
            or hint is None
            or not series
            or not plot.sceneBoundingRect().contains(position)
        ):
            if line is not None:
                line.hide()
            if hint is not None:
                hint.hide()
            return
        point = plot.getViewBox().mapSceneToView(position)
        rows: list[str] = []
        cursor_x: float | None = None
        for image_index, channel_name, edges, values in series:
            bin_index = int(np.searchsorted(edges, point.x(), side="right") - 1)
            if bin_index < 0 or bin_index >= len(values):
                continue
            cursor_x = float((edges[bin_index] + edges[bin_index + 1]) / 2.0)
            value = float(values[bin_index])
            rows.append(
                f"<tr><td><b>{image_index + 1}</b></td>"
                f'<td style="color:{channel_color(channel_name)}; padding-left:7px">'
                f"{channel_name}</td>"
                f'<td style="padding-left:10px; text-align:right">'
                f"{plot_number(value)}</td></tr>"
            )
        if cursor_x is None or not rows:
            line.hide()
            hint.hide()
            return
        view_range = plot.getViewBox().viewRange()
        y_anchor = 0 if point.y() > sum(view_range[1]) / 2 else 1
        hint.setAnchor((1, y_anchor))
        coordinate_label = (
            "Normalized code" if self.histogram_range.currentText() == "Normalized 0–1" else "Code"
        )
        header = coordinate_header(coordinate_label, cursor_x)
        hint.setHtml(f"<b>{header}</b><table cellspacing='2'>{''.join(rows)}</table>")
        x_range, y_range = view_range
        x_padding = (x_range[1] - x_range[0]) * 0.04
        y_padding = (y_range[1] - y_range[0]) * 0.08
        hint_x = min(max(cursor_x, x_range[0] + x_padding), x_range[1] - x_padding)
        hint_y = min(max(point.y(), y_range[0] + y_padding), y_range[1] - y_padding)
        hint.setPos(hint_x, hint_y)
        line.setPos(cursor_x)
        line.show()
        hint.show()

    @staticmethod
    def _channel_control_name(channel_name: str) -> str:
        return "G" if channel_name in ("Gr", "Gb") else channel_name

    def _arrange_histogram_plots(self, count: int) -> None:
        visible_count = min(6, count)
        if visible_count == self._arranged_histogram_count:
            return
        for plot in self.plots:
            self.histogram_layout.removeWidget(plot)
            plot.hide()
        for index in range(visible_count):
            plot = self.plots[index]
            self.histogram_layout.addWidget(plot, index, 0)
        self._arranged_histogram_count = visible_count
        for row in range(6):
            self.histogram_layout.setRowStretch(row, 1 if row < visible_count else 0)
        self.histogram_layout.setColumnStretch(0, 1)

    def _clear_histogram_plots(self) -> None:
        self._arranged_histogram_count = 0
        for plot, legend in zip(self.plots, self.legends, strict=True):
            plot.clear()
            legend.clear()
            plot.setTitle("")
            self._set_plot_axes_visible(plot, False)
            plot.hide()
        self._histogram_series = [[] for _index in range(6)]

    def _statistics_view_changed(self, index: int) -> None:
        self.statistics_stack.setCurrentIndex(index)
        self._refresh_pivot()

    def _clear_pivot(self) -> None:
        """Never leave old numbers visible when W02's live token is invalid."""
        self._pivot = None
        self.pivot_table.clear()
        self.pivot_table.setRowCount(0)
        self.pivot_table.setColumnCount(0)
        self.pivot_export_button.setEnabled(False)

    def _refresh_pivot(self, _index: int = -1) -> None:
        """Presentation-only operation: never requests analysis or changes selection."""
        if self._histogram_resources_disposed:
            return
        token = self.get_presented_analysis_token()
        if token is None or token != self.get_current_analysis_token():
            self._clear_pivot()
            return
        try:
            if len(self._documents) != len(token.source_documents) or any(
                document.document_id != document_id or document.generation != generation
                for document, (document_id, generation) in zip(
                    self._documents, token.source_documents, strict=True
                )
            ):
                raise ValueError("changed current comparison source")
            sources, measurements, _presentation = self.read_presented_analysis()
            if (
                self.get_presented_analysis_token() != token
                or self.get_current_analysis_token() != token
            ):
                raise ValueError("changed Statistics presentation during read")

            # W03's document.display_name is already the canonical qualified
            # alias; re-resolving with a separate folder/identity store would
            # override persistent tag edits.
            labels = {
                key: document.display_name
                for document, key in zip(self._documents, token.source_keys, strict=True)
            }
            selected_channel = self.pivot_channel.currentText()
            channels = list(
                dict.fromkeys(
                    item.channel for item in measurements if item.metric in STATISTICS_METRICS
                )
            )
            channel_options = ["All", *channels]
            if [
                self.pivot_channel.itemText(i) for i in range(self.pivot_channel.count())
            ] != channel_options:
                self.pivot_channel.blockSignals(True)
                self.pivot_channel.clear()
                self.pivot_channel.addItems(channel_options)
                self.pivot_channel.setCurrentText(
                    selected_channel if selected_channel in channel_options else "All"
                )
                self.pivot_channel.blockSignals(False)

            old_ref = self.pivot_reference.currentData()
            reference_keys = list(token.source_keys)
            old_keys = [
                self.pivot_reference.itemData(i) for i in range(1, self.pivot_reference.count())
            ]
            old_labels = [
                self.pivot_reference.itemText(i) for i in range(1, self.pivot_reference.count())
            ]
            new_labels = [f"{index} · {labels[key]}" for index, key in enumerate(reference_keys, 1)]
            if old_keys != reference_keys or old_labels != new_labels:
                self.pivot_reference.blockSignals(True)
                self.pivot_reference.clear()
                self.pivot_reference.addItem("No reference", None)
                for key, display in zip(reference_keys, new_labels, strict=True):
                    self.pivot_reference.addItem(display, key)
                selected = self.pivot_reference.findData(old_ref)
                self.pivot_reference.setCurrentIndex(max(0, selected))
                self.pivot_reference.blockSignals(False)

            metric_options = {
                "Mean / Std / P99": FOCUSED_METRICS,
                "All metrics": STATISTICS_METRICS,
                "Percentiles": PERCENTILE_METRICS,
            }
            metric_filter = metric_options[self.pivot_metrics.currentText()]
            pivot = build_statistics_pivot(
                token,
                sources,
                measurements,
                labels,
                channel=self.pivot_channel.currentText(),
                metrics=metric_filter,
                reference_key=self.pivot_reference.currentData(),
            )
        except (ValueError, RuntimeError, TypeError, KeyError, IndexError):
            self._clear_pivot()
            return

        self._pivot = pivot
        self._render_pivot(pivot)
        self.pivot_export_button.setEnabled(bool(pivot.rows))

    def _render_pivot(self, pivot: StatisticsPivot) -> None:
        """One row per metric/channel, one source column; horizontal scroll at 6."""
        table = self.pivot_table
        table.setUpdatesEnabled(False)
        try:
            table.clear()
            table.setRowCount(len(pivot.rows))
            table.setColumnCount(len(pivot.columns) + 2)
            table.setHorizontalHeaderLabels(
                [
                    "Metric",
                    "Unit",
                    *[
                        f"{index} · {column.alias}"
                        + (" [Pivot Ref]" if column.source_key == pivot.reference_key else "")
                        for index, column in enumerate(pivot.columns, 1)
                    ],
                ]
            )
            header = table.horizontalHeader()
            header.resizeSection(0, 125)
            header.resizeSection(1, 110)
            for index, column in enumerate(pivot.columns, 2):
                header.resizeSection(index, 215)
                header_item = table.horizontalHeaderItem(index)
                if header_item is not None:
                    header_item.setToolTip(
                        f"Alias: {column.alias}\n"
                        f"Native layout: {column.source.channel_layout}\n"
                        f"Dtype: {column.source.native_dtype}\n"
                        f"Effective bits: {column.source.effective_bits}\n"
                        f"Source generation: {column.source.generation}"
                    )
            mode = self.pivot_delta.currentText()
            for row_index, row in enumerate(pivot.rows):
                table.setItem(row_index, 0, QTableWidgetItem(f"{row.metric} · {row.channel}"))
                table.setItem(row_index, 1, QTableWidgetItem(row.definition.unit))
                for column_index, cell in enumerate(row.cells, 2):
                    display = cell.formatted_value()
                    if mode != "Values":
                        is_relative = mode == "Relative Δ (%)"
                        delta_text = cell.formatted_delta(relative=is_relative)
                        delta_unit = "%" if is_relative else row.definition.unit
                        display = f"{display}  |  Δ {delta_text} {delta_unit}"
                    item = QTableWidgetItem(display)
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                    native_count = (
                        f"{cell.sample_count:,}" if cell.sample_count is not None else "N/A"
                    )
                    full_value = cell.formatted_value(precision=17)
                    tooltip = (
                        f"{pivot.columns[column_index - 2].alias}\n"
                        f"Metric: {row.metric} · {row.channel}\n"
                        f"Value (17 digits): {full_value} {row.definition.unit}\n"
                        f"State: {cell.state}\n"
                        f"Native samples: {native_count}\n"
                        f"Reference ROI: {pivot.token.roi_ref or 'Full image'}"
                    )
                    if pivot.reference_key is not None or mode != "Values":
                        tooltip += (
                            f"\nAbsolute Δ: {cell.formatted_delta(precision=17)} "
                            f"{row.definition.unit}"
                            f"\nRelative Δ: {cell.formatted_delta(relative=True, precision=17)} %"
                        )
                        if cell.delta_reason is not None:
                            tooltip += f"\nDelta limitation: {cell.delta_reason}"
                    item.setToolTip(tooltip)
                    table.setItem(row_index, column_index, item)
        finally:
            table.setUpdatesEnabled(True)

    def get_current_statistics_pivot(self) -> StatisticsPivot | None:
        """W09 read-only interface; None means pending, stale or not presented."""
        if (
            self._pivot is None
            or self.get_presented_analysis_token() != self._pivot.token
            or self.get_current_analysis_token() != self._pivot.token
        ):
            return None
        return self._pivot

    def _prompt_pivot_export(self) -> None:
        if self.get_current_statistics_pivot() is None:
            self._refresh_pivot()
        if self.get_current_statistics_pivot() is None:
            return
        filename, _filter = QFileDialog.getSaveFileName(
            self, "Export Pivot Statistics", "statistics-pivot.csv", "CSV Files (*.csv)"
        )
        if not filename:
            return
        try:
            self.export_pivot_csv(Path(filename))
        except (OSError, ValueError) as exc:
            self.status.setText(f"Pivot export unavailable: {exc}")

    def export_pivot_csv(self, path: Path) -> None:
        """Separate typed, full-precision CSV; legacy export_csv is untouched."""
        self._refresh_pivot()
        pivot = self.get_current_statistics_pivot()
        if pivot is None:
            raise ValueError("current Statistics pivot is pending or stale")
        with path.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.writer(stream)
            header = ["Metric", "Channel", "Unit"]
            for column in pivot.columns:
                prefix = f"{column.alias} [{column.source_key}]"
                header.extend(
                    (
                        f"{prefix} value",
                        f"{prefix} state",
                        f"{prefix} samples",
                        f"{prefix} Delta",
                        f"{prefix} Delta (%)",
                        f"{prefix} Delta reason",
                    )
                )
            writer.writerow(header)
            for row in pivot.rows:
                values = [row.metric, row.channel, row.definition.unit]
                for cell in row.cells:
                    values.extend(
                        (
                            cell.formatted_value(precision=17),
                            cell.state,
                            str(cell.sample_count) if cell.sample_count is not None else "",
                            cell.formatted_delta(precision=17),
                            cell.formatted_delta(relative=True, precision=17),
                            cell.delta_reason or "",
                        )
                    )
                writer.writerow(values)

    def _copy_pivot_selection(self) -> None:
        """Copy exactly the selected Pivot cells, without implicit source expansion.

        Preserve multi-range selection using empty TSV fields for unselected
        intersections. Screen rounding never becomes clipboard precision.
        """
        pivot = self.get_current_statistics_pivot()
        if pivot is None:
            return
        coordinates = {
            (index.row(), index.column())
            for index in self.pivot_table.selectedIndexes()
            if 0 <= index.row() < len(pivot.rows) and 0 <= index.column() < len(pivot.columns) + 2
        }
        if not coordinates:
            return
        rows = sorted({row for row, _column in coordinates})
        columns = sorted({column for _row, column in coordinates})
        header = [self.pivot_table.horizontalHeaderItem(column).text() for column in columns]
        lines = ["\t".join(header)]
        mode = self.pivot_delta.currentText()
        for row_index in rows:
            row = pivot.rows[row_index]
            fields: list[str] = []
            for column in columns:
                if (row_index, column) not in coordinates:
                    fields.append("")
                elif column == 0:
                    fields.append(f"{row.metric} · {row.channel}")
                elif column == 1:
                    fields.append(row.definition.unit)
                else:
                    cell = row.cells[column - 2]
                    text = cell.formatted_value(precision=17)
                    if mode != "Values":
                        relative = mode == "Relative Δ (%)"
                        text += (
                            " | Delta "
                            + cell.formatted_delta(relative=relative, precision=17)
                            + (" %" if relative else f" {row.definition.unit}")
                        )
                    fields.append(text)
            lines.append("\t".join(fields))
        QApplication.clipboard().setText("\n".join(lines))

    def copy_selection(self) -> None:
        if self.statistics_view.currentText() == "Pivot":
            self._copy_pivot_selection()
            return
        ranges = self.table.selectedRanges()
        if not ranges:
            return
        selected = ranges[0]
        lines: list[str] = []
        for row in range(selected.topRow(), selected.bottomRow() + 1):
            values: list[str] = []
            for column in range(selected.leftColumn(), selected.rightColumn() + 1):
                item = self.table.item(row, column)
                values.append(item.text() if item is not None else "")
            lines.append("\t".join(values))
        QApplication.clipboard().setText("\n".join(lines))

    def export_csv(self, path: Path) -> None:
        with path.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.writer(stream)
            writer.writerow(("Id", "Image", "Bit depth", "Samples"))
            for row in range(self.image_summary.rowCount()):
                writer.writerow(
                    [
                        self.image_summary.item(row, column).text()
                        if self.image_summary.item(row, column) is not None
                        else ""
                        for column in range(self.image_summary.columnCount())
                    ]
                )
            writer.writerow(())
            writer.writerow(self._COLUMNS)
            for row in range(self.table.rowCount()):
                writer.writerow(
                    [
                        self.table.item(row, column).text()
                        if self.table.item(row, column) is not None
                        else ""
                        for column in range(self.table.columnCount())
                    ]
                )

    @staticmethod
    def _set_plot_axes_visible(plot: pg.PlotWidget, visible: bool) -> None:
        for axis in ("left", "bottom"):
            if visible:
                plot.showAxis(axis)
            else:
                plot.hideAxis(axis)

    def shutdown(self) -> None:
        self._refresh_timer.stop()
        if self._worker is not None:
            self._worker.cancel()
        if self._histogram_resources_disposed:
            return
        self._histogram_resources_disposed = True

        for plot, callback in zip(
            tuple(self.plots),
            tuple(self._histogram_mouse_callbacks),
            strict=True,
        ):
            scene = plot.scene()
            with suppress(RuntimeError, TypeError):
                scene.sigMouseMoved.disconnect(callback)

            view_box = plot.getViewBox()
            menu = getattr(view_box, "menu", None)
            if menu is not None:
                view_box.menu = None
                menu.close()
                menu.deleteLater()

            plot.close()
            plot.deleteLater()

        self._histogram_mouse_callbacks.clear()
        self.plots.clear()
        self.legends.clear()
        self._histogram_hover_lines = [None] * 6
        self._histogram_hover_texts = [None] * 6
        self._histogram_series = [[] for _index in range(6)]
        self.plot = cast(Any, None)
        self.legend = cast(Any, None)
