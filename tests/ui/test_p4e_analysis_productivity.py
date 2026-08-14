from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QApplication,
    QTableWidgetItem,
    QToolButton,
    QWidget,
)

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument


def _window(qtbot: object) -> MainWindow:
    QSettings().clear()
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    return window


def _seed_statistics_table(window: MainWindow) -> None:
    panel = window.comparison_analysis_panel
    panel.image_summary.setRowCount(1)
    for column, value in enumerate(("1", "sample.raw", "10-bit", "16")):
        panel.image_summary.setItem(0, column, QTableWidgetItem(value))
    panel.table.setRowCount(1)
    values = ("1", "Gray", "0", "15", "7.5", "2", "1", "8", "14")
    for column, value in enumerate(values):
        panel.table.setItem(0, column, QTableWidgetItem(value))


def _seed_difference(window: MainWindow, tmp_path: Path) -> None:
    first = ImageDocument.from_array(
        np.zeros((4, 4), dtype=np.uint8),
        "first.png",
        source_path=tmp_path / "first.png",
    )
    second = ImageDocument.from_array(
        np.full((4, 4), 20, dtype=np.uint8),
        "second.png",
        source_path=tmp_path / "second.png",
    )
    for document in (first, second):
        window.add_document(document, select=False)
    window._select_document_ids([first.document_id, second.document_id])


def _calculate_difference(qtbot: object, window: MainWindow) -> None:
    window.difference_panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.difference_panel.last_result is not None
        and window.difference_panel._worker is None
        and window.difference_panel._preview_worker is None,
        timeout=5000,
    )
    window.analysis_export_controller.refresh_actions()


