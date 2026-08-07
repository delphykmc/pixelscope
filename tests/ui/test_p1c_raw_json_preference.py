from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QDialog

from pixelscope.app.main_window import MainWindow
from pixelscope.app.settings import LEGACY_DONT_SHOW_RAW_JSON_PROFILES_KEY
from pixelscope.io.path_discovery import ImageInput
from pixelscope.io.raw_profile import RawProfile

LEGACY_SETTING_KEY = LEGACY_DONT_SHOW_RAW_JSON_PROFILES_KEY


@pytest.fixture(autouse=True)
def isolated_raw_json_settings(tmp_path: Path) -> None:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str(tmp_path),
    )
    settings = QSettings()
    settings.clear()
    settings.sync()


def _profile() -> RawProfile:
    return RawProfile(
        name="sensor",
        width=4,
        height=4,
        stride_bytes=8,
        storage_format="unpacked",
        container_dtype="uint16",
        endianness="little",
        bit_depth=10,
        bit_alignment="lsb",
        channel_layout="GRAY",
        black_level=0,
        white_level=1023,
    )


def test_raw_json_dont_show_menu_defaults_off_and_persists(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    action = window.action_map["Don't Show RAW JSON Profiles"]
    assert action.isCheckable()
    assert not action.isChecked()
    action.trigger()
    assert action.isChecked()
    assert window.settings_repository.load().dont_show_raw_json_profiles is True
    window.close()

    restored = MainWindow()
    qtbot.addWidget(restored)  # type: ignore[attr-defined]
    assert restored.action_map["Don't Show RAW JSON Profiles"].isChecked()
    restored.close()


def test_valid_json_sidecar_skips_dialog_when_legacy_dont_show_is_migrated(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    raw_path = tmp_path / "sensor.raw"
    raw_path.write_bytes(bytes(32))
    sidecar = tmp_path / "sensor.json"
    profile = _profile()
    profile.save_json(sidecar)
    settings = QSettings()
    settings.setValue(LEGACY_SETTING_KEY, True)
    settings.sync()

    class UnexpectedDialog:
        def __init__(self, _parent: object) -> None:
            raise AssertionError("valid JSON sidecar unexpectedly opened the dialog")

    monkeypatch.setattr(  # type: ignore[attr-defined]
        "pixelscope.app.main_window.RawOpenDialog",
        UnexpectedDialog,
    )
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert window._confirm_raw_profile(ImageInput(raw_path, sidecar), None) == profile
    assert not settings.contains(LEGACY_SETTING_KEY)
    window.close()


def test_too_small_source_still_opens_dialog_when_dont_show_is_enabled(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    raw_path = tmp_path / "small.raw"
    raw_path.write_bytes(bytes(8))
    sidecar = tmp_path / "small.json"
    _profile().save_json(sidecar)
    settings = QSettings()
    settings.setValue(LEGACY_SETTING_KEY, True)
    settings.sync()

    class SizeErrorDialog:
        constructed = False
        source_path: Path | None = None

        def __init__(self, _parent: object) -> None:
            self.loaded: RawProfile | None = None
            type(self).constructed = True

        def set_source_path(self, path: Path) -> None:
            type(self).source_path = path

        def set_profile(self, profile: RawProfile) -> None:
            self.loaded = profile

        def set_json_confirmation_option_visible(self, _visible: bool) -> None:
            pass

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(  # type: ignore[attr-defined]
        "pixelscope.app.main_window.RawOpenDialog",
        SizeErrorDialog,
    )
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert window._confirm_raw_profile(ImageInput(raw_path, sidecar), None) is None
    assert SizeErrorDialog.constructed
    assert SizeErrorDialog.source_path == raw_path
    window.close()


def test_dialog_dont_show_opt_in_enables_future_skip(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    raw_path = tmp_path / "accepted.raw"
    raw_path.write_bytes(bytes(32))
    sidecar = tmp_path / "accepted.json"
    profile = _profile()
    profile.save_json(sidecar)

    class DontShowDialog:
        def __init__(self, _parent: object) -> None:
            self.loaded: RawProfile | None = None

        def set_source_path(self, _path: Path) -> None:
            pass

        def set_profile(self, loaded: RawProfile) -> None:
            self.loaded = loaded

        def set_json_confirmation_option_visible(self, visible: bool) -> None:
            assert visible

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

        def profile(self) -> RawProfile:
            assert self.loaded is not None
            return self.loaded

        def dont_show_json_profiles_requested(self) -> bool:
            return True

    monkeypatch.setattr(  # type: ignore[attr-defined]
        "pixelscope.app.main_window.RawOpenDialog",
        DontShowDialog,
    )
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert window._confirm_raw_profile(ImageInput(raw_path, sidecar), None) == profile
    assert window.action_map["Don't Show RAW JSON Profiles"].isChecked()
    assert window.settings_repository.load().dont_show_raw_json_profiles is True
    window.close()
