from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pixelscope.core.bayer import analyze_bayer_roi
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.roi import RoiAnalysisResult, RoiBounds, analyze_roi
from pixelscope.ui.plot_colors import channel_color, comparison_pen
from pixelscope.workers.task_worker import TaskError, TaskWorker


class KiloAxisItem(pg.AxisItem):  # type: ignore[misc]
    """Count axis that abbreviates thousands with a K suffix."""

    def tickStrings(  # noqa: N802
        self, values: list[float], scale: float, spacing: float
    ) -> list[str]:
        del scale, spacing
        return [f"{value / 1000:g}K" if abs(value) >= 1000 else f"{value:g}" for value in values]


def comparison_labels(documents: list[ImageDocument]) -> list[str]:
    """Return basenames only; numeric column headers disambiguate duplicates."""

    return [document.display_name for document in documents]


def automatic_histogram_spec(
    document: ImageDocument,
) -> tuple[int, tuple[float, float] | None]:
    """Select exact integer code bins from effective bit depth, capped at 16 bits."""

    source = document.source
    if source is None:
        raise ValueError("histogram requires a loaded document")
    effective_depth = min(max(document.bit_depth, 1), 16)
    bins = 1 << effective_depth
    if np.issubdtype(source.dtype, np.unsignedinteger):
        return bins, (0.0, float(1 << effective_depth))
    if np.issubdtype(source.dtype, np.signedinteger):
        limit = 1 << (effective_depth - 1)
        return bins, (float(-limit), float(limit))
    return min(bins, 4096), None


