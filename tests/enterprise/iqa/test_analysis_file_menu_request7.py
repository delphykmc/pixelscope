"""Request 7: file menu, injected package metadata and view-only unloading."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog

import numpy as np

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
        result_id, 128, 128, "Synthetic A", "Synthetic B", (attribute,),
        source_a=Path("missing-a.png"), source_b=Path("missing-b.png"),
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
    assert all("No result loaded" in view.scene().items()[0].toPlainText()
               for view in win._views)
    assert calls == []  # Close must never call injected disk I/O.

    # Clearing the final result does not poison later reuse of the same window.
    win.present_result(_result("new"))
    assert win.active_result_id == "new"
    assert win.close_result_action.isEnabled()
    win.close()


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

    def open_dialog(_owner: object, title: str, suggested: str, filter_text: str) -> tuple[str, str]:
        dialogs.append((title, suggested, filter_text))
        return str(tmp_path / "loaded.pxiqa"), filter_text

    def save_dialog(_owner: object, title: str, suggested: str, filter_text: str) -> tuple[str, str]:
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
