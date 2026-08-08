from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from pixelscope.app.settings import ApplicationSettings, QSettingsAdapter, SettingsRepository
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


def test_new_general_settings_default_to_requested_values(qtbot: object) -> None:
    repository = _repository()
    initial = repository.load()
    dialog = SettingsDialog(repository, initial, initial.performance_settings())
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert not dialog.require_exact_raw_file_size.isChecked()
    assert dialog.difference_threshold.value() == 10
    assert dialog.difference_gain.value() == 1
    assert not dialog.restart_required


def test_raw_size_and_difference_defaults_round_trip_without_restart(
    qtbot: object,
) -> None:
    repository = _repository()
    initial = repository.load()
    dialog = SettingsDialog(repository, initial, initial.performance_settings())
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    dialog.require_exact_raw_file_size.setChecked(True)
    dialog.difference_threshold.setValue(24)
    dialog.difference_gain.setValue(3)

    assert dialog.settings() == ApplicationSettings(
        require_exact_raw_file_size=True,
        difference_threshold=24,
        difference_gain=3,
    )
    assert not dialog.restart_required
