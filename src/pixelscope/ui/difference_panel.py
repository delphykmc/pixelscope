from __future__ import annotations

from math import isinf

import numpy as np
from numpy.typing import NDArray
from PySide6.QtCore import Qt, QThreadPool, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pixelscope.core.bayer import bayer_channel_positions, split_bayer_channels
from pixelscope.core.diff_engine import (
    DifferenceMetrics,
    absolute_difference_metrics,
    compact_absolute_difference,
    validate_difference_documents,
)
from pixelscope.core.difference_cache import (
    CachedDifferenceMap,
    DifferenceCacheKey,
    DifferenceMapCache,
)
from pixelscope.core.display_transform import (
    render_absolute_difference,
    render_threshold_mask,
)
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.performance_settings import DEFAULT_DIFFERENCE_CACHE_BYTES
from pixelscope.core.roi import RoiBounds
from pixelscope.ui.design_tokens import TOKENS, primary_button_style
from pixelscope.workers.task_worker import TaskError, TaskWorker


class DifferencePanel(QWidget):
    """Asynchronous native difference analysis with derived channel previews."""

    result_ready = Signal(object, object, object)
    preview_updated = Signal(object, object, object)

    def __init__(
        self,
        difference_cache_budget_bytes: int = DEFAULT_DIFFERENCE_CACHE_BYTES,
    ) -> None:
        super().__init__()
        self._documents: list[ImageDocument] = []
        self._active_roi: RoiBounds | None = None
        self._worker: TaskWorker | None = None
        self._worker_key: tuple[object, ...] | None = None
        self._map_cache = DifferenceMapCache(difference_cache_budget_bytes)
        self._metric_cache: dict[tuple[object, ...], DifferenceMetrics] = {}
        self._preview_key: tuple[object, ...] | None = None
        self._preview_value: NDArray[np.uint8] | None = None
        self.last_result: DifferenceMetrics | None = None

        self.a_selector = QComboBox()
        self.b_selector = QComboBox()
        self.channel = QComboBox()
        self.region = QComboBox()
        self.region.addItems(("Full image", "Active ROI"))
        self.mode = QComboBox()
        self.mode.addItems(("Absolute", "Mask"))
        self.gain = self._integer_control(1, 1000, 1)
        self.threshold = self._integer_control(0, 2_147_483_647, 10)

        self.calculate = QPushButton("Calculate")
        self.calculate.setObjectName("primaryAction")
        self.calculate.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.calculate.setMinimumHeight(30)
        self.calculate.setStyleSheet(primary_button_style())
        self.status = QLabel("Select a compatible image pair")
        self.metric_scope = QLabel("Metrics scope: —")
        self.metric_scope.setWordWrap(True)

        sources = QGridLayout()
        sources.setHorizontalSpacing(TOKENS.spacing_sm)
        sources.setVerticalSpacing(TOKENS.spacing_sm)
        sources.addWidget(QLabel("Image 1"), 0, 0)
        sources.addWidget(self.a_selector, 0, 1, 1, 3)
        sources.addWidget(QLabel("Image 2"), 1, 0)
        sources.addWidget(self.b_selector, 1, 1, 1, 3)
        sources.setColumnStretch(1, 1)

        options = QGridLayout()
        options.setHorizontalSpacing(TOKENS.spacing_sm)
        options.setVerticalSpacing(TOKENS.spacing_sm)
        options.addWidget(QLabel("Channel"), 0, 0)
        options.addWidget(self.channel, 0, 1)
        options.addWidget(QLabel("Mode"), 0, 2)
        options.addWidget(self.mode, 0, 3)
        options.addWidget(QLabel("Threshold"), 1, 0)
        options.addWidget(self.threshold, 1, 1)
        options.addWidget(QLabel("Gain"), 1, 2)
        options.addWidget(self.gain, 1, 3)
        options.setColumnStretch(1, 1)
        options.setColumnStretch(3, 1)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        metric_region = QHBoxLayout()
        metric_region.setSpacing(TOKENS.spacing_sm)
        metric_region.addWidget(QLabel("Metric region"))
        metric_region.addWidget(self.region, 1)

        metric_names = (
            "MAE",
            "MSE",
            "RMSE",
            "PSNR",
            "P95",
            "P99",
            "Max difference",
            "Non-zero ratio",
        )
        self.metrics = QTableWidget(len(metric_names), 2)
        self.metrics.setHorizontalHeaderLabels(("Metric", "Value"))
        self.metrics.verticalHeader().hide()
        self.metrics.horizontalHeader().setStretchLastSection(True)
        for row, name in enumerate(metric_names):
            self.metrics.setItem(row, 0, QTableWidgetItem(name))

        action_row = QHBoxLayout()
        action_row.addWidget(self.calculate)
        action_row.addWidget(self.status, 1)
        layout = QVBoxLayout(self)
        layout.setSpacing(TOKENS.spacing_md)
        layout.addLayout(action_row)
        layout.addLayout(sources)
        layout.addLayout(options)
        layout.addWidget(separator)
        layout.addLayout(metric_region)
        layout.addWidget(self.metric_scope)
        layout.addWidget(self.metrics, 1)

        self._display_timer = QTimer(self)
        self._display_timer.setSingleShot(True)
        self._display_timer.setInterval(180)
        self._display_timer.timeout.connect(self._apply_display_update)  # type: ignore[attr-defined]

        for selector in (self.a_selector, self.b_selector):
            selector.currentIndexChanged.connect(  # type: ignore[attr-defined]
                self._pair_changed
            )
        self.channel.currentIndexChanged.connect(self._channel_changed)  # type: ignore[attr-defined]
        self.region.currentIndexChanged.connect(self._metric_region_changed)  # type: ignore[attr-defined]
        self.mode.currentIndexChanged.connect(self._display_options_changed)  # type: ignore[attr-defined]
        for spin_box in (self.gain, self.threshold):
            spin_box.valueChanged.connect(self._schedule_display_update)  # type: ignore[attr-defined]
        self.calculate.clicked.connect(self.calculate_difference)  # type: ignore[attr-defined]
        self._update_control_states()
        self._clear_metrics()

    @property
    def difference_cache(self) -> DifferenceMapCache:
        """Expose read-only cache diagnostics and explicit cache operations."""

        return self._map_cache

    @staticmethod
    def _integer_control(minimum: int, maximum: int, value: int) -> QSpinBox:
        control = QSpinBox()
        control.setRange(minimum, maximum)
        control.setValue(value)
        control.setKeyboardTracking(True)
        return control

    def set_display_defaults(self, threshold: int, gain: int) -> None:
        """Apply persisted Difference display defaults to the live controls."""

        self.threshold.setValue(threshold)
        self.gain.setValue(gain)

    def set_documents(
        self,
        documents: list[ImageDocument],
        pair: tuple[str, str] | None,
        active_roi: RoiBounds | None = None,
    ) -> None:
        previous_key = self._cache_key()
        previous_metric_key = self._metric_key()
        previous_status = self.status.text()
        previous_roi = self._active_roi
        current_a = self.a_selector.currentData()
        current_b = self.b_selector.currentData()
        self._documents = [document for document in documents if document.source is not None]
        evicted = self._map_cache.discard_stale_generations(
            {document.document_id: document.generation for document in self._documents}
        )
        self._drop_dependent_cache_entries(evicted)
        self._active_roi = active_roi
        if previous_roi != active_roi:
            self.region.blockSignals(True)
            self.region.setCurrentText("Active ROI" if active_roi is not None else "Full image")
            self.region.blockSignals(False)
        for selector in (self.a_selector, self.b_selector):
            selector.blockSignals(True)
            selector.clear()
            for document in self._documents:
                parent = (
                    document.source_path.parent.name
                    if document.source_path is not None
                    else "Generated"
                )
                selector.addItem(
                    f"{parent} / {document.display_name}",
                    document.document_id,
                )
            selector.blockSignals(False)
        target_a = pair[0] if pair is not None else current_a
        target_b = pair[1] if pair is not None else current_b
        available_ids = [document.document_id for document in self._documents]
        if len(available_ids) >= 2 and (
            target_a not in available_ids or target_b not in available_ids or target_a == target_b
        ):
            target_a, target_b = available_ids[:2]
        self.a_selector.blockSignals(True)
        self.b_selector.blockSignals(True)
        self._select_id(self.a_selector, target_a, fallback=0)
        self._select_id(self.b_selector, target_b, fallback=1)
        self.a_selector.blockSignals(False)
        self.b_selector.blockSignals(False)
        self._update_channels()
        if previous_key != self._cache_key() or previous_roi != active_roi:
            self.last_result = None
            self._clear_metrics()
        self._validate()
        self._restore_or_refresh_metrics(
            previous_status if previous_metric_key == self._metric_key() else None
        )

    def set_active_roi(self, bounds: RoiBounds | None) -> None:
        if bounds == self._active_roi:
            return
        self._active_roi = bounds
        self.region.blockSignals(True)
        self.region.setCurrentText("Active ROI" if bounds is not None else "Full image")
        self.region.blockSignals(False)
        self.last_result = None
        self._clear_metrics()
        self._validate()
        self._restore_or_refresh_metrics()

    def _select_id(self, selector: QComboBox, document_id: object, fallback: int) -> None:
        index = selector.findData(document_id)
        selector.setCurrentIndex(index if index >= 0 else min(fallback, selector.count() - 1))

    def selected_documents(self) -> tuple[ImageDocument, ImageDocument] | None:
        by_id = {document.document_id: document for document in self._documents}
        a = by_id.get(str(self.a_selector.currentData()))
        b = by_id.get(str(self.b_selector.currentData()))
        return (a, b) if a is not None and b is not None and a is not b else None

    def _pair_changed(self, _value: object = None) -> None:
        self._cancel_worker()
        self.last_result = None
        self._clear_metrics()
        self._update_channels()
        self._validate()
        self._restore_or_refresh_metrics()

    def _channel_changed(self, _value: object = None) -> None:
        self._cancel_worker()
        self.last_result = None
        self._clear_metrics()
        self._update_metric_scope()
        self._validate()
        self._schedule_display_update()
        self._restore_or_refresh_metrics()

    def _metric_region_changed(self, _value: object = None) -> None:
        self.last_result = None
        self._clear_metrics()
        self._validate()
        self._restore_or_refresh_metrics()

    def _display_options_changed(self, _value: object = None) -> None:
        self._update_control_states()
        self._schedule_display_update()

    def _schedule_display_update(self, _value: object = None) -> None:
        if self.has_cached_map():
            self.status.setText("Updating display…")
            self._display_timer.start()

    def _apply_display_update(self) -> None:
        cached = self.cached_display_for_current()
        if cached is None:
            return
        self.status.setText("Ready")
        self.preview_updated.emit(*cached)

    def _clear_metrics(self) -> None:
        for row in range(self.metrics.rowCount()):
            item = QTableWidgetItem("—")
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.metrics.setItem(row, 1, item)

    def _update_channels(self) -> None:
        pair = self.selected_documents()
        current = self.channel.currentText()
        self.channel.blockSignals(True)
        self.channel.clear()
        if pair is not None and pair[0].channel_layout == "BAYER":
            self.channel.addItems(("Mosaic", "R", "Gr", "Gb", "B"))
        else:
            self.channel.addItems(("All", "R", "G", "B"))
        if self.channel.findText(current) >= 0:
            self.channel.setCurrentText(current)
        self.channel.blockSignals(False)
        self._update_metric_scope()

    def _validate(self) -> str | None:
        pair = self.selected_documents()
        reason = (
            "Select two different loaded images."
            if pair is None
            else validate_difference_documents(pair[0], pair[1], normalized_domain=False)
        )
        if reason is None and pair is not None and self.region.currentText() == "Active ROI":
            if self._active_roi is None:
                reason = "Active ROI is not available."
            elif self._metric_bounds(pair[0], self._active_roi) is None:
                reason = f"Active ROI contains no {self.channel.currentText()} samples."
        self.calculate.setEnabled(reason is None)
        self.calculate.setToolTip(reason or "Calculate or reuse the full absolute map")
        self.status.setText(
            reason or ("Cached map available" if self.has_cached_map() else "Ready")
        )
        self._update_metric_scope()
        return reason

    def _update_metric_scope(self) -> None:
        pair = self.selected_documents()
        if pair is None:
            self.metric_scope.setText("Metrics scope: —")
            return
        channel = self.channel.currentText()
        if pair[0].channel_layout == "BAYER":
            samples = (
                "all raw mosaic samples" if channel == "Mosaic" else f"the {channel} CFA plane"
            )
        else:
            samples = (
                "all R, G, and B samples combined" if channel == "All" else f"the {channel} channel"
            )
        region = "Active ROI" if self.region.currentText() == "Active ROI" else "Full image"
        self.metric_scope.setText(f"Metrics scope: {region}, {samples}.")

    @staticmethod
    def _full_sources(
        a: ImageDocument, b: ImageDocument
    ) -> tuple[NDArray[np.generic], NDArray[np.generic]]:
        assert a.source is not None and b.source is not None
        if a.channel_layout == "BAYER":
            return a.source, b.source
        return a.source[..., :3], b.source[..., :3]

    def _cache_key(self) -> DifferenceCacheKey | None:
        pair = self.selected_documents()
        if pair is None:
            return None
        first = (pair[0].document_id, pair[0].generation)
        second = (pair[1].document_id, pair[1].generation)
        return (first, second) if first <= second else (second, first)

    def _metric_key(self) -> tuple[object, ...] | None:
        key = self._cache_key()
        pair = self.selected_documents()
        if key is None or pair is None:
            return None
        bounds = self._metric_bounds(
            pair[0], self._active_roi if self.region.currentText() == "Active ROI" else None
        )
        region: object = "full" if self.region.currentText() == "Full image" else bounds
        return (*key, self.channel.currentText(), region)

    def _restore_or_refresh_metrics(self, presented_status: str | None = None) -> None:
        if self._validate() is not None:
            return
        difference_map = self.cached_result_for_current()
        metric_key = self._metric_key()
        if difference_map is None or metric_key is None:
            return
        metrics = self._metric_cache.get(metric_key)
        if metrics is not None:
            already_presented = self.last_result is metrics
            self.last_result = metrics
            self._render_metrics(metrics)
            if already_presented and presented_status is not None:
                self.status.setText(presented_status)
            else:
                self.status.setText("Cached metrics restored")
            return
        self.calculate_difference(publish_result=False)

    def has_cached_map(self) -> bool:
        key = self._cache_key()
        return key is not None and key in self._map_cache

    def cached_result_for_current(self) -> CachedDifferenceMap | None:
        key = self._cache_key()
        return self._map_cache.get(key) if key is not None else None

    def cached_display_for_current(
        self,
    ) -> tuple[str, NDArray[np.generic], NDArray[np.uint8]] | None:
        difference_map = self.cached_result_for_current()
        if difference_map is None:
            return None
        selected = self._selected_absolute(difference_map, self.channel.currentText())
        return self._title(), selected, self._cached_preview(difference_map, selected)

    def _cached_preview(
        self,
        difference_map: CachedDifferenceMap,
        selected: NDArray[np.generic],
    ) -> NDArray[np.uint8]:
        key = (
            self._cache_key(),
            self.channel.currentText(),
            self.mode.currentText(),
            self.gain.value(),
            self.threshold.value(),
        )
        if key != self._preview_key or self._preview_value is None:
            self._preview_key = key
            self._preview_value = self._preview(selected)
        return self._preview_value

    @staticmethod
    def _selected_absolute(
        difference_map: CachedDifferenceMap, channel: str
    ) -> NDArray[np.generic]:
        absolute = difference_map.absolute
        if difference_map.channel_layout == "BAYER":
            if channel == "Mosaic":
                return absolute
            assert difference_map.bayer_pattern is not None
            return dict(split_bayer_channels(absolute, difference_map.bayer_pattern))[channel]
        if channel == "All":
            return absolute
        return absolute[..., {"R": 0, "G": 1, "B": 2}[channel]]

    def _metric_bounds(
        self, document: ImageDocument, bounds: RoiBounds | None
    ) -> tuple[int, int, int, int] | None:
        if bounds is None or self.region.currentText() == "Full image":
            return None
        channel = self.channel.currentText()
        if document.channel_layout != "BAYER" or channel == "Mosaic":
            return (bounds.x, bounds.y, bounds.width, bounds.height)
        profile = document.raw_profile
        source = document.source
        assert profile is not None and source is not None
        pattern = str(profile.bayer_pattern)
        row_parity, column_parity = bayer_channel_positions(pattern)[channel]
        selected = dict(split_bayer_channels(source, pattern, bounds)).get(channel)
        if selected is None or selected.size == 0:
            return None
        plane_x = max(0, (bounds.x - column_parity + 1) // 2)
        plane_y = max(0, (bounds.y - row_parity + 1) // 2)
        return (plane_x, plane_y, selected.shape[1], selected.shape[0])

    def calculate_difference(self, _checked: bool = False, *, publish_result: bool = True) -> None:
        if self._validate() is not None:
            return
        pair = self.selected_documents()
        key = self._cache_key()
        metric_key = self._metric_key()
        assert pair is not None and key is not None and metric_key is not None
        request_key = (key, metric_key)
        if self._worker is not None and self._worker_key == request_key:
            return
        a, b = sorted(pair, key=lambda document: (document.document_id, document.generation))
        source_a, source_b = self._full_sources(a, b)
        cached = self._map_cache.get(key)
        channel = self.channel.currentText()
        data_range = float((1 << a.bit_depth) - 1)
        metric_bounds = self._metric_bounds(
            a, self._active_roi if self.region.currentText() == "Active ROI" else None
        )
        if a.channel_layout == "BAYER":
            assert a.raw_profile is not None
            pattern = str(a.raw_profile.bayer_pattern)
        else:
            pattern = None

        def calculate() -> tuple[CachedDifferenceMap, DifferenceMetrics, bool]:
            difference_map = cached
            reused = difference_map is not None
            if difference_map is None:
                difference_map = CachedDifferenceMap(
                    compact_absolute_difference(source_a, source_b),
                    data_range,
                    a.channel_layout,
                    pattern,
                )
            selected = self._selected_absolute(difference_map, channel)
            metrics = absolute_difference_metrics(selected, data_range, metric_bounds)
            return difference_map, metrics, reused

        self._cancel_worker()
        self.status.setText("Updating metrics…" if cached is not None else "Calculating map…")
        worker = TaskWorker(calculate)
        worker.signals.succeeded.connect(
            lambda _task_id, _document_id, _generation, result: self._on_result(
                key, metric_key, result, publish_result
            )
        )
        worker.signals.failed.connect(self._on_error)
        worker.signals.finished.connect(self._on_finished)
        self._worker = worker
        self._worker_key = request_key
        QThreadPool.globalInstance().start(worker)

    def _on_result(
        self,
        key: DifferenceCacheKey,
        metric_key: tuple[object, ...],
        payload: object,
        publish_result: bool,
    ) -> None:
        if (
            not isinstance(payload, tuple)
            or len(payload) != 3
            or not isinstance(payload[0], CachedDifferenceMap)
            or not isinstance(payload[1], DifferenceMetrics)
        ):
            return
        difference_map, metrics, reused = payload
        put_result = self._map_cache.put(key, difference_map)
        self._drop_dependent_cache_entries(put_result.evicted_keys)
        if put_result.stored:
            self._metric_cache[metric_key] = metrics
        if key != self._cache_key() or metric_key != self._metric_key():
            return
        self.last_result = metrics
        self._render_metrics(metrics)
        if reused:
            self.status.setText("Cached map reused")
        elif put_result.stored:
            self.status.setText("Ready")
        else:
            self.status.setText("Ready; map exceeds cache budget")
        if publish_result:
            selected = self._selected_absolute(difference_map, self.channel.currentText())
            self.result_ready.emit(
                self._title(), selected, self._cached_preview(difference_map, selected)
            )

    def _drop_dependent_cache_entries(
        self,
        evicted_keys: tuple[DifferenceCacheKey, ...],
    ) -> None:
        if not evicted_keys:
            return
        evicted = set(evicted_keys)
        self._metric_cache = {
            metric_key: value
            for metric_key, value in self._metric_cache.items()
            if len(metric_key) < 2 or (metric_key[0], metric_key[1]) not in evicted
        }
        if self._preview_key is not None and self._preview_key and self._preview_key[0] in evicted:
            self._preview_key = None
            self._preview_value = None

    def _render_metrics(self, metrics: DifferenceMetrics) -> None:
        values = (
            metrics.mae,
            metrics.mse,
            metrics.rmse,
            metrics.psnr,
            metrics.p95,
            metrics.p99,
            metrics.maximum_absolute,
            metrics.nonzero_ratio,
        )
        for row, value in enumerate(values):
            text = "∞" if isinf(value) else f"{value:.8g}"
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.metrics.setItem(row, 1, item)

    def _title(self) -> str:
        pair = self.selected_documents()
        if pair is None:
            return "Difference"
        return (
            f"{self.mode.currentText()} [{self.channel.currentText()}]: "
            f"{pair[0].display_name} vs {pair[1].display_name}"
        )

    def _preview(self, absolute: NDArray[np.generic]) -> NDArray[np.uint8]:
        if self.mode.currentText() == "Mask":
            return render_threshold_mask(absolute, self.threshold.value())
        return render_absolute_difference(absolute, float(self.gain.value()))

    def _update_control_states(self) -> None:
        absolute = self.mode.currentText() == "Absolute"
        self.threshold.setEnabled(not absolute)
        self.gain.setEnabled(absolute)

    def _cancel_worker(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self._worker = None
        self._worker_key = None

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
            self._worker_key = None

    def shutdown(self) -> None:
        self._display_timer.stop()
        self._cancel_worker()
