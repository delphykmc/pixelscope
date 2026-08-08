from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox

from pixelscope.app.main_window import MainWindow
from pixelscope.app.settings import (
    ApplicationSettings,
    QSettingsAdapter,
    SettingsRepository,
)
from pixelscope.core.image_document import ImageDocument
from pixelscope.io.path_discovery import ImageInput
from pixelscope.io.raw_profile import RawProfile


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path: Path) -> None:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str(tmp_path),
    )
    settings = QSettings()
    settings.clear()
    settings.sync()


def _repository() -> SettingsRepository:
    return SettingsRepository(QSettingsAdapter(QSettings()))


def _raw_profile() -> RawProfile:
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


def _wait_for_load(qtbot: object, window: MainWindow, document_id: str) -> None:
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.documents[document_id].loading_state in {"ready", "error"},
        timeout=3000,
    )


def test_exact_raw_setting_reaches_worker_and_reader(
    qtbot: object,
    tmp_path: Path,
) -> None:
    raw_path = tmp_path / "oversized.raw"
    raw_path.write_bytes(bytes(40))
    profile = _raw_profile()

    relaxed = ApplicationSettings(require_exact_raw_file_size=False)
    relaxed_window = MainWindow(relaxed, relaxed.performance_settings(), _repository())
    qtbot.addWidget(relaxed_window)  # type: ignore[attr-defined]
    relaxed_document = ImageDocument.pending_document(raw_path)
    relaxed_window.documents[relaxed_document.document_id] = relaxed_document
    relaxed_window._start_load(relaxed_document.document_id, raw_path, profile)
    _wait_for_load(qtbot, relaxed_window, relaxed_document.document_id)

    relaxed_loaded = relaxed_window.documents[relaxed_document.document_id]
    assert relaxed_loaded.loading_state == "ready"
    assert relaxed_loaded.source is not None
    relaxed_window.close()

    exact = ApplicationSettings(require_exact_raw_file_size=True)
    exact_window = MainWindow(exact, exact.performance_settings(), _repository())
    qtbot.addWidget(exact_window)  # type: ignore[attr-defined]
    exact_document = ImageDocument.pending_document(raw_path)
    exact_window.documents[exact_document.document_id] = exact_document
    exact_window._start_load(exact_document.document_id, raw_path, profile)
    _wait_for_load(qtbot, exact_window, exact_document.document_id)

    loaded = exact_window.documents[exact_document.document_id]
    assert loaded.loading_state == "error"
    assert loaded.source is None
    assert loaded.error_state is not None
    exact_window.close()


def test_exact_raw_setting_controls_sidecar_auto_approval(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    raw_path = tmp_path / "oversized.raw"
    raw_path.write_bytes(bytes(40))
    sidecar = tmp_path / "oversized.json"
    profile = _raw_profile()
    profile.save_json(sidecar)

    class UnexpectedDialog:
        def __init__(self, _parent: object) -> None:
            raise AssertionError("relaxed valid sidecar unexpectedly opened the dialog")

    monkeypatch.setattr(  # type: ignore[attr-defined]
        "pixelscope.app.main_window.RawOpenDialog",
        UnexpectedDialog,
    )
    relaxed = ApplicationSettings(
        dont_show_raw_json_profiles=True,
        require_exact_raw_file_size=False,
    )
    relaxed_window = MainWindow(relaxed, relaxed.performance_settings(), _repository())
    qtbot.addWidget(relaxed_window)  # type: ignore[attr-defined]
    confirmed = relaxed_window._confirm_raw_profile(ImageInput(raw_path, sidecar), None)
    assert confirmed == profile
    relaxed_window.close()

    class ExactMismatchDialog:
        constructed = False

        def __init__(self, _parent: object) -> None:
            type(self).constructed = True

        def set_source_path(self, _path: Path) -> None:
            pass

        def set_profile(self, _profile: RawProfile) -> None:
            pass

        def set_json_confirmation_option_visible(self, _visible: bool) -> None:
            pass

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(  # type: ignore[attr-defined]
        "pixelscope.app.main_window.RawOpenDialog",
        ExactMismatchDialog,
    )
    exact = replace(relaxed, require_exact_raw_file_size=True)
    exact_window = MainWindow(exact, exact.performance_settings(), _repository())
    qtbot.addWidget(exact_window)  # type: ignore[attr-defined]

    confirmed = exact_window._confirm_raw_profile(ImageInput(raw_path, sidecar), None)
    assert confirmed is None
    assert ExactMismatchDialog.constructed
    exact_window.close()


def test_difference_defaults_apply_at_startup_and_on_settings_save(
    qtbot: object,
) -> None:
    repository = _repository()
    initial = ApplicationSettings(difference_threshold=37, difference_gain=5)
    repository.save(initial)
    window = MainWindow(initial, initial.performance_settings(), repository)
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert window.difference_panel.threshold.value() == 37
    assert window.difference_panel.gain.value() == 5

    dialog = window.create_settings_dialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.difference_threshold.setValue(73)
    dialog.difference_gain.setValue(9)
    assert not dialog.restart_required

    save_button = dialog.button_box.button(QDialogButtonBox.StandardButton.Save)
    assert save_button is not None
    qtbot.mouseClick(save_button, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]

    assert window.difference_panel.threshold.value() == 73
    assert window.difference_panel.gain.value() == 9
    persisted = repository.load()
    assert persisted.difference_threshold == 73
    assert persisted.difference_gain == 9
    window.close()


def test_raw_dont_show_update_preserves_all_v3_settings(
    qtbot: object,
    tmp_path: Path,
) -> None:
    repository = _repository()
    initial = ApplicationSettings(
        dont_show_raw_json_profiles=False,
        difference_cache_mib=1024,
        default_open_directory=str(tmp_path / "open"),
        default_export_directory=str(tmp_path / "export"),
        require_exact_raw_file_size=True,
        difference_threshold=91,
        difference_gain=7,
    )
    repository.save(initial)
    window = MainWindow(initial, initial.performance_settings(), repository)
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    window._set_dont_show_raw_json_profiles(True)

    expected = replace(initial, dont_show_raw_json_profiles=True)
    assert window.application_settings == expected
    assert repository.load() == expected
    window.close()