class ComparisonAnalysisPanel(QWidget):
    """Transposed per-image statistics and channel-faithful histogram overlays."""

    _METRICS = (
        "Pixels",
        "Bit Depth",
        "Min",
        "Max",
        "Mean",
        "Std",
        "P1",
        "P50",
        "P99",
    )

    def __init__(self) -> None:
        super().__init__()
        self._documents: list[ImageDocument] = []
        self._bounds: RoiBounds | None = None
        self._worker: TaskWorker | None = None
        self._request_signature: tuple[object, ...] = ()
        self._histogram_specs: list[tuple[int, tuple[float, float] | None]] = []
        self.last_results: tuple[RoiAnalysisResult, ...] = ()
        self._pool = QThreadPool.globalInstance()

        self.status = QLabel("No images selected")
        self.roi_label = QLabel("Full image")
        self.channel_buttons: dict[str, QToolButton] = {}
        controls = QHBoxLayout()
        controls.addWidget(self.roi_label)
        controls.addSpacing(8)
        controls.addWidget(QLabel("Channels"))
        for name, color in (("R", "#ff3b30"), ("G", "#24b34b"), ("B", "#2684ff")):
            button = QToolButton()
            button.setText(name)
            button.setCheckable(True)
            button.setChecked(True)
            button.setStyleSheet(f"QToolButton:checked {{ color: {color}; font-weight: bold; }}")
            button.toggled.connect(  # type: ignore[attr-defined]
                self._channels_changed
            )
            self.channel_buttons[name] = button
            controls.addWidget(button)
        controls.addStretch(1)
        controls.addWidget(self.status)

        self.table = QTableWidget(len(self._METRICS), 0)
        self.table.setVerticalHeaderLabels(self._METRICS)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setMinimumSectionSize(80)
        self.table.horizontalHeader().setStyleSheet(
            "QHeaderView::section {"
            "background-color: #3b3f46; color: white; font-weight: bold;"
            "border: 1px solid #666b73; padding: 5px;"
            "}"
        )

        self.histogram_grid = QWidget()
        self.histogram_layout = QGridLayout(self.histogram_grid)
        self.histogram_layout.setContentsMargins(0, 0, 0, 0)
        self.histogram_layout.setSpacing(3)
        self.plots: list[pg.PlotWidget] = []
        self.legends: list[pg.LegendItem] = []
        for _index in range(6):
            plot = pg.PlotWidget(axisItems={"left": KiloAxisItem(orientation="left")})
            plot.setLabel("left", "Count")
            plot.setLabel("bottom", "Pixel value")
            plot.showGrid(x=True, y=True, alpha=0.25)
            plot.getViewBox().setDefaultPadding(0.08)
            legend = plot.addLegend(offset=(-8, 8))
            self.plots.append(plot)
            self.legends.append(legend)
            self._set_plot_axes_visible(plot, False)
            plot.hide()
        # Compatibility aliases for callers that inspect the first histogram pane.
        self.plot = self.plots[0]
        self.legend = self.legends[0]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addLayout(controls)
        layout.addWidget(self.table, 1)

    def set_documents(self, documents: list[ImageDocument], bounds: RoiBounds | None) -> None:
        self._documents = [document for document in documents if document.source is not None]
        self._bounds = bounds
        if bounds is None:
            self.roi_label.setText("Full image")
        else:
            self.roi_label.setText(
                f"ROI x={bounds.x}, y={bounds.y}, {bounds.width} x {bounds.height}"
            )
        self.refresh()

    def clear(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
        self._worker = None
        self._documents = []
        self._bounds = None
        self._request_signature = ()
        self._histogram_specs = []
        self.last_results = ()
        self.table.setColumnCount(0)
        self._clear_histogram_plots()
        self.status.setText("No images selected")
        self.roi_label.setText("Full image")

    def refresh(self) -> None:
        documents = self._documents
        if not documents:
            self.clear()
            return
        bounds = self._bounds
        histogram_specs = [automatic_histogram_spec(document) for document in documents]
        self._histogram_specs = histogram_specs
        signature: tuple[object, ...] = (
            tuple((document.document_id, document.generation) for document in documents),
            bounds,
            tuple(histogram_specs),
        )
        self._request_signature = signature
        if self._worker is not None:
            self._worker.cancel()

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

        self.status.setText("Calculating...")
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
        self._render(typed_result, histogram_specs)

    def _on_error(
        self,
        _task_id: str,
        _document_id: str | None,
        _generation: int,
        error: TaskError,
    ) -> None:
        self.status.setText(f"Error: {error.message}")

    def _on_finished(self, task_id: str) -> None:
        if self._worker is not None and self._worker.task_id == task_id:
            self._worker = None

    def _channels_changed(self, _checked: bool) -> None:
        if self.last_results and self._histogram_specs:
            self._render(self.last_results, self._histogram_specs)

    def _render(
        self,
        results: tuple[RoiAnalysisResult, ...],
        histogram_specs: list[tuple[int, tuple[float, float] | None]],
    ) -> None:
        labels = comparison_labels(self._documents)
        metrics: list[tuple[str, ...]] = []
        for document, result in zip(self._documents, results, strict=True):
            channels = [
                (name, statistics)
                for name, statistics in zip(
                    result.channel_names,
                    result.channel_statistics,
                    strict=True,
                )
                if name != "A"
            ]

            metrics.append(
                (
                    f"{result.pixel_count:,}",
                    f"{document.bit_depth}-bit",
                    "\n".join(f"{name}: {statistics.minimum:.6g}" for name, statistics in channels),
                    "\n".join(f"{name}: {statistics.maximum:.6g}" for name, statistics in channels),
                    "\n".join(f"{name}: {statistics.mean:.6g}" for name, statistics in channels),
                    "\n".join(
                        f"{name}: {statistics.standard_deviation:.6g}"
                        for name, statistics in channels
                    ),
                    "\n".join(
                        f"{name}: {statistics.percentiles[1.0]:.6g}"
                        for name, statistics in channels
                    ),
                    "\n".join(
                        f"{name}: {statistics.percentiles[50.0]:.6g}"
                        for name, statistics in channels
                    ),
                    "\n".join(
                        f"{name}: {statistics.percentiles[99.0]:.6g}"
                        for name, statistics in channels
                    ),
                )
            )

        self.table.setColumnCount(len(results))
        elided_labels = [
            f"{index + 1}\n"
            + self.fontMetrics().elidedText(label, Qt.TextElideMode.ElideMiddle, 135)
            for index, label in enumerate(labels)
        ]
        self.table.setHorizontalHeaderLabels(elided_labels)
        for column, (document, result, values) in enumerate(
            zip(self._documents, results, metrics, strict=True)
        ):
            header = self.table.horizontalHeaderItem(column)
            header.setToolTip(str(document.source_path or document.display_name))
            channel_text = "\n".join(
                f"{name}: mean {channel.mean:.6g}, std {channel.standard_deviation:.6g}"
                for name, channel in zip(
                    result.channel_names,
                    result.channel_statistics,
                    strict=True,
                )
                if name != "A"
            )
            for row, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(channel_text)
                self.table.setItem(row, column, item)

        self._arrange_histogram_plots(len(results))
        for image_index, (document, result) in enumerate(
            zip(self._documents, results, strict=True)
        ):
            plot = self.plots[image_index]
            legend = self.legends[image_index]
            plot.clear()
            legend.clear()
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
                fill_color.setAlpha(75)
                plot.plot(
                    edges,
                    counts,
                    stepMode="center",
                    fillLevel=0.0,
                    brush=pg.mkBrush(fill_color),
                    pen=comparison_pen(channel_name, 0, width=0.7),
                    name=channel_name,
                    antialias=True,
                )
            title = document.display_name
            if len(title) > 36:
                title = f"{title[:17]}...{title[-16:]}"
            plot.setTitle(f"{image_index + 1}  {title}")
            self._set_plot_axes_visible(plot, True)
            plot.getViewBox().autoRange(padding=0.08)
        self.table.resizeRowsToContents()
        self.status.clear()

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

    @staticmethod
    def _set_plot_axes_visible(plot: pg.PlotWidget, visible: bool) -> None:
        for axis in ("left", "bottom"):
            if visible:
                plot.showAxis(axis)
            else:
                plot.hideAxis(axis)

    def shutdown(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
