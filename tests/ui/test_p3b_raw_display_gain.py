from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QComboBox

from pixelscope.app import main_window as main_window_module
from pixelscope.app.main_window import MainWindow
from pixelscope.app.settings import QSettingsAdapter, SettingsRepository
from pixelscope.core.display_transform import DisplayTransform
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.raw_display import render_raw_preview
from pixelscope.io.raw_profile import RawProfile
from pixelscope.ui.multi_compare_view import MultiCompareView
from pixelscope.ui.raw_display import install_raw_gain_control, raw_display_state


def _repository(path: Path) -> tuple[SettingsRepository, QSettings]:
    settings = QSettings(str(path), QSettings.Format.IniFormat)
    settings.clear()
    return SettingsRepository(QSettingsAdapter(settings)), settings


def _raw_document(name: str, offset: int = 0) -> ImageDocument:
    profile = RawProfile(
        name=name,
        width=4,
        height=2,
        stride_bytes=8,
        bit_depth=12,
        channel_layout="GRAY",
        black_level=64,
        white_level=3800,
    )
    source = np.array(
        [[60 + offset, 64 + offset, 70 + offset, 512], [1024, 2048, 3072, 4095]],
        dtype=np.uint16,
    )
    return ImageDocument.from_array(
        source,
        name,
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


def test_raw_gain_control_is_session_only_and_updates_single_and_multi_view(
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
    repository, app_store = _repository(tmp_path / "app.ini")
    window = MainWindow(settings_repository=repository)
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    combo = install_raw_gain_control(window)
    assert isinstance(combo, QComboBox)
    assert combo.objectName() == "RawGainCombo"
    assert combo.currentData() == 1.0

    first = _raw_document("first")
    second = _raw_document("second", 1)
    first_source = first.source.copy() if first.source is not None else None
    first_preview = first.preview
    first_generation = first.generation

    window.add_document(first, select=True)
    window.show()
    qtbot.waitUntil(lambda: window.viewer.document is first)  # type: ignore[attr-defined]
    assert combo.isEnabled()
    resident_bytes = window.residency_manager.used_bytes

    combo.setCurrentIndex(combo.findData(4.0))
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.viewer._displayed_raw_gain == 4.0
        and window.viewer._raw_preview_worker is None
    )
    assert first.source is not None
    assert first_source is not None
    assert np.array_equal(first.source, first_source)
    assert first.preview is first_preview
    assert first.generation == first_generation
    assert first.pixel_at(0, 0) == int(first_source[0, 0])
    assert window.residency_manager.used_bytes == resident_bytes

    # A superseded asynchronous request must never overwrite the newest gain.
    combo.setCurrentIndex(combo.findData(8.0))
    combo.setCurrentIndex(combo.findData(2.0))
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.viewer._displayed_raw_gain == 2.0
        and window.viewer._raw_preview_worker is None
    )
    qtbot.wait(25)  # type: ignore[attr-defined]
    assert window.viewer._displayed_raw_gain == 2.0
    assert first.generation == first_generation

    window.add_document(second, select=False)
    window._select_document_ids([first.document_id, second.document_id])
    window.set_layout_mode("Multi View")
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.central_stack.currentWidget() is window.multi_compare_view
        and len(window.multi_compare_view.occupied_viewers) == 2
    )
    combo.setCurrentIndex(combo.findData(4.0))
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: all(
            viewer._displayed_raw_gain == 4.0
            for viewer in window.multi_compare_view.occupied_viewers
        )
    )

    non_raw = ImageDocument.from_array(
        np.arange(16, dtype=np.uint8).reshape(4, 4),
        "gray",
    )
    window.add_document(non_raw, select=False)
    window._select_document_ids([non_raw.document_id])
    window.set_layout_mode("Single View")
    qtbot.waitUntil(lambda: window.viewer.document is non_raw)  # type: ignore[attr-defined]
    assert not combo.isEnabled()
    assert not any("raw_gain" in key.casefold() for key in app_store.allKeys())
    assert not any("raw_display" in key.casefold() for key in app_store.allKeys())
    window.close()
    raw_display_state().reset()


def test_raw_gain_state_disconnects_when_control_is_destroyed(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    ui_settings = QSettings(str(tmp_path / "ui-teardown.ini"), QSettings.Format.IniFormat)
    ui_settings.clear()
    monkeypatch.setattr(  # type: ignore[attr-defined]
        main_window_module,
        "QSettings",
        lambda: ui_settings,
    )
    repository, _app_store = _repository(tmp_path / "app-teardown.ini")
    window = MainWindow(settings_repository=repository)
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    combo = install_raw_gain_control(window)
    state = raw_display_state()

    state.set_gain(2.0)
    assert combo.currentData() == 2.0

    destroyed: list[bool] = []
    combo.destroyed.connect(lambda: destroyed.append(True))
    combo.deleteLater()
    qtbot.waitUntil(lambda: bool(destroyed))  # type: ignore[attr-defined]

    # The QApplication-owned state outlives toolbar controls. Emitting after the
    # combo is destroyed must not call a Python closure holding its dead C++ object.
    state.set_gain(4.0)
    assert state.gain == 4.0
    state.reset()
    window.close()


def test_hidden_multi_viewers_release_gained_preview_and_regenerate_when_shown(
    qtbot: object,
) -> None:
    state = raw_display_state()
    state.reset()
    view = MultiCompareView()
    qtbot.addWidget(view)  # type: ignore[attr-defined]
    documents = [_raw_document(f"raw-{index}", index) for index in range(6)]

    view.set_capacity(6)
    view.show()
    view.set_documents(documents, 0, 6, None, None)
    state.set_gain(4.0)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: all(
            viewer._displayed_raw_gain == 4.0 and viewer._raw_preview_worker is None
            for viewer in view.viewers
        )
    )
    assert all(
        viewer.document is not None and viewer._displayed_preview is not viewer.document.preview
        for viewer in view.viewers
    )

    view.set_capacity(2)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: all(viewer.isHidden() for viewer in view.viewers[2:])
    )
    for viewer in view.viewers[2:]:
        assert viewer.document is not None
        assert viewer._displayed_preview is viewer.document.preview
        assert viewer._displayed_raw_gain == 1.0
        assert viewer._raw_preview_worker is None

    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: all(viewer._displayed_raw_gain == 4.0 for viewer in view.viewers[:2])
    )
    view.set_capacity(6)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: all(
            viewer._displayed_raw_gain == 4.0 and viewer._raw_preview_worker is None
            for viewer in view.viewers
        )
    )
    assert all(
        viewer.document is not None and viewer._displayed_preview is not viewer.document.preview
        for viewer in view.viewers
    )

    view.close()
    state.reset()
