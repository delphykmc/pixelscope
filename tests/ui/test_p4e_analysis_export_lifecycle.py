from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QTableWidgetItem

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow


def test_analysis_export_close_disarms_late_table_refresh(qtbot: object) -> None:
    QSettings().clear()
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    controller = window.analysis_export_controller
    statistics = window.comparison_analysis_panel.table
    metrics = window.difference_panel.metrics

    window.close()

    assert controller._shutting_down
    statistics.setRowCount(1)
    statistics.setItem(0, 0, QTableWidgetItem("1"))
    metrics.setItem(0, 1, QTableWidgetItem("0"))
    controller.refresh_actions()

    window.deleteLater()
    qtbot.wait(1)  # type: ignore[attr-defined]
