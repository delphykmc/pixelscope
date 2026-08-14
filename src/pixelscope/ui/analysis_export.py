from __future__ import annotations

import csv
import re
from contextlib import suppress
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QAction, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QTableWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pixelscope.io.analysis_export import (
    DifferenceMetricsExport,
    HistogramExportSeries,
    LineProfileExportSeries,
    write_difference_metrics_csv,
    write_difference_png,
    write_histogram_csv,
    write_line_profile_csv,
)
from pixelscope.workers.task_worker import TaskError, TaskWorker
from pixelscope.workers.thread_pools import analysis_thread_pool


def _export_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]


def _filename_token(value: str) -> str:
    token = re.sub(r"[^a-z0-9]+", "-", value.strip().casefold()).strip("-")
    return token or "value"


def _filename_number(value: float) -> str:
    return f"{value:g}".replace("-", "m").replace(".", "p")


def _table_csv_text(table: QTableWidget) -> str:
    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(
        [
            table.horizontalHeaderItem(column).text()
            if table.horizontalHeaderItem(column) is not None
            else ""
            for column in range(table.columnCount())
        ]
    )
    for row in range(table.rowCount()):
        writer.writerow(
            [
                table.item(row, column).text() if table.item(row, column) is not None else ""
                for column in range(table.columnCount())
            ]
        )
    return buffer.getvalue()


def _copy_icon(widget: QWidget) -> QIcon:
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    pen = QPen(widget.palette().buttonText().color())
    pen.setWidth(1)
    painter.setPen(pen)
    painter.drawRect(5, 2, 8, 9)
    painter.drawRect(2, 5, 8, 9)
    painter.end()
    return QIcon(pixmap)


def _copy_button(parent: QWidget, tooltip: str) -> QToolButton:
    button = QToolButton(parent)
    button.setAutoRaise(True)
    button.setIcon(_copy_icon(button))
    button.setToolTip(tooltip)
    button.setAccessibleName(tooltip)
    button.setFixedSize(24, 24)
    return button


def _csv_export_button(parent: QWidget, tooltip: str) -> QToolButton:
    button = QToolButton(parent)
    button.setAutoRaise(True)
    button.setText("CSV")
    button.setToolTip(tooltip)
    button.setAccessibleName(tooltip)
    return button


