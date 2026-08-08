from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from pixelscope.app.settings import (
    CURRENT_SETTINGS_SCHEMA_VERSION,
    DEFAULT_DIFFERENCE_GAIN,
    DEFAULT_DIFFERENCE_THRESHOLD,
    DIFFERENCE_GAIN_KEY,
    DIFFERENCE_THRESHOLD_KEY,
    REQUIRE_EXACT_RAW_FILE_SIZE_KEY,
    SCHEMA_VERSION_KEY,
    ApplicationSettings,
    QSettingsAdapter,
    SettingsRepository,
)


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


def _repository() -> tuple[SettingsRepository, QSettings]:
    settings = QSettings()
    return SettingsRepository(QSettingsAdapter(settings)), settings


def test_schema_v3_defaults_match_requested_raw_and_difference_behavior() -> None:
    repository, settings = _repository()

    loaded = repository.load()

    assert loaded.require_exact_raw_file_size is False
    assert loaded.difference_threshold == DEFAULT_DIFFERENCE_THRESHOLD == 10
    assert loaded.difference_gain == DEFAULT_DIFFERENCE_GAIN == 1
    assert settings.value(SCHEMA_VERSION_KEY, type=int) == CURRENT_SETTINGS_SCHEMA_VERSION
    assert settings.value(REQUIRE_EXACT_RAW_FILE_SIZE_KEY, type=bool) is False
    assert settings.value(DIFFERENCE_THRESHOLD_KEY, type=int) == 10
    assert settings.value(DIFFERENCE_GAIN_KEY, type=int) == 1


def test_schema_v2_migrates_new_fields_to_defaults() -> None:
    repository, settings = _repository()
    settings.setValue(SCHEMA_VERSION_KEY, 2)
    settings.setValue("settings/general/dont_show_raw_json_profiles", True)
    settings.setValue("settings/files/default_open_directory", "C:/images")
    settings.setValue("settings/files/default_export_directory", "D:/exports")
    settings.setValue("settings/performance/difference_cache_mib", 1024)

    loaded = repository.load()

    assert loaded == ApplicationSettings(
        dont_show_raw_json_profiles=True,
        difference_cache_mib=1024,
        default_open_directory="C:/images",
        default_export_directory="D:/exports",
    )
    assert settings.value(SCHEMA_VERSION_KEY, type=int) == 3
    assert settings.value(REQUIRE_EXACT_RAW_FILE_SIZE_KEY, type=bool) is False
    assert settings.value(DIFFERENCE_THRESHOLD_KEY, type=int) == 10
    assert settings.value(DIFFERENCE_GAIN_KEY, type=int) == 1


def test_schema_v3_new_fields_round_trip() -> None:
    repository, settings = _repository()
    expected = ApplicationSettings(
        require_exact_raw_file_size=True,
        difference_threshold=32,
        difference_gain=4,
    )

    repository.save(expected)

    assert repository.load() == expected
    assert settings.value(REQUIRE_EXACT_RAW_FILE_SIZE_KEY, type=bool) is True
    assert settings.value(DIFFERENCE_THRESHOLD_KEY, type=int) == 32
    assert settings.value(DIFFERENCE_GAIN_KEY, type=int) == 4
