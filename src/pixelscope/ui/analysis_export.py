from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from PySide6.QtCore import QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFileDialog, QMenu

from pixelscope.io.analysis_export import (
    HistogramExportSeries,
    LineProfileExportSeries,
    write_difference_png,
    write_histogram_csv,
    write_line_profile_csv,
)
from pixelscope.workers.task_worker import TaskError, TaskWorker
from pixelscope.workers.thread_pools import analysis_thread_pool


class AnalysisExportController(QObject):
    """File-menu adapter for focused exports of already-computed analysis results."""

    def __init__(self, window: Any) -> None:
        super().__init__(window)
        self.window = window
        self._difference_worker: TaskWorker | None = None
        self._pool = analysis_thread_pool()

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

    def refresh_actions(self) -> None:
        self.histogram_action.setEnabled(self._histogram_ready())
        self.line_profile_action.setEnabled(self._line_profile_ready())
        self.difference_action.setEnabled(
            self._difference_worker is None and self._difference_preview() is not None
        )

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
            return document.display_name
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

    def export_histogram_csv(self) -> None:
        series = self._histogram_snapshot()
        if not series:
            self.window.statusBar().showMessage("No current Histogram data to export", 3000)
            self.refresh_actions()
            return
        target = self._choose_path(
            "Export Histogram",
            "pixelscope_histogram.csv",
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
            "pixelscope_line_profile.csv",
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

    def export_difference_image(self) -> None:
        preview = self._difference_preview()
        if preview is None or self._difference_worker is not None:
            self.window.statusBar().showMessage("No current Difference image to export", 3000)
            self.refresh_actions()
            return
        target = self._choose_path(
            "Export Difference Image",
            "pixelscope_difference.png",
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
        if not isinstance(result, Path):
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
        self.window.statusBar().showMessage(f"Difference export failed: {error.message}", 5000)

    def _difference_finished(self, task_id: str) -> None:
        if self._difference_worker is not None and self._difference_worker.task_id == task_id:
            self._difference_worker = None
        self.refresh_actions()


def install_analysis_export(window: Any) -> AnalysisExportController:
    existing = getattr(window, "analysis_export_controller", None)
    if isinstance(existing, AnalysisExportController):
        return existing
    controller = AnalysisExportController(window)
    window.analysis_export_controller = controller
    return controller
