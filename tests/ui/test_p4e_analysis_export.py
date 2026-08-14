from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
from PySide6.QtCore import QSettings

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineSelection
from pixelscope.core.roi import RoiAnalysisResult, RoiBounds
from pixelscope.core.statistics import HistogramResult, ImageStatistics


def _stats() -> ImageStatistics:
    return ImageStatistics(0.0, 1.0, 0.5, 0.5, {1.0: 0.0, 50.0: 0.5, 99.0: 1.0})


def _window(qtbot: object) -> MainWindow:
    QSettings().clear()
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    return window


def _csv_rows(path: Path) -> list[list[str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        return list(csv.reader(stream))


def _read_png_as_preview(path: Path) -> np.ndarray:
    decoded = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if decoded is None:
        raise AssertionError(f"Failed to decode exported PNG: {path}")
    if decoded.ndim == 3 and decoded.shape[2] == 3:
        return cv2.cvtColor(decoded, cv2.COLOR_BGR2RGB)
    if decoded.ndim == 3 and decoded.shape[2] == 4:
        return cv2.cvtColor(decoded, cv2.COLOR_BGRA2RGBA)
    return decoded


def _seed_histogram(
    window: MainWindow,
    tmp_path: Path,
    channels: tuple[str, ...],
    *,
    scope: str = "Full image",
) -> None:
    panel = window.comparison_analysis_panel
    document = ImageDocument.from_array(
        np.zeros((8, 8), dtype=np.uint8),
        "source.raw",
        source_path=tmp_path / "source.raw",
    )
    counts = tuple(
        np.asarray([index + 1, index + 2], dtype=np.int64)
        for index in range(len(channels))
    )
    histogram = HistogramResult(counts, np.asarray([0.0, 1.0, 2.0]), channels)
    bounds = RoiBounds(1, 2, 3, 4) if scope == "Active ROI" else RoiBounds(0, 0, 8, 8)
    pixel_count = bounds.width * bounds.height
    result = RoiAnalysisResult(
        bounds=bounds,
        pixel_count=pixel_count,
        overall=_stats(),
        channel_statistics=tuple(_stats() for _ in channels),
        channel_names=channels,
        histogram=histogram,
        channel_sample_counts=tuple(pixel_count for _ in channels),
    )
    panel._documents = [document]
    panel.last_results = (result,)
    panel._request_signature = ("ready",)
    panel._completed_signature = panel._request_signature
    panel._histogram_series = [[] for _index in range(6)]
    for channel, channel_counts in zip(channels, counts, strict=True):
        panel._histogram_series[0].append(
            (0, channel, histogram.edges, channel_counts.astype(np.float64))
        )
    panel.region_scope.blockSignals(True)
    panel.set_roi_available(scope == "Active ROI")
    panel.region_scope.setCurrentText(scope)
    panel.region_scope.blockSignals(False)


def _seed_line_profile(window: MainWindow, tmp_path: Path) -> None:
    panel = window.line_profile_panel
    document = ImageDocument.from_array(
        np.zeros((2, 3, 3), dtype=np.uint8),
        "line.png",
        source_path=tmp_path / "line.png",
    )
    panel._documents = [document]
    panel._selection = LineSelection(0, 1, 2, 1)
    panel._worker = None
    panel.last_results = (
        SimpleNamespace(channel_names=("R", "G", "B")),
    )
    panel._profile_series = [[] for _index in range(6)]
    panel._profile_series[0] = [
        (
            0,
            "R",
            np.asarray([0.0, 1.0, 2.0]),
            np.asarray([10.0, 11.0, 12.0]),
        ),
        (
            0,
            "B",
            np.asarray([0.0, 1.0, 2.0]),
            np.asarray([20.0, 21.0, 22.0]),
        ),
    ]


def _export_action_names(window: MainWindow) -> list[str]:
    return [
        action.text()
        for action in window.analysis_export_controller.file_menu.actions()
        if action.text().startswith("Export ")
    ]


def test_file_menu_export_actions_install_once_and_follow_current_data(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window = _window(qtbot)
    controller = window.analysis_export_controller

    _compose_main_window_presentation(window)
    assert _export_action_names(window) == [
        "Export Statistics CSV...",
        "Export Histogram CSV...",
        "Export Line Profile CSV...",
        "Export Difference Image...",
    ]
    assert not controller.histogram_action.isEnabled()
    assert not controller.line_profile_action.isEnabled()
    assert not controller.difference_action.isEnabled()

    _seed_histogram(window, tmp_path, ("Gray",))
    _seed_line_profile(window, tmp_path)
    controller.refresh_actions()
    assert controller.histogram_action.isEnabled()
    assert controller.line_profile_action.isEnabled()
    assert not controller.difference_action.isEnabled()


def test_export_actions_do_not_leak_across_main_window_recreation(qtbot: object) -> None:
    first = _window(qtbot)
    assert _export_action_names(first).count("Export Difference Image...") == 1
    first.close()

    second = _window(qtbot)
    assert _export_action_names(second) == [
        "Export Statistics CSV...",
        "Export Histogram CSV...",
        "Export Line Profile CSV...",
        "Export Difference Image...",
    ]


def test_histogram_export_is_deterministic_for_gray_rgb_bayer_full_and_roi(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    window = _window(qtbot)
    controller = window.analysis_export_controller

    for name, channels, scope, expected_bounds in (
        ("gray-full", ("Gray",), "Full image", ("0", "0", "8", "8")),
        ("gray-roi", ("Gray",), "Active ROI", ("1", "2", "3", "4")),
        ("rgb-roi", ("R", "G", "B"), "Active ROI", ("1", "2", "3", "4")),
        ("bayer-roi", ("R", "Gr", "Gb", "B"), "Active ROI", ("1", "2", "3", "4")),
    ):
        _seed_histogram(window, tmp_path, channels, scope=scope)
        target = tmp_path / f"{name}.csv"
        monkeypatch.setattr(  # type: ignore[attr-defined]
            "pixelscope.ui.analysis_export.QFileDialog.getSaveFileName",
            lambda *_args, path=target, **_kwargs: (str(path), "CSV (*.csv)"),
        )
        before = _workspace_state(window)
        controller.export_histogram_csv()
        assert _workspace_state(window) == before
        rows = _csv_rows(target)
        assert rows[0][0:5] == ["scope", "roi_x", "roi_y", "roi_width", "roi_height"]
        assert {row[0] for row in rows[1:]} == {scope}
        assert {tuple(row[1:5]) for row in rows[1:]} == {expected_bounds}
        assert [row[7] for row in rows[1::2]] == list(channels)
        assert all(row[15].isdigit() for row in rows[1:])


def test_line_profile_export_uses_current_rendered_series_and_sample_order(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    window = _window(qtbot)
    controller = window.analysis_export_controller
    panel = window.line_profile_panel
    panel.y_mode.blockSignals(True)
    panel.y_mode.setCurrentText("Difference from reference")
    panel.y_mode.blockSignals(False)
    _seed_line_profile(window, tmp_path)
    target = tmp_path / "line.csv"
    monkeypatch.setattr(  # type: ignore[attr-defined]
        "pixelscope.ui.analysis_export.QFileDialog.getSaveFileName",
        lambda *_args, **_kwargs: (str(target), "CSV (*.csv)"),
    )

    before = _workspace_state(window)
    controller.export_line_profile_csv()
    assert _workspace_state(window) == before

    rows = _csv_rows(target)
    assert [row[6] for row in rows[1:]] == ["R", "R", "R", "B", "B", "B"]
    assert [row[-3:] for row in rows[1:4]] == [
        ["0", "0", "10"],
        ["1", "1", "11"],
        ["2", "2", "12"],
    ]
    assert {row[8] for row in rows[1:]} == {"Difference from reference"}


def _seed_difference(window: MainWindow, tmp_path: Path) -> tuple[ImageDocument, ImageDocument]:
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
    return first, second


def _wait_for_difference(qtbot: object, window: MainWindow) -> None:
    window.difference_panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_document is not None
        and window.difference_panel._preview_worker is None,
        timeout=5000,
    )


def _workspace_state(window: MainWindow) -> tuple[object, ...]:
    return (
        tuple(document.document_id for document in window.selected_documents),
        window._active_document_id,
        window._focus_document_id,
        window._primary_page_slot,
        window._page_start,
        tuple((key, document.generation) for key, document in window.documents.items()),
        window.difference_panel.difference_cache.used_bytes,
        window.difference_panel.difference_cache.entry_count,
        tuple(window.difference_panel.difference_cache.keys()),
        len(window._workers),
        len(window._preload_workers),
    )


def test_difference_export_requires_explicit_active_result_and_reuses_current_preview(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    window = _window(qtbot)
    controller = window.analysis_export_controller
    _seed_difference(window, tmp_path)
    controller.refresh_actions()
    assert not controller.difference_action.isEnabled()

    _wait_for_difference(qtbot, window)
    controller.refresh_actions()
    assert controller.difference_action.isEnabled()

    def forbidden_recalculation() -> None:
        raise AssertionError("Difference export must not recalculate Difference")

    monkeypatch.setattr(
        window.difference_panel,
        "calculate_difference",
        forbidden_recalculation,
    )

    panel = window.difference_panel
    panel.gain.setValue(4)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: not panel._display_timer.isActive() and panel._preview_worker is None,
        timeout=5000,
    )

    absolute_target = tmp_path / "absolute.png"
    monkeypatch.setattr(  # type: ignore[attr-defined]
        "pixelscope.ui.analysis_export.QFileDialog.getSaveFileName",
        lambda *_args, **_kwargs: (str(absolute_target), "PNG (*.png)"),
    )
    before = _workspace_state(window)
    expected_absolute = window._difference_document.preview.copy()
    controller.export_difference_image()
    qtbot.waitUntil(lambda: absolute_target.exists(), timeout=5000)  # type: ignore[attr-defined]
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: controller._difference_worker is None, timeout=5000
    )
    assert _workspace_state(window) == before
    np.testing.assert_array_equal(_read_png_as_preview(absolute_target), expected_absolute)

    panel.mode.setCurrentText("Mask")
    panel.threshold.setValue(5)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: not panel._display_timer.isActive() and panel._preview_worker is None,
        timeout=5000,
    )
    expected_mask = window._difference_document.preview.copy()
    mask_target = tmp_path / "mask.png"
    monkeypatch.setattr(  # type: ignore[attr-defined]
        "pixelscope.ui.analysis_export.QFileDialog.getSaveFileName",
        lambda *_args, **_kwargs: (str(mask_target), "PNG (*.png)"),
    )
    before = _workspace_state(window)
    controller.export_difference_image()
    qtbot.waitUntil(lambda: mask_target.exists(), timeout=5000)  # type: ignore[attr-defined]
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: controller._difference_worker is None, timeout=5000
    )
    assert _workspace_state(window) == before
    np.testing.assert_array_equal(_read_png_as_preview(mask_target), expected_mask)


def test_cached_difference_without_active_binding_is_not_exportable(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window = _window(qtbot)
    controller = window.analysis_export_controller
    _seed_difference(window, tmp_path)
    _wait_for_difference(qtbot, window)
    assert window.difference_panel.difference_cache.entry_count == 1

    window._difference_document = None
    window._difference_source_ids = None
    controller.refresh_actions()

    assert window.difference_panel.difference_cache.entry_count == 1
    assert not controller.difference_action.isEnabled()


def test_difference_export_cancel_and_write_failure_do_not_mutate_workspace(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    window = _window(qtbot)
    controller = window.analysis_export_controller
    _seed_difference(window, tmp_path)
    _wait_for_difference(qtbot, window)
    before = _workspace_state(window)

    monkeypatch.setattr(  # type: ignore[attr-defined]
        "pixelscope.ui.analysis_export.QFileDialog.getSaveFileName",
        lambda *_args, **_kwargs: ("", "PNG (*.png)"),
    )
    controller.export_difference_image()
    assert _workspace_state(window) == before

    invalid_target = tmp_path / "missing" / "difference.png"
    monkeypatch.setattr(  # type: ignore[attr-defined]
        "pixelscope.ui.analysis_export.QFileDialog.getSaveFileName",
        lambda *_args, **_kwargs: (str(invalid_target), "PNG (*.png)"),
    )
    controller.export_difference_image()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: controller._difference_worker is None, timeout=5000
    )
    assert "Difference export failed:" in window.statusBar().currentMessage()
    assert _workspace_state(window) == before


def test_export_dialog_reuses_configured_export_directory(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    window = _window(qtbot)
    controller = window.analysis_export_controller
    _seed_histogram(window, tmp_path, ("Gray",))
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

    def capture(_parent: object, _title: str, initial: str, _filter: str) -> tuple[str, str]:
        observed.append(initial)
        return "", "CSV (*.csv)"

    monkeypatch.setattr(  # type: ignore[attr-defined]
        "pixelscope.ui.analysis_export.QFileDialog.getSaveFileName",
        capture,
    )
    before = _workspace_state(window)
    controller.export_histogram_csv()

    assert observed == [
        str(tmp_path / "pixelscope_histogram_20260814-221500-123.csv")
    ]
    assert _workspace_state(window) == before
