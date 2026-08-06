from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from numpy.typing import NDArray
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import (
    LineProfileResult,
    LineSelection,
    selected_bayer_line_profile,
    selected_line_profile,
)
from pixelscope.ui.design_tokens import TOKENS, channel_button_style
from pixelscope.ui.plot_colors import channel_color, image_marker_symbol, line_profile_pen
from pixelscope.ui.plot_text import coordinate_header, middle_elide, plot_number
from pixelscope.workers.task_worker import TaskError, TaskWorker


class LineProfilePanel(QWidget):
    """Full-width asynchronous profile plot for the shared Alt-drag line."""

    def __init__(self) -> None:
        super().__init__()
        self._documents: list[ImageDocument] = []
        self._selection: LineSelection | None = None
        self._worker: TaskWorker | None = None
        self._request_signature: tuple[object, ...] = ()
        self.last_results: tuple[LineProfileResult, ...] = ()
        self._hover_lines: list[pg.InfiniteLine | None] = [None] * 6
        self._hover_texts: list[pg.TextItem | None] = [None] * 6
        self._plot_result_indices: list[list[int]] = [[] for _index in range(6)]
        self._plot_channel_filters: list[str | None] = [None] * 6
        self._profile_series: list[
            list[tuple[int, str, NDArray[np.float64], NDArray[np.float64]]]
        ] = [[] for _index in range(6)]
        self._reference_document_id: str | None = None
        self._reference_priority_ids: tuple[str, ...] = ()
        self._reference_locked = False

        self.status = QLabel("Alt+drag on an image to set a line profile")
        self.view_mode = QComboBox()
        self.view_mode.addItems(("Overlay", "Separate by image", "Separate by channel"))
        self.y_mode = QComboBox()
        self.y_mode.addItems(("Native value", "Normalized 0–1", "Difference from reference"))
        self.x_mode = QComboBox()
        self.x_mode.addItems(("Distance px", "Normalized distance"))
        self.reference_label = QLabel("Reference")
        self.reference_selector = QComboBox()
        self.reference_selector.setMaximumWidth(280)
        self.reference_label.hide()
        self.reference_selector.hide()
        self.channel_buttons: dict[str, QToolButton] = {}
        controls = QHBoxLayout()
        controls.setSpacing(TOKENS.spacing_sm)
        for label, combo in (
            ("View", self.view_mode),
            ("Y", self.y_mode),
            ("X", self.x_mode),
        ):
            controls.addWidget(QLabel(label))
            controls.addWidget(combo)
            controls.addSpacing(TOKENS.spacing_lg)
            combo.setMaximumWidth(170)
        controls.addWidget(self.reference_label)
        controls.addWidget(self.reference_selector)
        controls.addSpacing(TOKENS.spacing_lg)
        controls.addWidget(QLabel("Channels"))
        for name, color in (
            ("R", "#ff3b30"),
            ("G", "#24b34b"),
            ("Gr", "#35d05b"),
            ("Gb", "#168f38"),
            ("B", "#2684ff"),
        ):
            button = QToolButton()
            button.setText(name)
            button.setCheckable(True)
            button.setChecked(True)
            button.setStyleSheet(channel_button_style(color))
            button.toggled.connect(  # type: ignore[attr-defined]
                self._channels_changed
            )
            self.channel_buttons[name] = button
            controls.addWidget(button)
        for combo in (self.view_mode, self.y_mode, self.x_mode):
            combo.currentIndexChanged.connect(  # type: ignore[attr-defined]
                self._plot_options_changed
            )
        self.reference_selector.currentIndexChanged.connect(  # type: ignore[attr-defined]
            self._reference_changed
        )
        controls.addStretch(1)
        controls.addWidget(self.status)

        self.plot_grid = QWidget()
        self.plot_grid.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.plot_layout = QGridLayout(self.plot_grid)
        self.plot_layout.setContentsMargins(0, 0, 0, 0)
        self.plots: list[pg.PlotWidget] = []
        self.legends: list[pg.LegendItem] = []
        for plot_index in range(6):
            plot = pg.PlotWidget()
            plot.setLabel("left", "Pixel value")
            plot.setLabel("bottom", "Distance", units="px")
            plot.showGrid(x=True, y=True, alpha=0.25)
            plot.getViewBox().setDefaultPadding(0.08)
            plot.setMinimumHeight(180)
            plot.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Expanding,
            )
            self.plots.append(plot)
            self.legends.append(plot.addLegend(offset=(-10, 10)))
            plot.scene().sigMouseMoved.connect(
                lambda position, index=plot_index: self._on_plot_mouse_moved(position, index)
            )
            plot.hide()
        self.plot = self.plots[0]
        self.legend = self.legends[0]
        self._set_axes_visible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 4)
        layout.addLayout(controls)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(self.plot_grid)
        layout.addWidget(scroll, 1)

    @property
    def _hover_line(self) -> pg.InfiniteLine | None:
        """Compatibility alias for the primary overlay plot hover line."""

        return self._hover_lines[0]

    @property
    def _hover_text(self) -> pg.TextItem | None:
        """Compatibility alias for the primary overlay plot tooltip."""

        return self._hover_texts[0]

    def set_documents(
        self,
        documents: list[ImageDocument],
        selection: LineSelection | None,
        *,
        reference_priority_ids: tuple[str, ...] = (),
    ) -> None:
        self._documents = [document for document in documents if document.source is not None]
        self._selection = selection
        self._reference_priority_ids = reference_priority_ids
        self._sync_reference_selector()
        self.refresh()

    def set_reference_priority_ids(self, document_ids: tuple[str, ...]) -> None:
        previous_id = self._reference_document_id
        self._reference_priority_ids = document_ids
        self._sync_reference_selector()
        if (
            previous_id != self._reference_document_id
            and self.last_results
            and self.y_mode.currentText() == "Difference from reference"
        ):
            self._render(self.last_results)

    def clear(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
        self._worker = None
        self._documents = []
        self._selection = None
        self._reference_priority_ids = ()
        self._sync_reference_selector()
        self._request_signature = ()
        self.last_results = ()
        self._clear_plot()

    def clear_selection(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
        self._worker = None
        self._selection = None
        self._request_signature = ()
        self.last_results = ()
        self._clear_plot()

    def refresh(self) -> None:
        documents = self._documents
        selection = self._selection
        if not documents or selection is None:
            self.last_results = ()
            self._clear_plot()
            return
        signature: tuple[object, ...] = (
            tuple(
                (
                    document.document_id,
                    document.generation,
                    document.channel_layout,
                    getattr(document.raw_profile, "bayer_pattern", None),
                )
                for document in documents
            ),
            selection,
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
        cache_keys: list[tuple[object, ...]] = [
            (
                "line-profile",
                selection,
                document.generation,
                document.channel_layout,
                getattr(document.raw_profile, "bayer_pattern", None),
            )
            for document in documents
        ]
        cached_results = [
            document.statistics_cache.get(key)
            for document, key in zip(documents, cache_keys, strict=True)
        ]
        typed_cached = tuple(
            result for result in cached_results if isinstance(result, LineProfileResult)
        )
        if len(typed_cached) == len(cached_results):
            self.last_results = typed_cached
            self._render(typed_cached)
            return

        def calculate() -> tuple[LineProfileResult, ...]:
            results: list[LineProfileResult] = []
            for document, source, cached in zip(
                documents,
                sources,
                cached_results,
                strict=True,
            ):
                if source is None:
                    continue
                if isinstance(cached, LineProfileResult):
                    results.append(cached)
                    continue
                bayer_pattern = getattr(document.raw_profile, "bayer_pattern", None)
                if document.channel_layout == "BAYER" and isinstance(bayer_pattern, str):
                    results.append(selected_bayer_line_profile(source, selection, bayer_pattern))
                else:
                    results.append(selected_line_profile(source, selection))
            return tuple(results)

        self.status.setText("Calculating line profile...")
        worker = TaskWorker(calculate)
        worker.signals.succeeded.connect(
            lambda _task_id, _document_id, _generation, result: self._on_result(
                signature, cache_keys, result
            )
        )
        worker.signals.failed.connect(self._on_error)
        worker.signals.finished.connect(self._on_finished)
        self._worker = worker
        QThreadPool.globalInstance().start(worker)

    def _on_result(
        self,
        signature: tuple[object, ...],
        cache_keys: list[tuple[object, ...]],
        result: object,
    ) -> None:
        if signature != self._request_signature or not isinstance(result, tuple):
            return
        if len(result) != len(self._documents) or not all(
            isinstance(item, LineProfileResult) for item in result
        ):
            return
        self.last_results = tuple(result)
        for document, key, item in zip(self._documents, cache_keys, self.last_results, strict=True):
            document.statistics_cache[key] = item
        self._render(self.last_results)

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
        if self.last_results:
            self._render(self.last_results)

    def _plot_options_changed(self, _index: int) -> None:
        if self.y_mode.currentText() == "Difference from reference":
            self._reference_locked = self._reference_document_id is not None
        self._sync_reference_selector()
        if self.last_results:
            self._render(self.last_results)

    def _reference_changed(self, index: int) -> None:
        if index < 0:
            return
        document_id = self.reference_selector.itemData(index)
        if not isinstance(document_id, str):
            return
        changed = document_id != self._reference_document_id
        self._reference_document_id = document_id
        self._reference_locked = True
        if changed and self.last_results:
            self._render(self.last_results)

    def _sync_reference_selector(self) -> None:
        available_ids = [document.document_id for document in self._documents]
        selected_id = self._reference_document_id
        if selected_id not in available_ids:
            selected_id = None
            self._reference_locked = False
        if selected_id is None or not self._reference_locked:
            selected_id = next(
                (
                    document_id
                    for document_id in self._reference_priority_ids
                    if document_id in available_ids
                ),
                available_ids[0] if available_ids else None,
            )
        self._reference_document_id = selected_id
        if selected_id is not None and self.y_mode.currentText() == "Difference from reference":
            self._reference_locked = True

        self.reference_selector.blockSignals(True)
        self.reference_selector.clear()
        for index, document in enumerate(self._documents):
            label = f"{index + 1} · {self._document_label(document)}"
            self.reference_selector.addItem(label, document.document_id)
        selected_index = self.reference_selector.findData(selected_id)
        if selected_index >= 0:
            self.reference_selector.setCurrentIndex(selected_index)
        self.reference_selector.blockSignals(False)
        self._update_reference_visibility()

    def _update_reference_visibility(self) -> None:
        visible = self.y_mode.currentText() == "Difference from reference"
        self.reference_label.setVisible(visible)
        self.reference_selector.setVisible(visible)
        self.reference_selector.setEnabled(bool(self._documents))

    def _reference_index(self, results: tuple[LineProfileResult, ...]) -> int | None:
        if self._reference_document_id is None:
            return None
        for index, document in enumerate(self._documents[: len(results)]):
            if document.document_id == self._reference_document_id:
                return index
        return None

    def _render(self, results: tuple[LineProfileResult, ...]) -> None:
        for plot, legend in zip(self.plots, self.legends, strict=True):
            self.plot_layout.removeWidget(plot)
            plot.clear()
            legend.clear()
            plot.hide()
        self._plot_result_indices = [[] for _index in range(6)]
        self._plot_channel_filters = [None] * 6
        self._profile_series = [[] for _index in range(6)]
        channel_names = {name for result in results for name in result.channel_names if name != "A"}
        bayer = bool(channel_names.intersection({"Gr", "Gb"}))
        for name, button in self.channel_buttons.items():
            button.setVisible(name in channel_names or (name == "G" and not bayer))

        view_mode = self.view_mode.currentText()
        groups: list[tuple[str, list[tuple[int, LineProfileResult, str | None]]]]
        if view_mode == "Separate by image":
            groups = [
                (
                    f"{index + 1} · {self._document_label(self._documents[index])}",
                    [(index, result, None)],
                )
                for index, result in enumerate(results)
            ]
        elif view_mode == "Separate by channel":
            groups = [
                (
                    channel_name,
                    [
                        (index, result, channel_name)
                        for index, result in enumerate(results)
                        if channel_name in result.channel_names
                    ],
                )
                for channel_name in ("R", "G", "Gr", "Gb", "B")
                if channel_name in channel_names
            ]
        else:
            groups = [
                (
                    f"Overlay · {len(results)} images",
                    [(index, result, None) for index, result in enumerate(results)],
                )
            ]

        active_plot_count = min(len(groups), len(self.plots))
        for row in range(len(self.plots)):
            self.plot_layout.setRowStretch(row, 1 if row < active_plot_count else 0)

        for plot_index, (title, entries) in enumerate(groups[:6]):
            plot = self.plots[plot_index]
            self.plot_layout.addWidget(plot, plot_index, 0)
            plot.show()
            plot.setTitle(middle_elide(title))
            self._plot_result_indices[plot_index] = sorted(
                {image_index for image_index, _result, _filter in entries}
            )
            filters = {channel_filter for _image, _result, channel_filter in entries}
            self._plot_channel_filters[plot_index] = (
                next(iter(filters)) if len(filters) == 1 else None
            )
            for image_index, result, channel_filter in entries:
                for values, channel_name, positions in zip(
                    result.values,
                    result.channel_names,
                    result.positions,
                    strict=True,
                ):
                    if channel_name == "A" or (
                        channel_filter is not None and channel_name != channel_filter
                    ):
                        continue
                    if not self._channel_is_enabled(channel_name):
                        continue
                    x_values, y_values = self._transformed_profile(
                        image_index,
                        channel_name,
                        positions,
                        values,
                        results,
                    )
                    legend_name = f"{image_index + 1} · {channel_name}"
                    curve_name = legend_name if view_mode == "Separate by image" else None
                    plot.plot(
                        x_values,
                        y_values,
                        pen=line_profile_pen(channel_name),
                        antialias=True,
                        connect="finite",
                        name=curve_name,
                    )
                    self._profile_series[plot_index].append(
                        (image_index, channel_name, x_values, y_values)
                    )
                    if view_mode != "Separate by image":
                        marker_indices = self._marker_indices(x_values.size)
                        marker = pg.ScatterPlotItem(
                            x=x_values[marker_indices],
                            y=y_values[marker_indices],
                            symbol=image_marker_symbol(image_index),
                            size=7.0,
                            pen=pg.mkPen(channel_color(channel_name), width=0.8),
                            brush=pg.mkBrush(channel_color(channel_name)),
                        )
                        marker.setZValue(3)
                        plot.addItem(marker)
                        self.legends[plot_index].addItem(marker, legend_name)
            plot.setLabel(
                "left",
                "Normalized"
                if self.y_mode.currentText() == "Normalized 0–1"
                else "Difference"
                if self.y_mode.currentText() == "Difference from reference"
                else "Pixel value",
            )
            plot.setLabel(
                "bottom",
                "Normalized distance"
                if self.x_mode.currentText() == "Normalized distance"
                else "Distance",
                units=None if self.x_mode.currentText() == "Normalized distance" else "px",
            )
            for axis in ("left", "bottom"):
                plot.showAxis(axis)
            plot.getViewBox().autoRange(padding=0.08)
            self._create_hover_items(plot_index)
        selection = self._selection
        if selection is not None:
            self.status.setText(
                f"({selection.x1}, {selection.y1}) to ({selection.x2}, {selection.y2})"
            )

    @staticmethod
    def _marker_indices(sample_count: int, target_count: int = 18) -> NDArray[np.intp]:
        """Spread identity markers across a curve without obscuring its shape."""

        if sample_count <= 0:
            return np.empty(0, dtype=np.intp)
        if sample_count <= target_count:
            return np.arange(sample_count, dtype=np.intp)
        return np.unique(np.linspace(1, sample_count - 2, target_count, dtype=np.intp))

    def _transformed_profile(
        self,
        image_index: int,
        channel_name: str,
        positions: NDArray[np.float64],
        values: NDArray[np.float64],
        results: tuple[LineProfileResult, ...],
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        x_values = positions.astype(np.float64, copy=False)
        if self.x_mode.currentText() == "Normalized distance" and x_values.size > 1:
            span = float(x_values[-1] - x_values[0])
            if span > 0:
                x_values = (x_values - x_values[0]) / span
        y_values = values.astype(np.float64, copy=False)
        if self.y_mode.currentText() == "Normalized 0–1":
            document = self._documents[image_index]
            y_values = y_values / float((1 << document.bit_depth) - 1)
        elif self.y_mode.currentText() == "Difference from reference":
            reference_result_index = self._reference_index(results)
            if reference_result_index is not None:
                if image_index == reference_result_index:
                    y_values = np.zeros_like(y_values)
                else:
                    reference = results[reference_result_index]
                    if channel_name in reference.channel_names:
                        reference_index = reference.channel_names.index(channel_name)
                        reference_x = reference.positions[reference_index]
                        reference_y = reference.values[reference_index]
                        y_values = y_values - np.interp(
                            positions,
                            reference_x,
                            reference_y,
                        )
        return x_values, y_values

    def _channel_is_enabled(self, channel_name: str) -> bool:
        button = self.channel_buttons.get(channel_name)
        return button is None or button.isChecked()

    def _clear_plot(self) -> None:
        for plot, legend in zip(self.plots, self.legends, strict=True):
            plot.clear()
            legend.clear()
            plot.hide()
        self._hover_lines = [None] * 6
        self._hover_texts = [None] * 6
        self._plot_result_indices = [[] for _index in range(6)]
        self._plot_channel_filters = [None] * 6
        self._profile_series = [[] for _index in range(6)]
        self._set_axes_visible(False)
        self.status.setText("Alt+drag on an image to set a line profile")

    def _create_hover_items(self, plot_index: int) -> None:
        line = pg.InfiniteLine(
            angle=90,
            movable=False,
            pen=pg.mkPen("#d0d0d0", width=0.7),
        )
        hint = pg.TextItem(
            anchor=(0, 1),
            fill=pg.mkBrush(24, 24, 24, 225),
            border=pg.mkPen("#808080", width=0.7),
        )
        line.setZValue(20)
        hint.setZValue(21)
        self.plots[plot_index].addItem(line, ignoreBounds=True)
        self.plots[plot_index].addItem(hint, ignoreBounds=True)
        line.hide()
        hint.hide()
        self._hover_lines[plot_index] = line
        self._hover_texts[plot_index] = hint

    def _on_plot_mouse_moved(self, position: object, plot_index: int = 0) -> None:
        line = self._hover_lines[plot_index]
        hint = self._hover_texts[plot_index]
        plot = self.plots[plot_index]
        series = self._profile_series[plot_index]
        if (
            line is None
            or hint is None
            or not series
            or not plot.sceneBoundingRect().contains(position)
        ):
            self._hide_hover(plot_index)
            return

        point = plot.getViewBox().mapSceneToView(position)
        primary_x = series[0][2]
        if primary_x.size == 0 or point.x() < primary_x[0] or point.x() > primary_x[-1]:
            self._hide_hover(plot_index)
            return
        primary_index = int(np.argmin(np.abs(primary_x - point.x())))
        cursor_x = float(primary_x[primary_index])

        rows: list[str] = []
        for image_index, channel_name, x_values, y_values in series:
            if x_values.size == 0 or y_values.size == 0:
                continue
            nearest = int(np.argmin(np.abs(x_values - cursor_x)))
            sample_x = float(x_values[nearest])
            value = float(y_values[nearest])
            position_suffix = (
                ""
                if np.isclose(sample_x, cursor_x, rtol=0.0, atol=1e-9)
                else f"@{plot_number(sample_x)}"
            )
            rows.append(
                f"<tr><td><b>{image_index + 1}</b></td>"
                f'<td style="color:{channel_color(channel_name)}; padding-left:7px">'
                f"{channel_name}{position_suffix}</td>"
                f'<td style="padding-left:10px; text-align:right">'
                f"{plot_number(value)}</td></tr>"
            )
        if not rows:
            self._hide_hover(plot_index)
            return

        view_range = plot.getViewBox().viewRange()
        y_anchor = 0 if point.y() > sum(view_range[1]) / 2 else 1
        line.setPos(cursor_x)
        hint.setAnchor((1, y_anchor))
        normalized = self.x_mode.currentText() == "Normalized distance"
        header = coordinate_header(
            "Normalized distance" if normalized else "Distance",
            cursor_x,
            None if normalized else "px",
        )
        hint.setHtml(f"<b>{header}</b><table cellspacing='1'>{''.join(rows)}</table>")
        x_range, y_range = view_range
        x_padding = (x_range[1] - x_range[0]) * 0.04
        y_padding = (y_range[1] - y_range[0]) * 0.08
        hint_x = min(max(cursor_x, x_range[0] + x_padding), x_range[1] - x_padding)
        hint_y = min(max(point.y(), y_range[0] + y_padding), y_range[1] - y_padding)
        hint.setPos(hint_x, hint_y)
        line.show()
        hint.show()

    def _hide_hover(self, plot_index: int = 0) -> None:
        line = self._hover_lines[plot_index]
        hint = self._hover_texts[plot_index]
        if line is not None:
            line.hide()
        if hint is not None:
            hint.hide()

    def _set_axes_visible(self, visible: bool) -> None:
        for plot in self.plots:
            for axis in ("left", "bottom"):
                if visible:
                    plot.showAxis(axis)
                else:
                    plot.hideAxis(axis)

    @staticmethod
    def _document_label(document: ImageDocument) -> str:
        if document.source_path is None:
            return document.display_name
        return f"{document.source_path.parent.name} / {document.display_name}"

    def shutdown(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
