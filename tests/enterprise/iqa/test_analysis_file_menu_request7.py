"""Request 7: file menu, injected package metadata and view-only unloading."""

from __future__ import annotations

from concurrent.futures import Future
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QFileDialog

from pixelscope_enterprise.iqa.analysis_model import (
    AnalysisResult,
    AttributeDisplay,
    LoadedAnalysis,
    SpatialMap,
)
from pixelscope_enterprise.iqa.analysis_window import (
    AnalysisWindow,
    AnalysisWindowManager,
    ResultFileType,
)
from pixelscope_enterprise.iqa.hover_fields import (
    format_source_rgb_field,
    hover_fixed_pitch_font,
)


def _result(result_id: str) -> AnalysisResult:
    spatial = SpatialMap(
        values=np.array([[1.0, -1.0], [0.0, 0.0]]),
        valid_mask=np.array([[True, True], [True, False]]),
        image_width=128,
        image_height=128,
        block_width=64,
        block_height=64,
    )
    attribute = AttributeDisplay(
        "metric_db", "Example dB", "dB", "power", 1.5, "available", True, 5.0, spatial
    )
    return AnalysisResult(
        result_id,
        128,
        128,
        "Synthetic A",
        "Synthetic B",
        (attribute,),
        source_a=Path("missing-a.png"),
        source_b=Path("missing-b.png"),
    )


def test_close_iqa_result_chooses_next_and_preserves_jobs_and_files(
    qtbot: object,
) -> None:
    calls: list[str] = []
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.install_file_handlers(
        load=lambda _path: (calls.append("read"), LoadedAnalysis(_result("disk")))[1],
        save=lambda _result, _state, _path: calls.append("write"),
    )
    win.show()
    for name in ("first", "second", "third"):
        win.present_result(_result(name))
    assert win.close_result_action.isEnabled()
    assert win.close_result_action.shortcut().toString() == "Ctrl+W"
    assert win.close_result_action.shortcutContext() == Qt.ShortcutContext.WindowShortcut

    win.result_combo.setCurrentIndex(win.result_combo.findData("second"))
    win._set_roi(0, 0, 64, 64)
    win._spatial_cache[("second", "metric_db", 128)] = ()
    win.close_result_action.trigger()
    assert win.active_result_id == "third"  # next result in combo order
    assert list(win._results) == ["first", "third"]
    assert "second" not in win._states
    assert not any(key[0] == "second" for key in win._spatial_cache)
    assert win.result_combo.count() == 2
    assert win.isVisible()

    win.close_result_action.trigger()
    assert win.active_result_id == "first"  # last entry falls back to previous
    win.close_result_action.trigger()
    assert win.active_result_id is None
    assert win.result_combo.count() == 0
    assert not win.close_result_action.isEnabled()
    assert not win.save_action.isEnabled()
    assert not win.export_menu_action.isEnabled()
    assert not win.fit_action.isEnabled()
    assert not win._group_tables
    assert not win._top3_attribute_ids
    assert win.windowTitle() == "IQA Analysis"
    assert all("No result loaded" in view.scene().items()[0].toPlainText() for view in win._views)
    assert calls == []  # Close must never call injected disk I/O.

    # Clearing the final result does not poison later reuse of the same window.
    win.present_result(_result("new"))
    assert win.active_result_id == "new"
    assert win.close_result_action.isEnabled()
    win.close()


def test_close_during_running_spatial_scan_discards_late_completion(
    qtbot: object,
) -> None:
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.present_result(_result("closing"))
    key = win._spatial_key()
    assert key is not None
    win._spatial_cache[key] = ()
    running: Future[tuple[object, ...]] = Future()
    assert running.set_running_or_notify_cancel()
    win._spatial_future = running  # Simulate a worker already executing.
    win._spatial_pending = key
    win._spatial_displayed = key
    win._spatial_timer.start()

    win.close_result_action.trigger()
    assert win.active_result_id is None
    assert win._spatial_future is None
    assert win._spatial_pending is None
    assert win._spatial_displayed is None
    assert not win._spatial_timer.isActive()
    assert key not in win._spatial_cache
    assert "closing" not in win._results
    assert not running.cancelled()  # Already-running work cannot be cancelled.

    win.present_result(_result("replacement"))
    running.set_result(())
    win._finish_spatial_if_ready()
    assert win.active_result_id == "replacement"
    assert "closing" not in win._results
    assert key not in win._spatial_cache
    assert "closing" not in win._states

    # A freshly loaded artifact may legally reuse the closed result ID.
    win.close_result_action.trigger()
    win.present_result(_result("closing"))
    win._finish_spatial_if_ready()
    assert win.active_result_id == "closing"
    assert win._results["closing"].result_id == "closing"
    assert key not in win._spatial_cache
    win.close()


def test_hover_source_fields_reserve_stable_rgb_columns() -> None:
    font = hover_fixed_pitch_font()
    assert font.fixedPitch()

    ref_small = format_source_rgb_field("Reference", (0, 9, 255), bit_depth=8)
    ref_large = format_source_rgb_field("Reference", (255, 255, 255), bit_depth=8)
    assert len(ref_small) == len(ref_large)
    assert ref_small.startswith("Reference RGB8:")
    assert ref_large.startswith("Reference RGB8:")

    missing = format_source_rgb_field("Target", None, bit_depth=None)
    present_16 = format_source_rgb_field("Target", (0, 1, 65535), bit_depth=16)
    assert missing.startswith("Target RGB: unavailable")
    assert len(missing) == len(present_16)
    assert present_16.endswith("65535")
    # The following map column remains at the same position over unavailable
    # and available pixels when the source slot is declared 16-bit.
    assert len(missing + " | Map: value") == len(present_16 + " | Map: value")
    with pytest.raises(ValueError):
        format_source_rgb_field("Reference", (256, 1, 2), bit_depth=8)


