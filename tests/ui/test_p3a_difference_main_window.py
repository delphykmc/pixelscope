from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QSettings

from pixelscope.app import main_window as main_window_module
from pixelscope.app.main_window import MainWindow
from pixelscope.app.settings import QSettingsAdapter, SettingsRepository


def _repository(path: Path) -> SettingsRepository:
    settings = QSettings(str(path), QSettings.Format.IniFormat)
    settings.clear()
    return SettingsRepository(QSettingsAdapter(settings))


def test_normalized_float32_difference_enters_and_refreshes_single_view(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    ui_settings = QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat)
    ui_settings.clear()
    monkeypatch.setattr(main_window_module, "QSettings", lambda: ui_settings)  # type: ignore[attr-defined]

    window = MainWindow(settings_repository=_repository(tmp_path / "app.ini"))
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.set_layout_mode("Single View")

    numerical = np.array([[0.0, 0.25], [0.5, 1.0]], dtype=np.float32)
    preview = np.rint(numerical[..., None] * np.array([255.0, 255.0, 255.0])).astype(np.uint8)
    window._difference_panel_ready("Normalized Gray Difference", numerical, preview)

    difference = window._difference_document
    assert difference is not None
    assert difference.channel_layout == "DIFFERENCE"
    assert difference.source is not None
    assert difference.source.dtype == np.dtype(np.float32)
    assert difference.bit_depth == 32  # Derived storage width, not source effective depth.
    assert window.viewer.document is difference
    assert window.central_stack.currentWidget() is window.viewer
    assert window.diff_action.isChecked()
    assert difference.pixel_at(1, 1) == 1.0

    updated = np.array([[1.0, 0.5], [0.25, 0.0]], dtype=np.float32)
    updated_preview = np.rint(updated[..., None] * np.array([255.0, 255.0, 255.0])).astype(np.uint8)
    window._difference_preview_updated(
        "Normalized Gray Difference updated",
        updated,
        updated_preview,
    )

    refreshed = window._difference_document
    assert refreshed is not None
    assert refreshed is not difference
    assert refreshed.source is not None
    assert refreshed.source.dtype == np.dtype(np.float32)
    assert refreshed.bit_depth == 32
    assert window.viewer.document is refreshed
    assert window.central_stack.currentWidget() is window.viewer
    assert window.diff_action.isChecked()
    assert refreshed.pixel_at(0, 0) == 1.0
    window.close()