class AnalysisExportController(QObject):
    """Focused export and clipboard adapter for already-computed analysis results."""

    def __init__(self, window: Any) -> None:
        super().__init__(window)
        self.window = window
        self._difference_worker: TaskWorker | None = None
        self._pool = analysis_thread_pool()
        self._shutting_down = False
        self._observed_models: tuple[QObject, ...] = ()

        self.histogram_action = QAction("Export Histogram CSV...", window)
        self.line_profile_action = QAction("Export Line Profile CSV...", window)
        self.difference_action = QAction("Export Difference Image...", window)
        self.histogram_action.triggered.connect(  # type: ignore[attr-defined]
            self.export_histogram_csv
        )
        self.line_profile_action.triggered.connect(  # type: ignore[attr-defined]
            self.export_line_profile_csv
        )
        self.difference_action.triggered.connect(  # type: ignore[attr-defined]
            self.export_difference_image
        )
        self.file_menu = self._file_menu()
        self._install_actions()
        self._install_table_productivity()
        self.window.installEventFilter(self)
        self.window.destroyed.connect(self._on_window_destroyed)  # type: ignore[attr-defined]
        self.file_menu.aboutToShow.connect(self.refresh_actions)  # type: ignore[attr-defined]
        self.refresh_actions()

    def _file_menu(self) -> QMenu:
        session = getattr(self.window, "session_controller", None)
        menu = getattr(session, "_file_menu_ref", None)
        if not isinstance(menu, QMenu):
            raise RuntimeError("Analysis export requires the composed File menu")
        return menu

    def _install_actions(self) -> None:
        actions = self.file_menu.actions()
        statistics_action = self.window.action_map.get("Export Statistics CSV...")
        if not isinstance(statistics_action, QAction) or statistics_action not in actions:
            raise RuntimeError("Analysis export requires Export Statistics CSV")
        self.statistics_action = statistics_action
        with suppress(RuntimeError, TypeError):
            self.statistics_action.triggered.disconnect()  # type: ignore[attr-defined]
        self.statistics_action.triggered.connect(  # type: ignore[attr-defined]
            self.export_statistics_csv
        )
        statistics_index = actions.index(statistics_action)
        before = actions[statistics_index + 1] if statistics_index + 1 < len(actions) else None
        for action in (
            self.histogram_action,
            self.line_profile_action,
            self.difference_action,
        ):
            if before is None:
                self.file_menu.addAction(action)
            else:
                self.file_menu.insertAction(before, action)
            self.window.action_map[action.text()] = action

    def _install_table_productivity(self) -> None:
        statistics = self.window.comparison_analysis_panel
        for group, title in (
            (statistics.region_group, "Region"),
            (statistics.image_summary_group, "Images"),
            (statistics.statistics_group, "Channel statistics"),
        ):
            if isinstance(group, QGroupBox):
                group.setTitle(title)
                group.setStyleSheet("QGroupBox::title { font-weight: 600; }")

        self.statistics_copy_button = _copy_button(
            statistics.statistics_group,
            "Copy Channel statistics as CSV",
        )
        statistics_layout = statistics.statistics_group.layout()
        if isinstance(statistics_layout, QVBoxLayout):
            copy_row = QHBoxLayout()
            copy_row.setContentsMargins(0, 0, 0, 0)
            copy_row.addStretch(1)
            copy_row.addWidget(self.statistics_copy_button)
            statistics_layout.insertLayout(0, copy_row)
        self.statistics_copy_button.clicked.connect(  # type: ignore[attr-defined]
            self.copy_statistics_csv
        )

        difference = self.window.difference_panel
        difference.metric_scope.hide()
        difference.domain_status.hide()
        self.difference_metrics_label = QLabel("Difference metrics", difference)
        self.difference_metrics_label.setStyleSheet("font-weight: 600;")
        self.difference_metrics_export_button = _csv_export_button(
            difference,
            "Export Difference metrics CSV",
        )
        self.difference_metrics_copy_button = _copy_button(
            difference,
            "Copy Difference metrics as CSV",
        )
        difference_layout = difference.layout()
        if isinstance(difference_layout, QVBoxLayout):
            metric_header = QHBoxLayout()
            metric_header.setContentsMargins(0, 0, 0, 0)
            metric_header.addWidget(self.difference_metrics_label)
            metric_header.addStretch(1)
            metric_header.addWidget(self.difference_metrics_export_button)
            metric_header.addWidget(self.difference_metrics_copy_button)
            metric_index = difference_layout.indexOf(difference.metrics)
            difference_layout.insertLayout(max(0, metric_index), metric_header)
        self.difference_metrics_export_button.clicked.connect(  # type: ignore[attr-defined]
            self.export_difference_metrics_csv
        )
        self.difference_metrics_copy_button.clicked.connect(  # type: ignore[attr-defined]
            self.copy_difference_metrics_csv
        )

        self._observed_models = (
            statistics.table.model(),
            difference.metrics.model(),
        )
        for model in self._observed_models:
            model.dataChanged.connect(self._refresh_from_model)  # type: ignore[attr-defined]
            model.rowsInserted.connect(self._refresh_from_model)  # type: ignore[attr-defined]
            model.rowsRemoved.connect(self._refresh_from_model)  # type: ignore[attr-defined]
            model.modelReset.connect(self._refresh_from_model)  # type: ignore[attr-defined]

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched is self.window and event.type() == QEvent.Type.Close:
            self.shutdown()
        return super().eventFilter(watched, event)

    def _on_window_destroyed(self, _object: object = None) -> None:
        self.shutdown()

    def _refresh_from_model(self, *_args: object) -> None:
        self.refresh_actions()

    def shutdown(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        with suppress(RuntimeError, TypeError):
            self.file_menu.aboutToShow.disconnect(self.refresh_actions)  # type: ignore[attr-defined]
        for model in self._observed_models:
            with suppress(RuntimeError, TypeError):
                model.dataChanged.disconnect(self._refresh_from_model)  # type: ignore[attr-defined]
            with suppress(RuntimeError, TypeError):
                model.rowsInserted.disconnect(self._refresh_from_model)  # type: ignore[attr-defined]
            with suppress(RuntimeError, TypeError):
                model.rowsRemoved.disconnect(self._refresh_from_model)  # type: ignore[attr-defined]
            with suppress(RuntimeError, TypeError):
                model.modelReset.disconnect(self._refresh_from_model)  # type: ignore[attr-defined]
        with suppress(RuntimeError):
            self.window.removeEventFilter(self)
        if self._difference_worker is not None:
            self._difference_worker.cancel()

    def refresh_actions(self) -> None:
        if self._shutting_down or bool(getattr(self.window, "_closing", False)):
            return
        statistics_ready = self._statistics_ready()
        difference_metrics_ready = self._difference_metrics_snapshot() is not None
        self.statistics_action.setEnabled(statistics_ready)
        self.histogram_action.setEnabled(self._histogram_ready())
        self.line_profile_action.setEnabled(self._line_profile_ready())
        self.difference_action.setEnabled(
            self._difference_worker is None and self._difference_preview() is not None
        )
        self.statistics_copy_button.setEnabled(statistics_ready)
        self.difference_metrics_export_button.setEnabled(difference_metrics_ready)
        self.difference_metrics_copy_button.setEnabled(difference_metrics_ready)
        self._sync_difference_metric_context()

    def _statistics_ready(self) -> bool:
        panel = self.window.comparison_analysis_panel
        return bool(panel.table.rowCount() and panel.image_summary.rowCount())

    def _sync_difference_metric_context(self) -> None:
        panel = self.window.difference_panel
        compatibility = panel._compatibility()
        if (
            compatibility is None
            or not compatibility.compatible
            or compatibility.domain != "normalized"
        ):
            panel.domain_status.hide()
            return
        panel.domain_status.setText(
            "Normalized metric domain [0–1] · "
            f"{compatibility.effective_bit_depth_a}-bit vs "
            f"{compatibility.effective_bit_depth_b}-bit"
        )
        panel.domain_status.show()

    def _histogram_ready(self) -> bool:
        panel = self.window.comparison_analysis_panel
        return bool(
            panel.last_results
            and panel._worker is None
            and not panel._refresh_timer.isActive()
            and panel._completed_signature == panel._request_signature
            and len(panel.last_results) == len(panel._documents)
            and any(panel._histogram_series)
        )

    def _line_profile_ready(self) -> bool:
        panel = self.window.line_profile_panel
        return bool(
            panel._selection is not None
            and panel._worker is None
            and panel.last_results
            and len(panel.last_results) == len(panel._documents)
            and any(panel._profile_series)
        )

    def _difference_preview(self) -> NDArray[np.uint8] | None:
        document = getattr(self.window, "_difference_document", None)
        source_ids = getattr(self.window, "_difference_source_ids", None)
        if document is None or source_ids is None:
            return None
        preview = getattr(document, "preview", None)
        if not isinstance(preview, np.ndarray) or preview.dtype != np.uint8:
            return None
        panel = self.window.difference_panel
        if panel._display_timer.isActive() or panel._preview_worker is not None:
            return None
        return preview

    @staticmethod
    def _source_identity(document: Any) -> str:
        if document.source_path is None:
            return str(document.display_name)
        return str(document.source_path.resolve(strict=False))

    @staticmethod
    def _series_identity(index: int, document: Any) -> str:
        return f"{index + 1} · {document.display_name}"

    def _histogram_snapshot(self) -> tuple[HistogramExportSeries, ...]:
        if not self._histogram_ready():
            return ()
        panel = self.window.comparison_analysis_panel
        rendered: dict[
            tuple[int, str],
            tuple[NDArray[np.float64], NDArray[np.float64]],
        ] = {}
        for plot_series in panel._histogram_series:
            for image_index, channel, display_edges, display_values in plot_series:
                rendered[(image_index, channel)] = (display_edges, display_values)

        exported: list[HistogramExportSeries] = []
        scope = panel.region_scope.currentText()
        x_mode = panel.histogram_range.currentText()
        y_mode = panel.histogram_units.currentText()
        for image_index, (document, result) in enumerate(
            zip(panel._documents, panel.last_results, strict=True)
        ):
            bounds = result.bounds
            for channel_index, channel in enumerate(result.histogram.channel_names):
                current = rendered.get((image_index, channel))
                if current is None:
                    continue
                display_edges, display_values = current
                exported.append(
                    HistogramExportSeries(
                        scope=scope,
                        bounds=(bounds.x, bounds.y, bounds.width, bounds.height),
                        source=self._source_identity(document),
                        series=self._series_identity(image_index, document),
                        channel=channel,
                        x_mode=x_mode,
                        y_mode=y_mode,
                        native_edges=result.histogram.edges,
                        display_edges=np.asarray(display_edges, dtype=np.float64),
                        counts=result.histogram.counts[channel_index],
                        display_values=np.asarray(display_values, dtype=np.float64),
                    )
                )
        return tuple(exported)

    def _line_profile_snapshot(self) -> tuple[LineProfileExportSeries, ...]:
        if not self._line_profile_ready():
            return ()
        panel = self.window.line_profile_panel
        selection = panel._selection
        assert selection is not None and selection.y2 is not None
        rendered: dict[
            tuple[int, str],
            tuple[NDArray[np.float64], NDArray[np.float64]],
        ] = {}
        for plot_series in panel._profile_series:
            for image_index, channel, positions, values in plot_series:
                rendered[(image_index, channel)] = (positions, values)

        exported: list[LineProfileExportSeries] = []
        line = (selection.x1, selection.y1, selection.x2, selection.y2)
        x_mode = panel.x_mode.currentText()
        y_mode = panel.y_mode.currentText()
        for image_index, (document, result) in enumerate(
            zip(panel._documents, panel.last_results, strict=True)
        ):
            for channel in result.channel_names:
                if channel == "A":
                    continue
                current = rendered.get((image_index, channel))
                if current is None:
                    continue
                positions, values = current
                exported.append(
                    LineProfileExportSeries(
                        selection=line,
                        source=self._source_identity(document),
                        series=self._series_identity(image_index, document),
                        channel=channel,
                        x_mode=x_mode,
                        y_mode=y_mode,
                        positions=np.asarray(positions, dtype=np.float64),
                        values=np.asarray(values, dtype=np.float64),
                    )
                )
        return tuple(exported)

    def _difference_metrics_snapshot(self) -> DifferenceMetricsExport | None:
        panel = self.window.difference_panel
        pair = panel.selected_documents()
        metrics = panel.last_result
        compatibility = panel._compatibility()
        if (
            pair is None
            or metrics is None
            or compatibility is None
            or not compatibility.compatible
            or compatibility.domain is None
        ):
            return None
        return DifferenceMetricsExport(
            source_a=self._source_identity(pair[0]),
            source_b=self._source_identity(pair[1]),
            region=panel.region.currentText(),
            channel=panel.channel.currentText(),
            domain=compatibility.domain,
            bit_depth_a=compatibility.effective_bit_depth_a,
            bit_depth_b=compatibility.effective_bit_depth_b,
            values=(
                ("MAE", metrics.mae),
                ("MSE", metrics.mse),
                ("RMSE", metrics.rmse),
                ("PSNR", metrics.psnr),
                ("P95", metrics.p95),
                ("P99", metrics.p99),
                ("Max difference", metrics.maximum_absolute),
                ("Non-zero ratio", metrics.nonzero_ratio),
            ),
        )

    def _initial_path(self, filename: str) -> str:
        directory = self.window._export_dialog_directory()
        return str(Path(directory) / filename) if directory else filename

    def _choose_path(
        self,
        title: str,
        filename: str,
        file_filter: str,
        suffix: str,
    ) -> Path | None:
        path, _ = QFileDialog.getSaveFileName(
            self.window,
            title,
            self._initial_path(filename),
            file_filter,
        )
        if not path:
            return None
        target = Path(path)
        return target if target.suffix.casefold() == suffix else target.with_suffix(suffix)

    def _remember_success(self, target: Path) -> None:
        self.window._remember_directory(target.parent)

    @staticmethod
    def _timestamped_filename(stem: str, suffix: str) -> str:
        return f"{stem}_{_export_timestamp()}{suffix}"

    def _difference_image_filename(self) -> str:
        panel = self.window.difference_panel
        channel = _filename_token(panel.channel.currentText())
        mode = _filename_token(panel.mode.currentText())
        parts = ["pixelscope_difference", channel, mode]
        if panel.mode.currentText() == "Mask":
            unit = "code" if panel._threshold_domain == "native" else "pctfs"
            parts.append(f"thr-{_filename_number(float(panel.threshold.value()))}{unit}")
        else:
            parts.append(f"gain-{int(panel.gain.value())}x")
        parts.append(_export_timestamp())
        return "_".join(parts) + ".png"

    def _difference_metrics_filename(self, result: DifferenceMetricsExport) -> str:
        stem = "_".join(
            (
                "pixelscope_difference_metrics",
                _filename_token(result.channel),
                _filename_token(result.region),
                _filename_token(result.domain),
            )
        )
        return self._timestamped_filename(stem, ".csv")

    def copy_statistics_csv(self) -> None:
        if not self._statistics_ready():
            self.window.statusBar().showMessage("No current statistics to copy", 3000)
            self.refresh_actions()
            return
        table = self.window.comparison_analysis_panel.table
        QApplication.clipboard().setText(_table_csv_text(table))
        self.window.statusBar().showMessage("Copied Channel statistics as CSV", 3000)

    def copy_difference_metrics_csv(self) -> None:
        if self._difference_metrics_snapshot() is None:
            self.window.statusBar().showMessage("No current Difference metrics to copy", 3000)
            self.refresh_actions()
            return
        table = self.window.difference_panel.metrics
        QApplication.clipboard().setText(_table_csv_text(table))
        self.window.statusBar().showMessage("Copied Difference metrics as CSV", 3000)

    def export_statistics_csv(self) -> None:
        if not self._statistics_ready():
            self.window.statusBar().showMessage("No current statistics to export", 3000)
            self.refresh_actions()
            return
        target = self._choose_path(
            "Export Statistics",
            self._timestamped_filename("pixelscope_statistics", ".csv"),
            "CSV (*.csv)",
            ".csv",
        )
        if target is None:
            return
        try:
            self.window.comparison_analysis_panel.export_csv(target)
        except OSError as exc:
            self.window.statusBar().showMessage(f"Statistics export failed: {exc}", 5000)
            return
        self._remember_success(target)
        self.window.statusBar().showMessage(f"Exported Statistics · {target.name}", 4000)

    def export_histogram_csv(self) -> None:
        series = self._histogram_snapshot()
        if not series:
            self.window.statusBar().showMessage("No current Histogram data to export", 3000)
            self.refresh_actions()
            return
        target = self._choose_path(
            "Export Histogram",
            self._timestamped_filename("pixelscope_histogram", ".csv"),
            "CSV (*.csv)",
            ".csv",
        )
        if target is None:
            return
        try:
            write_histogram_csv(target, series)
        except (OSError, ValueError) as exc:
            self.window.statusBar().showMessage(f"Histogram export failed: {exc}", 5000)
            return
        self._remember_success(target)
        self.window.statusBar().showMessage(f"Exported Histogram · {target.name}", 4000)

    def export_line_profile_csv(self) -> None:
        series = self._line_profile_snapshot()
        if not series:
            self.window.statusBar().showMessage("No current Line Profile data to export", 3000)
            self.refresh_actions()
            return
        target = self._choose_path(
            "Export Line Profile",
            self._timestamped_filename("pixelscope_line_profile", ".csv"),
            "CSV (*.csv)",
            ".csv",
        )
        if target is None:
            return
        try:
            write_line_profile_csv(target, series)
        except (OSError, ValueError) as exc:
            self.window.statusBar().showMessage(f"Line Profile export failed: {exc}", 5000)
            return
        self._remember_success(target)
        self.window.statusBar().showMessage(f"Exported Line Profile · {target.name}", 4000)

    def export_difference_metrics_csv(self) -> None:
        result = self._difference_metrics_snapshot()
        if result is None:
            self.window.statusBar().showMessage("No current Difference metrics to export", 3000)
            self.refresh_actions()
            return
        target = self._choose_path(
            "Export Difference Metrics",
            self._difference_metrics_filename(result),
            "CSV (*.csv)",
            ".csv",
        )
        if target is None:
            return
        try:
            write_difference_metrics_csv(target, result)
        except (OSError, ValueError) as exc:
            self.window.statusBar().showMessage(f"Difference metrics export failed: {exc}", 5000)
            return
        self._remember_success(target)
        self.window.statusBar().showMessage(
            f"Exported Difference metrics · {target.name}",
            4000,
        )

    def export_difference_image(self) -> None:
        preview = self._difference_preview()
        if preview is None or self._difference_worker is not None:
            self.window.statusBar().showMessage("No current Difference image to export", 3000)
            self.refresh_actions()
            return
        target = self._choose_path(
            "Export Difference Image",
            self._difference_image_filename(),
            "PNG (*.png)",
            ".png",
        )
        if target is None:
            return
        worker = TaskWorker(write_difference_png, target, preview)
        worker.signals.succeeded.connect(self._difference_succeeded)
        worker.signals.failed.connect(self._difference_failed)
        worker.signals.finished.connect(self._difference_finished)
        self._difference_worker = worker
        self.refresh_actions()
        self.window.statusBar().showMessage("Exporting Difference image...", 0)
        self._pool.start(worker)

    def _difference_succeeded(
        self,
        _task_id: str,
        _document_id: str | None,
        _generation: int,
        result: object,
    ) -> None:
        if self._shutting_down or not isinstance(result, Path):
            return
        self._remember_success(result)
        self.window.statusBar().showMessage(f"Exported Difference · {result.name}", 4000)

    def _difference_failed(
        self,
        _task_id: str,
        _document_id: str | None,
        _generation: int,
        error: TaskError,
    ) -> None:
        if self._shutting_down:
            return
        self.window.statusBar().showMessage(f"Difference export failed: {error.message}", 5000)

    def _difference_finished(self, task_id: str) -> None:
        if self._difference_worker is not None and self._difference_worker.task_id == task_id:
            self._difference_worker = None
        if not self._shutting_down:
            self.refresh_actions()


def install_analysis_export(window: Any) -> AnalysisExportController:
    existing = getattr(window, "analysis_export_controller", None)
    if isinstance(existing, AnalysisExportController):
        return existing
    controller = AnalysisExportController(window)
    window.analysis_export_controller = controller
    return controller
