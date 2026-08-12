from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QComboBox, QLabel

from pixelscope.app import main_window as main_window_module
from pixelscope.app.main_window import MainWindow
from pixelscope.app.settings import QSettingsAdapter, SettingsRepository
from pixelscope.core.display_transform import DisplayTransform, render_ordinary_display_preview
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.raw_display import render_raw_preview
from pixelscope.io.raw_profile import RawProfile
from pixelscope.ui.display_gain import display_gain_state, install_display_gain_control
from pixelscope.ui.image_viewer import ImageViewer
from pixelscope.ui.multi_compare_view import MultiCompareView


def _repository(path: Path) -> SettingsRepository:
    settings = QSettings(str(path), QSettings.Format.IniFormat)
    settings.clear()
    return SettingsRepository(QSettingsAdapter(settings))


def _raw_document(name: str = "raw") -> ImageDocument:
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
        [[60, 64, 70, 512], [1024, 2048, 3072, 4095]],
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
        ),
    )


def _ordinary_document(layout: str, name: str, value: int = 20) -> ImageDocument:
    if layout == "GRAY":
        source = np.full((3, 4), value, dtype=np.uint8)
    else:
        channels = 4 if layout == "RGBA" else 3
        source = np.full((3, 4, channels), value, dtype=np.uint8)
        if layout == "RGBA":
            source[..., 3] = np.arange(12, dtype=np.uint8).reshape(3, 4) * np.uint8(17)
    return ImageDocument.from_array(source, name, channel_layout=layout)


def test_toolbar_is_one_general_display_gain_control_for_supported_presentations(
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
    combo = install_display_gain_control(window)
    label = window.findChild(QLabel, "DisplayGainLabel")

    assert label is not None
    assert label.text() == "Display Gain"
    assert combo.objectName() == "DisplayGainCombo"
    assert [combo.itemText(index) for index in range(combo.count())] == [
        "1×",
        "2×",
        "4×",
        "8×",
        "16×",
    ]
    assert len(window.findChildren(QComboBox, "DisplayGainCombo")) == 1

    window.show()
    window.central_stack.setCurrentWidget(window.viewer)
    for layout in ("GRAY", "RGB", "RGBA"):
        document = _ordinary_document(layout, layout.casefold())
        window.viewer.set_document(document)
        qtbot.waitUntil(lambda: combo.isEnabled())  # type: ignore[attr-defined]

    raw = _raw_document()
    window.viewer.set_document(raw)
    qtbot.waitUntil(lambda: combo.isEnabled())  # type: ignore[attr-defined]

    difference_source = np.array([[1, 2], [3, 4]], dtype=np.uint8)
    difference = ImageDocument.from_array(
        difference_source,
        "difference",
        channel_layout="DIFFERENCE",
    )
    window.viewer.set_document(difference)
    qtbot.waitUntil(lambda: not combo.isEnabled())  # type: ignore[attr-defined]
    assert window.viewer._displayed_preview is difference.preview
    assert window.viewer._display_preview_worker is None

    window.close()
    display_gain_state().reset()


def test_ordinary_gain_changes_preview_but_not_source_residency_or_generation(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    ui_settings = QSettings(str(tmp_path / "ui-residency.ini"), QSettings.Format.IniFormat)
    ui_settings.clear()
    monkeypatch.setattr(  # type: ignore[attr-defined]
        main_window_module,
        "QSettings",
        lambda: ui_settings,
    )
    window = MainWindow(settings_repository=_repository(tmp_path / "app-residency.ini"))
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    combo = install_display_gain_control(window)
    rgb = _ordinary_document("RGB", "rgb", 30)
    source = rgb.source
    assert source is not None
    assert rgb.preview is not None
    original = source.copy()
    generation = rgb.generation
    canonical = rgb.preview

    window.add_document(rgb, select=True)
    window.show()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.viewer.document is rgb and combo.isEnabled()
    )
    resident_bytes = window.residency_manager.used_bytes
    assert window.viewer._displayed_preview is canonical
    assert window.viewer._display_preview_worker is None

    combo.setCurrentIndex(combo.findData(4.0))
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.viewer._displayed_gain == 4.0
        and window.viewer._display_preview_worker is None
    )
    expected = render_ordinary_display_preview(
        source,
        channel_layout="RGB",
        transform=rgb.display_transform,
        canonical_preview=canonical,
        gain=4.0,
    )
    assert np.array_equal(window.viewer._displayed_preview, expected)
    assert window.viewer._displayed_preview is not canonical
    assert np.array_equal(source, original)
    assert rgb.generation == generation
    assert window.residency_manager.used_bytes == resident_bytes

    combo.setCurrentIndex(combo.findData(1.0))
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.viewer._displayed_preview is canonical
        and window.viewer._display_preview_worker is None
    )
    window.close()
    display_gain_state().reset()