def test_integrated_hover_pair_is_fixed_pitch_padded_and_status_independent(
    qtbot: object, tmp_path: Path
) -> None:
    source8 = tmp_path / "source8.png"
    source16 = tmp_path / "source16.png"
    rgb8 = QImage(128, 128, QImage.Format.Format_RGB32)
    rgb8.fill(QColor(17, 33, 65))
    assert rgb8.save(str(source8))
    rgb16 = QImage(128, 128, QImage.Format.Format_RGBA64)
    rgb16.fill(QColor(32, 64, 128))
    assert rgb16.save(str(source16))

    mixed = replace(
        _result("mixed-depth"),
        source_a=source8,
        source_b=source16,
        source_a_role="Reference",
        source_b_role="Target",
    )
    window = AnalysisWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.resize(1600, 800)
    window.present_result(mixed)
    window.show()
    QApplication.processEvents()
    pair = window._hover_readouts
    assert pair.position.font().fixedPitch()
    assert pair.values.font().fixedPitch()
    assert window._hover_bit_depth(window._source_images[0]) == 8
    assert window._hover_bit_depth(window._source_images[1]) == 16

    def geometry() -> tuple[tuple[int, int, int], tuple[int, int, int]]:
        return (
            (pair.position.x(), pair.position.y(), pair.position.width()),
            (pair.values.x(), pair.values.y(), pair.values.width()),
        )

    original_geometry = geometry()
    window.statusBar().showMessage("Open failed: reserved for reader error")
    starts: set[tuple[int, int]] = set()
    for x, y in ((0, 0), (65, 1), (127, 127), (1, 65), (0, 0)):
        window._show_hover_pixel(x, y)
        QApplication.processEvents()
        text = pair.values.full_text
        assert "Reference RGB8:" in text
        assert "Target RGB16:" in text
        assert text.count("  ·  ") == 2
        starts.add((text.index("Target RGB16:"), text.index("Example dB Map")))
        assert pair.values.toolTip() == text
        assert pair.position.toolTip() == f"Pixel ({x}, {y})"
        assert window.statusBar().currentMessage() == "Open failed: reserved for reader error"
        assert geometry() == original_geometry
    assert len(starts) == 1  # Following columns never drift with RGB values.

    unavailable = replace(mixed, result_id="source-missing", source_b=None)
    window.present_result(unavailable)
    QApplication.processEvents()
    missing_geometry = geometry()  # Width changes only at a result transition.
    positions: set[int] = set()
    for x, y in ((0, 0), (65, 1), (127, 127)):
        window._show_hover_pixel(x, y)
        QApplication.processEvents()
        text = pair.values.full_text
        positions.add(text.index("Example dB Map"))
        assert "Target RGB: unavailable" in text
        assert geometry() == missing_geometry
    assert len(positions) == 1
    window.close()


def test_exit_closes_only_analysis_window(qtbot: object) -> None:
    manager = AnalysisWindowManager()
    win = manager.show(_result("retained"))
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    assert win.isVisible()
    win.exit_action.trigger()
    assert not win.isVisible()
    assert win.active_result_id == "retained"
    assert "retained" in win._results
    assert manager.show() is win
    assert win.active_result_id == "retained"
    manager.shutdown()


def test_reader_writer_contributed_type_drives_dialogs(
    qtbot: object, monkeypatch: object, tmp_path: Path
) -> None:
    presented = _result("pair:2026/10")
    paths: list[Path] = []
    dialogs: list[tuple[str, str, str]] = []

    def open_dialog(
        _owner: object, title: str, suggested: str, filter_text: str
    ) -> tuple[str, str]:
        dialogs.append((title, suggested, filter_text))
        return str(tmp_path / "loaded.pxiqa"), filter_text

    def save_dialog(
        _owner: object, title: str, suggested: str, filter_text: str
    ) -> tuple[str, str]:
        dialogs.append((title, suggested, filter_text))
        return str(tmp_path / "custom_name"), filter_text

    monkeypatch.setattr(QFileDialog, "getOpenFileName", open_dialog)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", save_dialog)
    manager = AnalysisWindowManager(
        load=lambda path: (paths.append(path), LoadedAnalysis(presented))[1],
        save=lambda _result, _state, path: paths.append(path),
        file_type=ResultFileType("PixelScope IQA result", ".pxiqa"),
    )
    win = manager.show()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.open_action.trigger()
    assert win.active_result_id == presented.result_id
    win.save_action.trigger()
    assert dialogs[0][2] == "PixelScope IQA result (*.pxiqa)"
    assert dialogs[1][1] == "pair_2026_10.pxiqa"
    assert dialogs[1][2] == "PixelScope IQA result (*.pxiqa)"
    assert paths == [tmp_path / "loaded.pxiqa", tmp_path / "custom_name.pxiqa"]
    manager.shutdown()


def test_file_type_metadata_is_validated_and_old_default_remains(
    qtbot: object, monkeypatch: object
) -> None:
    for description, suffix in (
        ("", ".pxiqa"),
        ("Unsafe;;filter", ".pxiqa"),
        ("PixelScope IQA result", "../pxiqa"),
        ("PixelScope IQA result", "*.pxiqa"),
    ):
        with pytest.raises(ValueError):
            ResultFileType(description, suffix)

    seen: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *args: (seen.append(args), ("", ""))[1],
    )
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.install_file_handlers(load=lambda _: LoadedAnalysis(_result("unused")))
    win.open_action.trigger()
    assert seen[0][3] == "Saved results (*)"
    win.close()
