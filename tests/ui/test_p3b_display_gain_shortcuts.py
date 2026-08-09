from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QSettings
from PySide6.QtGui import QKeySequence

from pixelscope.app import main_window as main_window_module
from pixelscope.app.main_window import MainWindow
from pixelscope.app.settings import QSettingsAdapter, SettingsRepository
from pixelscope.core.display_transform import DisplayTransform
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.raw_display import render_raw_preview
from pixelscope.io.raw_profile import RawProfile
from pixelscope.ui.display_gain_shortcuts import install_display_gain_shortcuts
from pixelscope.ui.raw_display import install_raw_gain_control, raw_display_state


def _repository(path: Path) -> SettingsRepository:
    settings = QSettings(str(path), QSettings.Format.IniFormat)
    settings.clear()
    return SettingsRepository(QSettingsAdapter(settings))


def _raw_document() -> ImageDocument:
    profile = RawProfile(
        name="shortcut-raw",
        width=4,
        height=2,
        stride_bytes=8,
        bit_depth=12,
        channel_layout="GRAY",
        black_level=64,
        white_level=3800,
    )
    source = np.array(
        [[60, 64, 70, 512], [1024, 2048, 3072, 4095]],
        dtype=np.uint16,
    )
    return ImageDocument.from_array(
        source,
        "shortcut-raw",
        channel_layout="GRAY",
        bit_depth=12,
        raw_profile=profile,
        display_transform=DisplayTransform(display_low=0.0, display_high=4095.0),
        prepared_preview=render_raw_preview(
            source,
            channel_layout="GRAY",
            bit_depth=12,
            black_level=profile.black_level,
            gain=1.0,
        ),
    )


def test_display_gain_shortcuts_step_clamp_and_ignore_disabled_control(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    ui_settings = QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat)
    ui_settings.clear()
    monkeypatch.setattr(  # type: ignore[attr-defined]
        main_window_module,
        "QSettings",
        lambda: ui_settings,
    )

    window = MainWindow(settings_repository=_repository(tmp_path / "app.ini"))
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    combo = install_raw_gain_control(window)
    increase, decrease = install_display_gain_shortcuts(window, combo)

    assert increase.key() == QKeySequence("+")
    assert decrease.key() == QKeySequence("-")

    raw = _raw_document()
    window.add_document(raw, select=True)
    window.show()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.viewer.document is raw and combo.isEnabled()
    )

    increase.activated.emit()
    assert combo.currentData() == 2.0
    assert raw_display_state().gain == 2.0

    for _ in range(10):
        increase.activated.emit()
    assert combo.currentData() == 16.0
    assert raw_display_state().gain == 16.0

    increase.activated.emit()
    assert combo.currentData() == 16.0

    for _ in range(10):
        decrease.activated.emit()
    assert combo.currentData() == 1.0
    assert raw_display_state().gain == 1.0

    decrease.activated.emit()
    assert combo.currentData() == 1.0

    combo.setCurrentIndex(combo.findData(4.0))
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.viewer._displayed_raw_gain == 4.0
        and window.viewer._raw_preview_worker is None
    )

    non_raw = ImageDocument.from_array(
        np.arange(16, dtype=np.uint8).reshape(4, 4),
        "gray",
    )
    window.add_document(non_raw, select=False)
    window._select_document_ids([non_raw.document_id])
    window.set_layout_mode("Single View")
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.viewer.document is non_raw and not combo.isEnabled()
    )

    increase.activated.emit()
    decrease.activated.emit()
    assert combo.currentData() == 4.0
    assert raw_display_state().gain == 4.0

    window.close()
    raw_display_state().reset()
