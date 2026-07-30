from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
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
from pixelscope.ui.plot_colors import channel_color, comparison_pen
from pixelscope.workers.task_worker import TaskError, TaskWorker


class LineProfilePanel(QWidget):
    """Full-width asynchronous profile plot for the shared Alt-drag line."""

    _MARKER_SYMBOLS = ("o", "s", "t", "d", "+", "star")

    def __init__(self) -> None:
        super().__init__()
        self._documents: list[ImageDocument] = []
        self._selection: LineSelection | None = None
        self._worker: TaskWorker | None = None
        self._request_signature: tuple[object, ...] = ()
        self.last_results: tuple[LineProfileResult, ...] = ()
        self._hover_line: pg.InfiniteLine | None = None
        self._hover_text: pg.TextItem | None = None

        self.status = QLabel("Alt+drag on an image to set a line profile")
        self.channel_buttons: dict[str, QToolButton] = {}
        controls = QHBoxLayout()
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

        self.plot = pg.PlotWidget()
        self.plot.setLabel("left", "Pixel value")
        self.plot.setLabel("bottom", "Distance", units="px")
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.plot.getViewBox().setDefaultPadding(0.08)
        self.legend = self.plot.addLegend(offset=(-10, 10))
        self.plot.scene().sigMouseMoved.connect(self._on_plot_mouse_moved)
        self._set_axes_visible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 4)
        layout.addLayout(controls)
        layout.addWidget(self.plot, 1)

    def set_documents(
        self, documents: list[ImageDocument], selection: LineSelection | None
    ) -> None:
        self._documents = [document for document in documents if document.source is not None]
        self._selection = selection
        self.refresh()

    def clear(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
        self._worker = None
        self._documents = []
        self._selection = None
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

    def _render(self, results: tuple[LineProfileResult, ...]) -> None:
        self.plot.clear()
        self.legend.clear()
        for image_index, result in enumerate(results):
            for values, channel_name, x_values in zip(
                result.values,
                result.channel_names,
                result.positions,
                strict=True,
            ):
                if channel_name == "A":
                    continue
                control_name = self._channel_control_name(channel_name)
                if (
                    control_name in self.channel_buttons
                    and not self.channel_buttons[control_name].isChecked()
                ):
                    continue
                self.plot.plot(
                    x_values,
                    values,
                    pen=comparison_pen(channel_name, 0, width=0.8),
                    antialias=True,
                    connect="finite",
                )
                marker_step = max(1, int(np.ceil(len(x_values) / 70)))
                marker_indices = np.arange(0, len(x_values), marker_step)
                if marker_indices[-1] != len(x_values) - 1:
                    marker_indices = np.append(marker_indices, len(x_values) - 1)
                color = channel_color(channel_name)
                markers = pg.ScatterPlotItem(
                    x=x_values[marker_indices],
                    y=values[marker_indices],
                    symbol=self._MARKER_SYMBOLS[image_index % len(self._MARKER_SYMBOLS)],
                    size=5,
                    pen=pg.mkPen(color, width=0.7),
                    brush=pg.mkBrush(color),
                    pxMode=True,
                )
                self.plot.addItem(markers)
                self.legend.addItem(markers, f"{image_index + 1}-{channel_name}")
        self._create_hover_items()
        self._set_axes_visible(True)
        self.plot.getViewBox().autoRange(padding=0.08)
        selection = self._selection
        if selection is not None:
            self.status.setText(
                f"({selection.x1}, {selection.y}) to ({selection.x2}, {selection.y})"
            )

    def _clear_plot(self) -> None:
        self.plot.clear()
        self.legend.clear()
        self._hover_line = None
        self._hover_text = None
        self._set_axes_visible(False)
        self.status.setText("Alt+drag on an image to set a line profile")

    def _create_hover_items(self) -> None:
        self._hover_line = pg.InfiniteLine(
            angle=90,
            movable=False,
            pen=pg.mkPen("#d0d0d0", width=0.7),
        )
        self._hover_text = pg.TextItem(
            anchor=(0, 1),
            fill=pg.mkBrush(24, 24, 24, 225),
            border=pg.mkPen("#808080", width=0.7),
        )
        self._hover_line.setZValue(20)
        self._hover_text.setZValue(21)
        self.plot.addItem(self._hover_line, ignoreBounds=True)
        self.plot.addItem(self._hover_text, ignoreBounds=True)
        self._hover_line.hide()
        self._hover_text.hide()

    def _on_plot_mouse_moved(self, position: object) -> None:
        line = self._hover_line
        hint = self._hover_text
        if (
            line is None
            or hint is None
            or not self.last_results
            or not self.plot.sceneBoundingRect().contains(position)
        ):
            self._hide_hover()
            return

        point = self.plot.getViewBox().mapSceneToView(position)
        sample_index = int(round(point.x()))
        max_index = int(
            max(
                float(np.max(positions))
                for result in self.last_results
                for positions in result.positions
            )
        )
        if sample_index < 0 or sample_index > max_index:
            self._hide_hover()
            return

        rows: list[str] = []
        for image_index, result in enumerate(self.last_results):
            channel_values: list[str] = []
            for values, channel_name, positions in zip(
                result.values,
                result.channel_names,
                result.positions,
                strict=True,
            ):
                if channel_name == "A":
                    continue
                control_name = self._channel_control_name(channel_name)
                if (
                    control_name in self.channel_buttons
                    and not self.channel_buttons[control_name].isChecked()
                ):
                    continue
                nearest = int(np.argmin(np.abs(positions - sample_index)))
                value = values[nearest]
                source_position = int(positions[nearest])
                color = channel_color(channel_name)
                position_suffix = f"@{source_position}" if source_position != sample_index else ""
                channel_values.append(
                    f'<td style="color:{color}; padding-left:6px">'
                    f"{channel_name}{position_suffix}: {value:.6g}</td>"
                )
            rows.append(f"<tr><td><b>{image_index + 1}</b></td>{''.join(channel_values)}</tr>")
        view_range = self.plot.getViewBox().viewRange()
        x_anchor = 1 if point.x() > sum(view_range[0]) / 2 else 0
        y_anchor = 0 if point.y() > sum(view_range[1]) / 2 else 1
        line.setPos(sample_index)
        hint.setAnchor((x_anchor, y_anchor))
        hint.setHtml(
            f"<b>x={sample_index} px</b>" f"<table cellspacing='1'>{''.join(rows)}</table>"
        )
        hint.setPos(sample_index, point.y())
        line.show()
        hint.show()

    @staticmethod
    def _channel_control_name(channel_name: str) -> str:
        return "G" if channel_name in ("Gr", "Gb") else channel_name

    def _hide_hover(self) -> None:
        if self._hover_line is not None:
            self._hover_line.hide()
        if self._hover_text is not None:
            self._hover_text.hide()

    def _set_axes_visible(self, visible: bool) -> None:
        for axis in ("left", "bottom"):
            if visible:
                self.plot.showAxis(axis)
            else:
                self.plot.hideAxis(axis)

    def shutdown(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