def _csv_rows(path: Path) -> list[list[str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        return list(csv.reader(stream))


def test_analysis_tables_use_clean_headings_and_unified_command_buttons(
    qtbot: object,
) -> None:
    window = _window(qtbot)
    controller = window.analysis_export_controller
    statistics = window.comparison_analysis_panel
    difference = window.difference_panel

    assert statistics.region_group.title() == "Region"
    assert statistics.image_summary_group.title() == "Images"
    assert "font-weight: bold" in statistics.region_group.styleSheet()
    assert "font-weight: bold" in statistics.image_summary_group.styleSheet()

    assert statistics.statistics_group.title() == ""
    assert controller.statistics_heading_label.text() == "Channel statistics"
    assert controller.statistics_heading_label.font().bold()
    statistics_header_layout = controller.statistics_header.layout()
    assert statistics_header_layout is not None
    assert statistics_header_layout.indexOf(controller.statistics_heading_label) == 0
    assert statistics_header_layout.indexOf(controller.statistics_copy_button) == 1
    assert controller.statistics_copy_button.toolTip() == "Copy Channel statistics as CSV"

    assert controller.difference_metrics_label.text() == "Difference metrics"
    assert controller.difference_metrics_label.font().bold()
    assert difference.metric_scope.isHidden()
    assert difference.domain_status.isHidden()
    assert controller.difference_metrics_copy_button.toolTip() == "Copy Difference metrics as CSV"
    assert controller.difference_metrics_export_button.text() == "CSV"

    analysis_buttons = (
        controller.statistics_copy_button,
        difference.calculate,
        controller.difference_metrics_export_button,
        controller.difference_metrics_copy_button,
    )
    assert len({button.styleSheet() for button in analysis_buttons}) == 1
    command_style = analysis_buttons[0].styleSheet()
    assert "background: transparent" in command_style
    assert "border: 1px solid transparent" in command_style
    assert "hover:enabled" in command_style
    assert "pressed:enabled" in command_style
    assert ":disabled" in command_style
    assert "padding-top:" in command_style
    assert len({button.height() for button in analysis_buttons}) == 1
    assert all(not button.isEnabled() for button in analysis_buttons)
    for button in analysis_buttons:
        if isinstance(button, QToolButton):
            assert not button.autoRaise()

    assert controller.statistics_copy_button.iconSize().width() == 18
    assert controller.statistics_copy_button.iconSize().height() == 18
    assert controller.difference_metrics_copy_button.iconSize().width() == 18
    assert controller.difference_metrics_copy_button.iconSize().height() == 18

    _compose_main_window_presentation(window)
    headers = statistics.statistics_group.findChildren(QWidget, "channelStatisticsHeader")
    assert len(headers) == 1

    _seed_statistics_table(window)
    controller.refresh_actions()
    assert controller.statistics_copy_button.isEnabled()
    controller.statistics_copy_button.click()

    assert QApplication.clipboard().text() == (
        "Id,Ch,Min,Max,Mean,Std,P1,P50,P99\n"
        "1,Gray,0,15,7.5,2,1,8,14\n"
    )


def test_default_export_path_is_timestamped_and_custom_name_is_respected(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    window = _window(qtbot)
    controller = window.analysis_export_controller
    monkeypatch.setattr(  # type: ignore[attr-defined]
        "pixelscope.ui.analysis_export._export_timestamp",
        lambda: "20260814-221500-123",
    )
    monkeypatch.setattr(  # type: ignore[attr-defined]
        window,
        "_export_dialog_directory",
        lambda: str(tmp_path),
    )
    observed: list[str] = []

    def capture_default(
        _parent: object,
        _title: str,
        initial: str,
        _filter: str,
    ) -> tuple[str, str]:
        observed.append(initial)
        return "", "CSV (*.csv)"

    monkeypatch.setattr(  # type: ignore[attr-defined]
        "pixelscope.ui.analysis_export.QFileDialog.getSaveFileName",
        capture_default,
    )
    filename = controller._timestamped_filename("pixelscope_histogram", ".csv")
    assert controller._choose_path(
        "Export Histogram",
        filename,
        "CSV (*.csv)",
        ".csv",
    ) is None
    assert observed == [
        str(tmp_path / "pixelscope_histogram_20260814-221500-123.csv")
    ]

    custom = tmp_path / "review.csv"
    monkeypatch.setattr(  # type: ignore[attr-defined]
        "pixelscope.ui.analysis_export.QFileDialog.getSaveFileName",
        lambda *_args, **_kwargs: (str(custom), "CSV (*.csv)"),
    )
    assert controller._choose_path(
        "Export Histogram",
        filename,
        "CSV (*.csv)",
        ".csv",
    ) == custom


def test_difference_postfix_and_metrics_export_preserve_current_context(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    window = _window(qtbot)
    controller = window.analysis_export_controller
    monkeypatch.setattr(  # type: ignore[attr-defined]
        "pixelscope.ui.analysis_export._export_timestamp",
        lambda: "20260814-221500-123",
    )
    _seed_difference(window, tmp_path)
    _calculate_difference(qtbot, window)
    panel = window.difference_panel

    panel.gain.setValue(4)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: not panel._display_timer.isActive() and panel._preview_worker is None,
        timeout=5000,
    )
    assert controller._difference_image_filename() == (
        "pixelscope_difference_gray_absolute_gain-4x_20260814-221500-123.png"
    )

    panel.mode.setCurrentText("Mask")
    panel.threshold.setValue(5)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: not panel._display_timer.isActive() and panel._preview_worker is None,
        timeout=5000,
    )
    assert controller._difference_image_filename() == (
        "pixelscope_difference_gray_mask_thr-5code_20260814-221500-123.png"
    )

    controller.copy_difference_metrics_csv()
    clipboard_rows = list(csv.reader(QApplication.clipboard().text().splitlines()))
    assert clipboard_rows[0] == ["Metric", "Value"]
    assert [row[0] for row in clipboard_rows[1:]] == [
        "MAE",
        "MSE",
        "RMSE",
        "PSNR",
        "P95",
        "P99",
        "Max difference",
        "Non-zero ratio",
    ]

    monkeypatch.setattr(  # type: ignore[attr-defined]
        window,
        "_export_dialog_directory",
        lambda: str(tmp_path),
    )
    observed_initial: list[str] = []

    def accept_default(
        _parent: object,
        _title: str,
        initial: str,
        _filter: str,
    ) -> tuple[str, str]:
        observed_initial.append(initial)
        return initial, "CSV (*.csv)"

    monkeypatch.setattr(  # type: ignore[attr-defined]
        "pixelscope.ui.analysis_export.QFileDialog.getSaveFileName",
        accept_default,
    )
    controller.export_difference_metrics_csv()

    filename = (
        "pixelscope_difference_metrics_gray_full-image_native_"
        "20260814-221500-123.csv"
    )
    assert observed_initial == [str(tmp_path / filename)]
    rows = _csv_rows(tmp_path / filename)
    assert rows[0] == [
        "source_a",
        "source_b",
        "region",
        "channel",
        "domain",
        "bit_depth_a",
        "bit_depth_b",
        "metric",
        "value",
    ]
    assert {row[2] for row in rows[1:]} == {"Full image"}
    assert {row[3] for row in rows[1:]} == {"Gray"}
    assert {row[4] for row in rows[1:]} == {"native"}
    assert {row[5] for row in rows[1:]} == {"8"}
    assert {row[6] for row in rows[1:]} == {"8"}
    assert [row[7] for row in rows[1:]] == [
        "MAE",
        "MSE",
        "RMSE",
        "PSNR",
        "P95",
        "P99",
        "Max difference",
        "Non-zero ratio",
    ]