def test_main_window_split_channels_apply_display_gain_to_transient_rgb_views(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    ui_settings = QSettings(str(tmp_path / "ui-split.ini"), QSettings.Format.IniFormat)
    ui_settings.clear()
    monkeypatch.setattr(  # type: ignore[attr-defined]
        main_window_module,
        "QSettings",
        lambda: ui_settings,
    )
    window = MainWindow(settings_repository=_repository(tmp_path / "app-split.ini"))
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    combo = install_display_gain_control(window)
    rgb = _ordinary_document("RGB", "split-rgb", 20)
    assert rgb.source is not None
    original = rgb.source.copy()

    window.add_document(rgb, select=True)
    window.show()
    qtbot.waitUntil(lambda: window.viewer.document is rgb)  # type: ignore[attr-defined]

    window.split_channels_action.trigger()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.central_stack.currentWidget() is window.multi_compare_view
        and len(window.multi_compare_view.occupied_viewers) == 3
        and combo.isEnabled()
    )
    viewers = window.multi_compare_view.occupied_viewers
    layouts = [viewer.document.channel_layout for viewer in viewers if viewer.document is not None]
    assert layouts == [
        "CHANNEL_R",
        "CHANNEL_G",
        "CHANNEL_B",
    ]

    combo.setCurrentIndex(combo.findData(4.0))
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: all(
            viewer._displayed_gain == 4.0 and viewer._display_preview_worker is None
            for viewer in viewers
        )
    )
    for channel_index, viewer in enumerate(viewers):
        document = viewer.document
        assert document is not None
        assert document.source is not None
        assert np.all(document.source == 20)
        assert isinstance(viewer._displayed_preview, np.ndarray)
        assert np.all(viewer._displayed_preview[..., channel_index] == 80)
        other_indices = [index for index in range(3) if index != channel_index]
        assert not np.any(viewer._displayed_preview[..., other_indices])

    assert np.array_equal(rgb.source, original)
    window.close()
    display_gain_state().reset()


def test_mixed_raw_and_rgb_multi_view_share_document_specific_gain_semantics(
    qtbot: object,
) -> None:
    state = display_gain_state()
    state.reset()
    view = MultiCompareView()
    qtbot.addWidget(view)  # type: ignore[attr-defined]
    raw = _raw_document()
    rgb = _ordinary_document("RGB", "rgb", 20)
    view.set_capacity(2)
    view.show()
    view.set_documents([raw, rgb], 0, 2, None, None)

    state.set_gain(4.0)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: all(
            viewer._displayed_gain == 4.0 and viewer._display_preview_worker is None
            for viewer in view.occupied_viewers
        )
    )
    assert raw.source is not None and raw.preview is not None
    assert rgb.source is not None and rgb.preview is not None
    raw_expected = render_raw_preview(
        raw.source,
        channel_layout="GRAY",
        bit_depth=12,
        black_level=64,
        gain=4.0,
    )
    rgb_expected = render_ordinary_display_preview(
        rgb.source,
        channel_layout="RGB",
        transform=rgb.display_transform,
        canonical_preview=rgb.preview,
        gain=4.0,
    )
    assert np.array_equal(view.viewers[0]._displayed_preview, raw_expected)
    assert np.array_equal(view.viewers[1]._displayed_preview, rgb_expected)

    view.close()
    state.reset()


def test_ordinary_rapid_gain_rejects_stale_result_and_hidden_preview_is_released(
    qtbot: object,
) -> None:
    state = display_gain_state()
    state.reset()
    view = MultiCompareView()
    qtbot.addWidget(view)  # type: ignore[attr-defined]
    documents = [_ordinary_document("RGB", f"rgb-{index}", 10 + index) for index in range(6)]
    view.set_capacity(6)
    view.show()
    view.set_documents(documents, 0, 6, None, None)

    state.set_gain(8.0)
    state.set_gain(2.0)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: all(
            viewer._displayed_gain == 2.0 and viewer._display_preview_worker is None
            for viewer in view.viewers
        )
    )
    qtbot.wait(25)  # type: ignore[attr-defined]
    assert all(viewer._displayed_gain == 2.0 for viewer in view.viewers)

    state.set_gain(4.0)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: all(viewer._displayed_gain == 4.0 for viewer in view.viewers)
    )
    view.set_capacity(2)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: all(viewer.isHidden() for viewer in view.viewers[2:])
    )
    for viewer in view.viewers[2:]:
        assert viewer.document is not None
        assert viewer._displayed_preview is viewer.document.preview
        assert viewer._displayed_gain == 1.0
        assert viewer._display_preview_worker is None

    view.set_capacity(6)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: all(
            viewer._displayed_gain == 4.0 and viewer._display_preview_worker is None
            for viewer in view.viewers
        )
    )
    view.close()
    state.reset()


def test_rgba_viewer_preserves_canonical_alpha_across_gain(qtbot: object) -> None:
    state = display_gain_state()
    state.reset()
    viewer = ImageViewer()
    qtbot.addWidget(viewer)  # type: ignore[attr-defined]
    rgba = _ordinary_document("RGBA", "rgba", 25)
    assert rgba.preview is not None
    canonical_alpha = rgba.preview[..., 3].copy()
    viewer.show()
    viewer.set_document(rgba)

    state.set_gain(4.0)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: viewer._displayed_gain == 4.0 and viewer._display_preview_worker is None
    )
    assert isinstance(viewer._displayed_preview, np.ndarray)
    assert np.array_equal(viewer._displayed_preview[..., 3], canonical_alpha)

    viewer.close()
    state.reset()
