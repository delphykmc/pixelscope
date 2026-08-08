from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from pixelscope.app.settings import (
    CURRENT_SETTINGS_SCHEMA_VERSION,
    DEFAULT_SOURCE_RESIDENCY_MIB,
    DIFFERENCE_CACHE_MIB_KEY,
    DIFFERENCE_GAIN_KEY,
    DIFFERENCE_THRESHOLD_KEY,
    DONT_SHOW_RAW_JSON_PROFILES_KEY,
    REQUIRE_EXACT_RAW_FILE_SIZE_KEY,
    SCHEMA_VERSION_KEY,
    SOURCE_RESIDENCY_MIB_KEY,
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


def test_schema_v4_fresh_default_is_256_mib() -> None:
    repository, settings = _repository()

    loaded = repository.load()

    assert loaded.source_residency_mib == DEFAULT_SOURCE_RESIDENCY_MIB == 256
    assert settings.value(SCHEMA_VERSION_KEY, type=int) == 4
    assert settings.value(SOURCE_RESIDENCY_MIB_KEY, type=int) == 256


def test_schema_v3_migration_preserves_every_value_and_adds_source_default() -> None:
    repository, settings = _repository()
    settings.setValue(SCHEMA_VERSION_KEY, 3)
    settings.setValue(DONT_SHOW_RAW_JSON_PROFILES_KEY, True)
    settings.setValue(REQUIRE_EXACT_RAW_FILE_SIZE_KEY, True)
    settings.setValue("settings/files/default_open_directory", "C:/images")
    settings.setValue("settings/files/default_export_directory", "D:/exports")
    settings.setValue(DIFFERENCE_THRESHOLD_KEY, 32)
    settings.setValue(DIFFERENCE_GAIN_KEY, 4)
    settings.setValue(DIFFERENCE_CACHE_MIB_KEY, 1280)
    settings.setValue("unrelated/workspace", "keep")

    loaded = repository.load()

    assert loaded == ApplicationSettings(
        dont_show_raw_json_profiles=True,
        difference_cache_mib=1280,
        source_residency_mib=256,
        default_open_directory="C:/images",
        default_export_directory="D:/exports",
        require_exact_raw_file_size=True,
        difference_threshold=32,
        difference_gain=4,
    )
    assert settings.value(SCHEMA_VERSION_KEY, type=int) == CURRENT_SETTINGS_SCHEMA_VERSION == 4
    assert settings.value(SOURCE_RESIDENCY_MIB_KEY, type=int) == 256
    assert settings.value("unrelated/workspace") == "keep"


@pytest.mark.parametrize("legacy_cache_mib", (2048, 4096, 8192))
def test_schema_v3_old_valid_cache_budget_clamps_to_new_maximum(
    legacy_cache_mib: int,
) -> None:
    repository, settings = _repository()
    settings.setValue(SCHEMA_VERSION_KEY, 3)
    settings.setValue(DIFFERENCE_CACHE_MIB_KEY, legacy_cache_mib)
    settings.setValue("unrelated/workspace", "keep")

    assert repository.load().difference_cache_mib == 1280
    assert settings.value(DIFFERENCE_CACHE_MIB_KEY, type=int) == 1280
    assert settings.value(SCHEMA_VERSION_KEY, type=int) == 4
    assert settings.value("unrelated/workspace") == "keep"


@pytest.mark.parametrize("legacy_cache_mib", ("bad", 0, 8193))
def test_schema_v3_invalid_cache_budget_uses_new_default(
    legacy_cache_mib: object,
) -> None:
    repository, settings = _repository()
    settings.setValue(SCHEMA_VERSION_KEY, 3)
    settings.setValue(DIFFERENCE_CACHE_MIB_KEY, legacy_cache_mib)

    assert repository.load().difference_cache_mib == 128
    assert settings.value(DIFFERENCE_CACHE_MIB_KEY, type=int) == 128


def test_schema_v4_source_budget_round_trips() -> None:
    repository, settings = _repository()
    expected = ApplicationSettings(source_residency_mib=2048)

    repository.save(expected)

    assert repository.load() == expected
    assert settings.value(SOURCE_RESIDENCY_MIB_KEY, type=int) == 2048
    assert settings.value(SCHEMA_VERSION_KEY, type=int) == 4


def test_schema_v2_still_migrates_all_later_fields_to_defaults() -> None:
    repository, settings = _repository()
    settings.setValue(SCHEMA_VERSION_KEY, 2)
    settings.setValue(DONT_SHOW_RAW_JSON_PROFILES_KEY, True)
    settings.setValue("settings/files/default_open_directory", "C:/images")
    settings.setValue("settings/files/default_export_directory", "D:/exports")
    settings.setValue(DIFFERENCE_CACHE_MIB_KEY, 1024)

    loaded = repository.load()

    assert loaded == ApplicationSettings(
        dont_show_raw_json_profiles=True,
        difference_cache_mib=1024,
        default_open_directory="C:/images",
        default_export_directory="D:/exports",
    )
    assert settings.value(SCHEMA_VERSION_KEY, type=int) == 4
    assert settings.value(REQUIRE_EXACT_RAW_FILE_SIZE_KEY, type=bool) is False
    assert settings.value(DIFFERENCE_THRESHOLD_KEY, type=int) == 10
    assert settings.value(DIFFERENCE_GAIN_KEY, type=int) == 1
    assert settings.value(SOURCE_RESIDENCY_MIB_KEY, type=int) == 256
