"""UX-3A native Qt integration: real CSV export is not portable Save As."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from PySide6.QtWidgets import QFileDialog

from pixelscope_enterprise.iqa.analysis_window import AnalysisWindow
from pixelscope_enterprise.iqa.demo import make_synthetic_result


def test_file_export_enabled_for_result_without_verified_reader(
    qtbot: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    # Use the retained Qt-owned File menu rather than borrowing a temporary
    # QAction.menu() wrapper, whose Python lifetime can differ by PySide6 build.
    file_menu = win.file_menu
    assert win.export_menu.title() == "Export Result"
    assert win.export_menu.objectName() == "enterpriseIqaExportResultMenu"
    assert win.export_menu_action in file_menu.actions()
    assert win.export_menu.actions() == [win.export_action]
    assert win.export_action.text() == "Measurements (CSV)..."
    assert win.export_action.objectName() == "enterpriseIqaExportMeasurementsCsv"
    assert not win.export_menu_action.isEnabled()
    assert not win.export_action.isEnabled()
    assert not win.open_action.isEnabled()
    assert not win.save_action.isEnabled()
    result = make_synthetic_result("ux3a-csv")
    win.present_result(result)
    win.show()
    assert win.export_menu_action.isEnabled()
    assert win.export_action.isEnabled()
    assert not win.open_action.isEnabled()
    assert not win.save_action.isEnabled()
    win._set_roi(64.0, 96.0, 512.0, 512.0)
    assert "Full-pair comparison" in win.official_label.text()
    assert "Grid-derived ROI estimate" in win.roi_label.text()
    assert "FULL-PAIR" in win.top3_title.text() or "SIGNAL PENDING" in win.top3_title.text()
    assert "official" not in win.official_label.text().lower()
    assert "official" not in win.roi_label.text().lower()
    assert "official" not in win.export_action.toolTip().lower()
    assert "official" not in win.spatial_panel.provenance_badge.toolTip().lower()
    before = win.current_roi
    win._swap_sources()  # visual placement must NOT swap exported source identity
    destination = tmp_path / "measurements.csv"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: (str(destination), "CSV files (*.csv)"),
    )
    win.export_action.trigger()
    assert destination.is_file()
    with destination.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) >= len(result.attributes)
    assert all(row["result_id"] == result.result_id for row in rows)
    assert all(row["source_a_label"] == result.source_a_label for row in rows)
    assert all(row["source_b_label"] == result.source_b_label for row in rows)
    assert any(row["measurement_scope"] == "GRID_DERIVED_ROI" for row in rows)
    assert win.current_roi == before
    assert "CSV exported" in win.statusBar().currentMessage()
    win.close()
    win._shutdown_spatial_worker()


def test_csv_dialog_cancel_and_failed_disk_write_are_non_destructive(
    qtbot: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    result = make_synthetic_result("ux3a-cancel")
    win.present_result(result)
    win.show()
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: ("", "CSV files (*.csv)"),
    )
    win.export_action.trigger()
    assert not list(tmp_path.glob("*"))
    assert win.active_result_id == result.result_id

    import pixelscope_enterprise.iqa.analysis_window as window_module

    def reject_save(*_args: object, **_kwargs: object) -> None:
        raise OSError("synthetic I/O failure")

    monkeypatch.setattr(window_module, "write_measurements_csv", reject_save)
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: (str(tmp_path / "will-not-exist"), "CSV files (*.csv)"),
    )
    win.export_action.trigger()
    assert "CSV export failed" in win.statusBar().currentMessage()
    assert win.active_result_id == result.result_id
    assert not list(tmp_path.glob("*"))
    win.close()
    win._shutdown_spatial_worker()
