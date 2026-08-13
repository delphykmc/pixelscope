from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, cast

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
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QScrollArea,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pixelscope.core.bayer import analyze_bayer_roi
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.roi import RoiAnalysisResult, RoiBounds, analyze_roi
from pixelscope.core.statistics import ImageStatistics
from pixelscope.ui.design_tokens import TOKENS, channel_button_style
from pixelscope.ui.plot_colors import channel_color, comparison_pen
from pixelscope.ui.plot_text import coordinate_header, middle_elide, plot_number
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

    def __init__(self) -> None:
        super().__init__()
        self._documents: list[ImageDocument] = []
        self._bounds: RoiBounds | None = None
        self._worker: TaskWorker | None = None
        self._request_signature: tuple[object, ...] = ()
        self._completed_signature: tuple[object, ...] = ()
        self._histogram_specs: list[tuple[int, tuple[float, float] | None]] = []
        self.last_results: tuple[RoiAnalysisResult, ...] = ()
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
        activity_layout.addWidget(self.status)
        activity_layout.addWidget(self.busy)

        self.roi_label = QLabel("")
        self.roi_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
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
        self.bounds_label = QLabel("Bounds")
        region_label_width = max(
            self.scope_label.sizeHint().width(),
            self.bounds_label.sizeHint().width(),
        )
        for label in (self.scope_label, self.bounds_label):
            label.setFixedWidth(region_label_width)
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.region_layout.addWidget(self.scope_label, 0, 0)
        self.region_layout.addWidget(
            self.region_scope,
            0,
            1,
            alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )
        self.region_layout.addWidget(self.bounds_label, 1, 0)
        self.region_layout.addWidget(self.roi_label, 1, 1)
        self.region_layout.setColumnStretch(1, 1)
        channel_controls = QHBoxLayout()
        channel_controls.addWidget(QLabel("Channels"))
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
            channel_controls.addWidget(button)
        channel_controls.addStretch(1)

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
        statistics_layout.addWidget(self.table)

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
        for plot_index in range(6):
            plot = pg.PlotWidget(axisItems={"left": KiloAxisItem(orientation="left")})
            plot.setLabel("left", "Count")
            plot.setLabel("bottom", "Pixel value")
            plot.showGrid(x=True, y=True, alpha=0.25)
            plot.getViewBox().setDefaultPadding(0.08)
            plot.setMinimumHeight(190)
            legend = plot.addLegend(offset=(-8, 8))
            self.plots.append(plot)
            self.legends.append(legend)
            plot.scene().sigMouseMoved.connect(
                lambda position, index=plot_index: self._on_histogram_mouse_moved(index, position)
            )
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
        histogram_controls = QHBoxLayout()
        histogram_controls.setSpacing(TOKENS.spacing_sm)
        histogram_controls.addWidget(QLabel("View"))
        histogram_controls.addWidget(self.histogram_mode)
        histogram_controls.addSpacing(TOKENS.spacing_lg)
        histogram_controls.addWidget(QLabel("Y"))
        histogram_controls.addWidget(self.histogram_units)
        histogram_controls.addSpacing(TOKENS.spacing_lg)
        histogram_controls.addWidget(QLabel("X"))
        histogram_controls.addWidget(self.histogram_range)
        histogram_controls.addSpacing(TOKENS.spacing_lg)
        histogram_controls.addWidget(QLabel("Bins"))
        histogram_controls.addWidget(self.histogram_bins)
        histogram_controls.addSpacing(TOKENS.spacing_lg)
        histogram_controls.addLayout(channel_controls)
        histogram_controls.addStretch(1)
        for combo in (
            self.histogram_mode,
            self.histogram_units,
            self.histogram_range,
            self.histogram_bins,
        ):
            combo.setMaximumWidth(170)
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
        histogram_panel_layout.addLayout(histogram_controls)
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

    def set_documents(
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
            self.set_roi_available(True)
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
        self._completed_signature = ()
        self._histogram_specs = histogram_specs
        self._set_activity("Preparing analysis...", busy=True)
        self._refresh_timer.start()

    def clear(self) -> None:
        self._refresh_timer.stop()
        if self._worker is not None:
            self._worker.cancel()
        self._worker = None
        self._documents = []
        self._bounds = None
        self._request_signature = ()
        self._completed_signature = ()
        self._histogram_specs = []
        self.last_results = ()
        self.image_summary.setRowCount(0)
        self.table.setRowCount(0)
        self.statistics_delegate.set_separator_rows(set())
        self._clear_histogram_plots()
        self.roi_label.clear()
        self._set_activity("No images selected", busy=False)

    def refresh(self) -> None:
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
            self._completed_signature = ()

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
            return tuple(results)

        self._set_activity("Calculating...", busy=True)
        worker = TaskWorker(calculate)
        worker.signals.succeeded.connect(
            lambda _task_id, _document_id, _generation, result: self._on_result(
                signature, cache_keys, histogram_specs, result
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
    ) -> None:
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
        self._set_activity(f"Error: {error.message}", busy=False)

    def _on_finished(self, task_id: str) -> None:
        if self._worker is not None and self._worker.task_id == task_id:
            self._worker = None

    def _channels_changed(self, _checked: bool) -> None:
        if self.last_results and self._histogram_specs:
            self._render(self.last_results, self._histogram_specs)

    def _histogram_options_changed(self, _index: int) -> None:
        if self.last_results and self._histogram_specs:
            self._render(self.last_results, self._histogram_specs)

    def _histogram_bins_changed(self, _index: int) -> None:
        if not self._documents:
            return
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

    def _update_region_label(self) -> None:
        bounds = self._bounds
        if bounds is None:
            if not self._documents or self._documents[0].source is None:
                self.roi_label.clear()
                return
            source = self._documents[0].source
            bounds = RoiBounds(0, 0, source.shape[1], source.shape[0])
        self.roi_label.setText(
            f"x={bounds.x}, y={bounds.y}, width={bounds.width}, height={bounds.height}"
        )

    def _set_activity(self, text: str, *, busy: bool) -> None:
        self.status.setText(text)
        self.busy.setVisible(busy)
        self.activity.setVisible(bool(text) or busy)

    def _render(
        self,
        results: tuple[RoiAnalysisResult, ...],
        histogram_specs: list[tuple[int, tuple[float, float] | None]],
    ) -> None:
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

        overlay = self.histogram_mode.currentText() == "Overlay"
        self._arrange_histogram_plots(1 if overlay else len(results))
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
        self.table.resizeRowsToContents()
        self.table.viewport().update()
        self._set_activity("", busy=False)

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
        for plot in self.plots:
            self.histogram_layout.removeWidget(plot)
            plot.hide()
        visible_count = min(6, count)
        for index in range(visible_count):
            plot = self.plots[index]
            self.histogram_layout.addWidget(plot, index, 0)
            plot.show()
        for row in range(6):
            self.histogram_layout.setRowStretch(row, 1 if row < visible_count else 0)
        self.histogram_layout.setColumnStretch(0, 1)

    def _clear_histogram_plots(self) -> None:
        for plot, legend in zip(self.plots, self.legends, strict=True):
            plot.clear()
            legend.clear()
            plot.setTitle("")
            self._set_plot_axes_visible(plot, False)
            plot.hide()
        self._histogram_series = [[] for _index in range(6)]

    def copy_selection(self) -> None:
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
