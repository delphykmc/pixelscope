from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox

from pixelscope.app.application import load_startup_settings
from pixelscope.app.main_window import MainWindow
from pixelscope.app.settings import (
    DEFAULT_EXPORT_DIRECTORY_KEY,
    DEFAULT_OPEN_DIRECTORY_KEY,
    DIFFERENCE_CACHE_MIB_KEY,
    ApplicationSettings,
    QSettingsAdapter,
    SettingsRepository,
)
from pixelscope.core.performance_settings import MIB
from pixelscope.ui.settings_dialog import SettingsDialog


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


def test_settings_action_opens_dialog(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[SettingsDialog] = []

    def fake_exec(dialog: SettingsDialog) -> int:
        opened.append(dialog)
        return int(QDialog.DialogCode.Rejected)

    monkeypatch.setattr(SettingsDialog, "exec", fake_exec)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    window.action_map["Settings..."].trigger()

    assert len(opened) == 1
    assert opened[0].windowTitle() == "Settings"


def test_settings_uses_general_files_and_performance_pages(qtbot: object) -> None:
    repository = _repository()
    initial = repository.save(
        ApplicationSettings(
            dont_show_raw_json_profiles=True,
            difference_cache_mib=1024,
            default_open_directory="C:/images",
            default_export_directory="D:/exports",
        )
    )
    dialog = SettingsDialog(repository, initial, initial.performance_settings())
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert [
        dialog.category_list.item(index).text()
        for index in range(dialog.category_list.count())
    ] == ["General", "Files", "Performance"]
    assert dialog.category_list.currentRow() == 0
    assert dialog.page_stack.currentIndex() == 0

    dialog.category_list.setCurrentRow(1)
    assert dialog.page_stack.currentIndex() == 1
    assert dialog.default_open_directory.text() == "C:/images"
    assert dialog.default_export_directory.text() == "D:/exports"

    dialog.category_list.setCurrentRow(2)
    assert dialog.page_stack.currentIndex() == 2
    assert dialog.difference_cache_mib.value() == 1024


def test_settings_prefill_save_cancel_and_runtime_cache_is_immutable(
    qtbot: object,
) -> None:
    repository = _repository()
    initial = repository.save(ApplicationSettings(True, 1024))
    runtime = initial.performance_settings()
    window = MainWindow(initial, runtime, repository)
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert "Settings..." in window.action_map
    assert "Don't Show RAW JSON Profiles" not in window.action_map
    dialog = window.create_settings_dialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    assert dialog.dont_show_raw_json_profiles.isChecked()
    assert dialog.difference_cache_mib.value() == 1024
    assert not dialog.restart_required

    dialog.dont_show_raw_json_profiles.setChecked(False)
    dialog.default_open_directory.setText("C:/open")
    dialog.default_export_directory.setText("D:/export")
    dialog.difference_cache_mib.setValue(2048)
    assert dialog.restart_required
    save = dialog.button_box.button(QDialogButtonBox.StandardButton.Save)
    assert save is not None
    qtbot.mouseClick(save, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]

    expected = ApplicationSettings(
        dont_show_raw_json_profiles=False,
        difference_cache_mib=2048,
        default_open_directory="C:/open",
        default_export_directory="D:/export",
    )
    assert repository.load() == expected
    assert window.application_settings == expected
    assert window.difference_panel.difference_cache.budget_bytes == 1024 * MIB

    cancelled = window.create_settings_dialog()
    qtbot.addWidget(cancelled)  # type: ignore[attr-defined]
    cancelled.default_open_directory.setText("C:/cancelled")
    cancelled.difference_cache_mib.setValue(4096)
    cancel = cancelled.button_box.button(QDialogButtonBox.StandardButton.Cancel)
    assert cancel is not None
    qtbot.mouseClick(cancel, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
    assert repository.load() == expected


def test_restart_required_changed_reverted_reset_and_reopen(qtbot: object) -> None:
    repository = _repository()
    initial = repository.save(ApplicationSettings(False, 512))
    runtime = initial.performance_settings()
    dialog = SettingsDialog(repository, initial, runtime)
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert not dialog.restart_required
    dialog.difference_cache_mib.setValue(1024)
    assert dialog.restart_required
    dialog.difference_cache_mib.setValue(512)
    assert not dialog.restart_required

    repository.save(
        ApplicationSettings(
            dont_show_raw_json_profiles=True,
            difference_cache_mib=1024,
            default_open_directory="C:/open",
            default_export_directory="D:/export",
        )
    )
    dialog.set_settings(repository.load())
    assert dialog.restart_required
    qtbot.mouseClick(  # type: ignore[attr-defined]
        dialog.reset_button,
        Qt.MouseButton.LeftButton,
    )
    assert repository.load() == ApplicationSettings()
    assert not dialog.restart_required

    reopened = SettingsDialog(repository, repository.load(), runtime)
    qtbot.addWidget(reopened)  # type: ignore[attr-defined]
    assert reopened.default_open_directory.text() == ""
    assert reopened.default_export_directory.text() == ""
    assert reopened.difference_cache_mib.value() == 512
    assert not reopened.restart_required


def test_difference_value_validation_and_startup_injection(qtbot: object) -> None:
    seed_repository = _repository()
    seed_repository.save(ApplicationSettings(False, 768))
    repository, persisted, runtime = load_startup_settings()
    window = MainWindow(persisted, runtime, repository)
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    dialog = window.create_settings_dialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    assert dialog.difference_cache_mib.minimum() == 64
    assert dialog.difference_cache_mib.maximum() == 8192
    dialog.difference_cache_mib.setValue(1)
    assert dialog.difference_cache_mib.value() == 64
    dialog.difference_cache_mib.setValue(99999)
    assert dialog.difference_cache_mib.value() == 8192
    dialog.difference_cache_mib.setValue(1024)
    assert persisted.difference_cache_mib == 768
    assert runtime.difference_cache_bytes == 768 * MIB
    assert window.difference_panel.difference_cache.budget_bytes == 768 * MIB

    save = dialog.button_box.button(QDialogButtonBox.StandardButton.Save)
    assert save is not None
    qtbot.mouseClick(save, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
    assert QSettings().value(DIFFERENCE_CACHE_MIB_KEY, type=int) == 1024
    assert window.difference_panel.difference_cache.budget_bytes == 768 * MIB


def test_settings_raw_preference_is_the_persistent_surface(qtbot: object) -> None:
    repository = _repository()
    initial = repository.load()
    window = MainWindow(initial, initial.performance_settings(), repository)
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert "Don't Show RAW JSON Profiles" not in window.action_map
    dialog = window.create_settings_dialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.dont_show_raw_json_profiles.setChecked(True)
    save = dialog.button_box.button(QDialogButtonBox.StandardButton.Save)
    assert save is not None
    qtbot.mouseClick(save, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]

    assert repository.load().dont_show_raw_json_profiles is True
    assert window.application_settings.dont_show_raw_json_profiles is True


def test_configured_file_locations_override_last_used_and_missing_paths_fallback(
    qtbot: object,
    tmp_path: Path,
) -> None:
    open_directory = tmp_path / "open"
    export_directory = tmp_path / "export"
    last_directory = tmp_path / "last"
    for directory in (open_directory, export_directory, last_directory):
        directory.mkdir()

    repository = _repository()
    initial = repository.save(
        ApplicationSettings(
            default_open_directory=str(open_directory),
            default_export_directory=str(export_directory),
        )
    )
    window = MainWindow(initial, initial.performance_settings(), repository)
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window._last_directory = str(last_directory)

    assert window._open_dialog_directory() == str(open_directory)
    assert window._export_dialog_directory() == str(export_directory)

    missing = ApplicationSettings(
        default_open_directory=str(tmp_path / "missing-open"),
        default_export_directory=str(tmp_path / "missing-export"),
    )
    window._application_settings_saved(missing)

    assert window._open_dialog_directory() == str(last_directory)
    assert window._export_dialog_directory() == str(last_directory)


def test_file_location_keys_are_saved_without_restart_requirement(
    qtbot: object,
) -> None:
    repository = _repository()
    initial = repository.load()
    dialog = SettingsDialog(repository, initial, initial.performance_settings())
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    dialog.default_open_directory.setText("C:/images")
    dialog.default_export_directory.setText("D:/exports")
    assert not dialog.restart_required
    save = dialog.button_box.button(QDialogButtonBox.StandardButton.Save)
    assert save is not None
    qtbot.mouseClick(save, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]

    assert QSettings().value(DEFAULT_OPEN_DIRECTORY_KEY, type=str) == "C:/images"
    assert QSettings().value(DEFAULT_EXPORT_DIRECTORY_KEY, type=str) == "D:/exports"


def test_reset_to_default_requires_restart_when_runtime_is_nondefault(
    qtbot: object,
) -> None:
    repository = _repository()
    initial = repository.save(ApplicationSettings(False, 1024))
    dialog = SettingsDialog(repository, initial, initial.performance_settings())
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert not dialog.restart_required
    qtbot.mouseClick(  # type: ignore[attr-defined]
        dialog.reset_button,
        Qt.MouseButton.LeftButton,
    )

    assert repository.load() == ApplicationSettings()
    assert dialog.restart_required
