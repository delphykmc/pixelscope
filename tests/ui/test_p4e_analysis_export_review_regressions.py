from __future__ import annotations

from pathlib import Path
from threading import Event

import numpy as np
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QTableWidgetItem

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
    for column, value in enumerate(("1", "sample.raw", "8-bit", "16")):
        panel.image_summary.setItem(0, column, QTableWidgetItem(value))
    panel.table.setRowCount(1)
    for column, value in enumerate(("1", "Gray", "0", "15", "7.5", "2", "1", "8", "14")):
        panel.table.setItem(0, column, QTableWidgetItem(value))


def _seed_difference_documents(
    window: MainWindow,
    tmp_path: Path,
    count: int,
) -> tuple[ImageDocument, ...]:
    documents = tuple(
        ImageDocument.from_array(
            np.full((4, 4), index * 10, dtype=np.uint8),
            f"image-{index}.png",
            source_path=tmp_path / f"image-{index}.png",
        )
        for index in range(count)
    )
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    return documents


def _calculate_difference(qtbot: object, window: MainWindow) -> None:
    window.difference_panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_document is not None
        and window._difference_source_ids is not None
        and window.difference_panel._worker is None
        and window.difference_panel._preview_worker is None,
        timeout=5000,
    )
    window.analysis_export_controller.refresh_actions()


def test_difference_export_disarms_when_panel_pair_diverges_from_active_result(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    window = _window(qtbot)
    controller = window.analysis_export_controller
    documents = _seed_difference_documents(window, tmp_path, 4)
    _calculate_difference(qtbot, window)

    active_document = window._difference_document
    active_source_ids = window._difference_source_ids
    assert active_document is not None
    assert active_source_ids is not None
    assert controller.difference_action.isEnabled()

    panel = window.difference_panel
    third_index = panel.a_selector.findData(documents[2].document_id)
    fourth_index = panel.b_selector.findData(documents[3].document_id)
    assert third_index >= 0
    assert fourth_index >= 0
    panel.a_selector.setCurrentIndex(third_index)
    panel.b_selector.setCurrentIndex(fourth_index)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: not controller.difference_action.isEnabled(),
        timeout=2000,
    )

    panel.mode.setCurrentText("Mask")
    panel.threshold.setValue(5)

    def forbidden_dialog(*_args: object, **_kwargs: object) -> tuple[str, str]:
        raise AssertionError("stale active Difference must not reach the export dialog")

    monkeypatch.setattr(  # type: ignore[attr-defined]
        "pixelscope.ui.analysis_export.QFileDialog.getSaveFileName",
        forbidden_dialog,
    )
    controller.export_difference_image()

    assert controller._difference_preview() is None
    assert window._difference_document is active_document
    assert window._difference_source_ids == active_source_ids
    assert "No current Difference image to export" in window.statusBar().currentMessage()


def test_statistics_toolbar_and_file_menu_share_timestamped_export_path(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    window = _window(qtbot)
    controller = window.analysis_export_controller
    _seed_statistics_table(window)
    controller.refresh_actions()
    assert controller.statistics_action.isEnabled()
    assert window.export_toolbar_action.isEnabled()

    monkeypatch.setattr(  # type: ignore[attr-defined]
        "pixelscope.ui.analysis_export._export_timestamp",
        lambda: "20260814-235500-123",
    )
    monkeypatch.setattr(  # type: ignore[attr-defined]
        window,
        "_export_dialog_directory",
        lambda: str(tmp_path),
    )
    observed: list[tuple[str, str]] = []

    def capture(
        _parent: object,
        title: str,
        initial: str,
        _file_filter: str,
    ) -> tuple[str, str]:
        observed.append((title, initial))
        return "", "CSV (*.csv)"

    monkeypatch.setattr(  # type: ignore[attr-defined]
        "pixelscope.ui.analysis_export.QFileDialog.getSaveFileName",
        capture,
    )

    controller.statistics_action.trigger()
    window.export_toolbar_action.trigger()

    expected = str(tmp_path / "pixelscope_statistics_20260814-235500-123.csv")
    assert observed == [
        ("Export Statistics", expected),
        ("Export Statistics", expected),
    ]


def test_running_difference_export_can_close_and_recreate_main_window(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    window = _window(qtbot)
    controller = window.analysis_export_controller
    _seed_difference_documents(window, tmp_path, 2)
    _calculate_difference(qtbot, window)
    assert controller.difference_action.isEnabled()

    target = tmp_path / "slow-difference.png"
    monkeypatch.setattr(  # type: ignore[attr-defined]
        "pixelscope.ui.analysis_export.QFileDialog.getSaveFileName",
        lambda *_args, **_kwargs: (str(target), "PNG (*.png)"),
    )
    started = Event()
    release = Event()

    def delayed_write(path: Path, preview: np.ndarray) -> Path:
        del preview
        started.set()
        release.wait(timeout=5.0)
        return path

    monkeypatch.setattr(  # type: ignore[attr-defined]
        "pixelscope.ui.analysis_export.write_difference_png",
        delayed_write,
    )

    controller.export_difference_image()
    qtbot.waitUntil(started.is_set, timeout=5000)  # type: ignore[attr-defined]
    worker = controller._difference_worker
    assert worker is not None

    try:
        window.close()
        assert controller._shutting_down
        assert worker.is_cancelled

        replacement = _window(qtbot)
        assert not replacement.analysis_export_controller._shutting_down
        replacement.analysis_export_controller.refresh_actions()
    finally:
        release.set()

    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: controller._difference_worker is None,
        timeout=5000,
    )
