from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from pixelscope.app.settings import (
    CURRENT_SETTINGS_SCHEMA_VERSION,
    DEFAULT_DIFFERENCE_CACHE_MIB,
    DEFAULT_EXPORT_DIRECTORY_KEY,
    DEFAULT_OPEN_DIRECTORY_KEY,
    DEFAULT_SOURCE_RESIDENCY_MIB,
    DIFFERENCE_CACHE_MIB_KEY,
    DONT_SHOW_RAW_JSON_PROFILES_KEY,
    LEGACY_DONT_SHOW_RAW_JSON_PROFILES_KEY,
    MAX_DIFFERENCE_CACHE_MIB,
    MAX_SOURCE_RESIDENCY_MIB,
    MIN_DIFFERENCE_CACHE_MIB,
    MIN_SOURCE_RESIDENCY_MIB,
    SCHEMA_VERSION_KEY,
    SOURCE_RESIDENCY_MIB_KEY,
    ApplicationSettings,
    QSettingsAdapter,
    SettingsRepository,
    UnsupportedSettingsSchemaError,
)
from pixelscope.core.performance_settings import MIB


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


def test_application_settings_defaults_custom_validation_and_immutability() -> None:
    defaults = ApplicationSettings()
    assert defaults.dont_show_raw_json_profiles is False
    assert defaults.difference_cache_mib == 128
    assert defaults.source_residency_mib == 256
    assert defaults.default_open_directory == ""
    assert defaults.default_export_directory == ""

    custom = ApplicationSettings(
        dont_show_raw_json_profiles=True,
        difference_cache_mib=1024,
        source_residency_mib=2048,
        default_open_directory="C:/images",
        default_export_directory="D:/exports",
    )
    runtime = custom.performance_settings()
    assert runtime.difference_cache_bytes == 1024 * MIB
    assert runtime.source_residency_bytes == 2048 * MIB

    with pytest.raises(ValueError):
        ApplicationSettings(difference_cache_mib=MIN_DIFFERENCE_CACHE_MIB - 1)
    with pytest.raises(ValueError):
        ApplicationSettings(difference_cache_mib=MAX_DIFFERENCE_CACHE_MIB + 1)
    with pytest.raises(ValueError):
        ApplicationSettings(source_residency_mib=MIN_SOURCE_RESIDENCY_MIB - 1)
    with pytest.raises(ValueError):
        ApplicationSettings(source_residency_mib=MAX_SOURCE_RESIDENCY_MIB + 1)
    with pytest.raises(TypeError):
        ApplicationSettings(dont_show_raw_json_profiles=1)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        ApplicationSettings(default_open_directory=1)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        ApplicationSettings(default_export_directory="bad\x00path")
    with pytest.raises(FrozenInstanceError):
        custom.difference_cache_mib = 256  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        runtime.difference_cache_bytes = 256 * MIB  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        runtime.source_residency_bytes = 256 * MIB  # type: ignore[misc]


def test_fresh_repository_normalizes_defaults_and_schema() -> None:
    repository, settings = _repository()

    loaded = repository.load()

    assert loaded == ApplicationSettings()
    assert settings.value(SCHEMA_VERSION_KEY, type=int) == CURRENT_SETTINGS_SCHEMA_VERSION
    assert settings.value(DONT_SHOW_RAW_JSON_PROFILES_KEY, type=bool) is False
    assert settings.value(DIFFERENCE_CACHE_MIB_KEY, type=int) == DEFAULT_DIFFERENCE_CACHE_MIB
    assert settings.value(SOURCE_RESIDENCY_MIB_KEY, type=int) == DEFAULT_SOURCE_RESIDENCY_MIB
    assert settings.value(DEFAULT_OPEN_DIRECTORY_KEY, type=str) == ""
    assert settings.value(DEFAULT_EXPORT_DIRECTORY_KEY, type=str) == ""


def test_saved_state_round_trips_and_converts_mib_to_runtime_bytes() -> None:
    repository, _settings = _repository()
    expected = ApplicationSettings(
        dont_show_raw_json_profiles=True,
        difference_cache_mib=1280,
        source_residency_mib=2560,
        default_open_directory="C:/open",
        default_export_directory="D:/export",
    )

    repository.save(expected)
    loaded = repository.load()

    assert loaded == expected
    assert loaded.performance_settings().difference_cache_bytes == 1280 * MIB
    assert loaded.performance_settings().source_residency_bytes == 2560 * MIB


def test_schema_v1_migrates_to_v2_with_default_file_locations() -> None:
    repository, settings = _repository()
    settings.setValue(SCHEMA_VERSION_KEY, 1)
    settings.setValue(DONT_SHOW_RAW_JSON_PROFILES_KEY, True)
    settings.setValue(DIFFERENCE_CACHE_MIB_KEY, 1024)

    loaded = repository.load()

    assert loaded == ApplicationSettings(
        dont_show_raw_json_profiles=True,
        difference_cache_mib=1024,
    )
    assert settings.value(SCHEMA_VERSION_KEY, type=int) == CURRENT_SETTINGS_SCHEMA_VERSION
    assert settings.value(DEFAULT_OPEN_DIRECTORY_KEY, type=str) == ""
    assert settings.value(DEFAULT_EXPORT_DIRECTORY_KEY, type=str) == ""


@pytest.mark.parametrize(
    ("persisted", "expected"),
    [
        (True, True),
        (False, False),
        ("true", True),
        ("false", False),
        ("1", True),
        ("0", False),
        ("yes", True),
        ("on", True),
        ("no", False),
        ("off", False),
    ],
)
def test_legacy_raw_preference_migrates(persisted: object, expected: bool) -> None:
    repository, settings = _repository()
    settings.setValue(LEGACY_DONT_SHOW_RAW_JSON_PROFILES_KEY, persisted)

    loaded = repository.load()

    assert loaded.dont_show_raw_json_profiles is expected
    assert settings.value(DONT_SHOW_RAW_JSON_PROFILES_KEY, type=bool) is expected
    assert not settings.contains(LEGACY_DONT_SHOW_RAW_JSON_PROFILES_KEY)


@pytest.mark.parametrize("persisted", ["not-a-bool", "", "2"])
def test_malformed_bool_falls_back_and_normalizes(persisted: object) -> None:
    repository, settings = _repository()
    settings.setValue(SCHEMA_VERSION_KEY, CURRENT_SETTINGS_SCHEMA_VERSION)
    settings.setValue(DONT_SHOW_RAW_JSON_PROFILES_KEY, persisted)
    settings.setValue(DIFFERENCE_CACHE_MIB_KEY, 512)
    settings.setValue(DEFAULT_OPEN_DIRECTORY_KEY, "")
    settings.setValue(DEFAULT_EXPORT_DIRECTORY_KEY, "")

    loaded = repository.load()

    assert loaded.dont_show_raw_json_profiles is False
    assert settings.value(DONT_SHOW_RAW_JSON_PROFILES_KEY, type=bool) is False


@pytest.mark.parametrize(
    "persisted",
    [
        "not-a-number",
        0,
        -1,
        MIN_DIFFERENCE_CACHE_MIB - 1,
        MAX_DIFFERENCE_CACHE_MIB + 1,
    ],
)
def test_invalid_cache_budget_falls_back_and_normalizes(persisted: object) -> None:
    repository, settings = _repository()
    settings.setValue(SCHEMA_VERSION_KEY, CURRENT_SETTINGS_SCHEMA_VERSION)
    settings.setValue(DONT_SHOW_RAW_JSON_PROFILES_KEY, False)
    settings.setValue(DIFFERENCE_CACHE_MIB_KEY, persisted)
    settings.setValue(DEFAULT_OPEN_DIRECTORY_KEY, "")
    settings.setValue(DEFAULT_EXPORT_DIRECTORY_KEY, "")

    loaded = repository.load()

    assert loaded.difference_cache_mib == DEFAULT_DIFFERENCE_CACHE_MIB
    assert settings.value(DIFFERENCE_CACHE_MIB_KEY, type=int) == DEFAULT_DIFFERENCE_CACHE_MIB


@pytest.mark.parametrize(
    "persisted",
    [
        "not-a-number",
        0,
        -1,
        MIN_SOURCE_RESIDENCY_MIB - 1,
        MAX_SOURCE_RESIDENCY_MIB + 1,
    ],
)
def test_invalid_source_budget_falls_back_and_normalizes(persisted: object) -> None:
    repository, settings = _repository()
    settings.setValue(SCHEMA_VERSION_KEY, CURRENT_SETTINGS_SCHEMA_VERSION)
    settings.setValue(SOURCE_RESIDENCY_MIB_KEY, persisted)

    loaded = repository.load()

    assert loaded.source_residency_mib == DEFAULT_SOURCE_RESIDENCY_MIB
    assert settings.value(SOURCE_RESIDENCY_MIB_KEY, type=int) == DEFAULT_SOURCE_RESIDENCY_MIB


def test_invalid_file_locations_fall_back_and_normalize() -> None:
    repository, settings = _repository()
    settings.setValue(SCHEMA_VERSION_KEY, CURRENT_SETTINGS_SCHEMA_VERSION)
    settings.setValue(DONT_SHOW_RAW_JSON_PROFILES_KEY, False)
    settings.setValue(DIFFERENCE_CACHE_MIB_KEY, 512)
    settings.setValue(DEFAULT_OPEN_DIRECTORY_KEY, 42)
    settings.setValue(DEFAULT_EXPORT_DIRECTORY_KEY, None)

    loaded = repository.load()

    assert loaded.default_open_directory == ""
    assert loaded.default_export_directory == ""
    assert settings.value(DEFAULT_OPEN_DIRECTORY_KEY, type=str) == ""
    assert settings.value(DEFAULT_EXPORT_DIRECTORY_KEY, type=str) == ""


def test_future_schema_uses_safe_defaults_without_rewrite() -> None:
    repository, settings = _repository()
    future = CURRENT_SETTINGS_SCHEMA_VERSION + 10
    settings.setValue(SCHEMA_VERSION_KEY, future)
    settings.setValue(DONT_SHOW_RAW_JSON_PROFILES_KEY, True)
    settings.setValue(DIFFERENCE_CACHE_MIB_KEY, 1024)
    settings.setValue(SOURCE_RESIDENCY_MIB_KEY, 2048)
    settings.setValue(DEFAULT_OPEN_DIRECTORY_KEY, "C:/future-open")
    settings.setValue(DEFAULT_EXPORT_DIRECTORY_KEY, "D:/future-export")

    loaded = repository.load()

    assert loaded == ApplicationSettings()
    assert repository.future_schema_version == future
    assert settings.value(SCHEMA_VERSION_KEY, type=int) == future
    assert settings.value(DIFFERENCE_CACHE_MIB_KEY, type=int) == 1024
    assert settings.value(SOURCE_RESIDENCY_MIB_KEY, type=int) == 2048
    assert settings.value(DEFAULT_OPEN_DIRECTORY_KEY) == "C:/future-open"
    assert settings.value(DEFAULT_EXPORT_DIRECTORY_KEY) == "D:/future-export"
    with pytest.raises(UnsupportedSettingsSchemaError):
        repository.save(ApplicationSettings(True, 1280))


def test_reset_only_changes_application_settings_keys() -> None:
    repository, settings = _repository()
    repository.save(
        ApplicationSettings(
            dont_show_raw_json_profiles=True,
            difference_cache_mib=1280,
            source_residency_mib=2560,
            default_open_directory="C:/open",
            default_export_directory="D:/export",
        )
    )
    settings.setValue("ui/window_geometry", "geometry")
    settings.setValue("paths/last_directory", "C:/images")
    settings.setValue("unrelated/key", "keep")

    reset = repository.reset()

    assert reset == ApplicationSettings()
    assert settings.value(DONT_SHOW_RAW_JSON_PROFILES_KEY, type=bool) is False
    assert settings.value(DIFFERENCE_CACHE_MIB_KEY, type=int) == 128
    assert settings.value(SOURCE_RESIDENCY_MIB_KEY, type=int) == 256
    assert settings.value(DEFAULT_OPEN_DIRECTORY_KEY, type=str) == ""
    assert settings.value(DEFAULT_EXPORT_DIRECTORY_KEY, type=str) == ""
    assert settings.value("ui/window_geometry") == "geometry"
    assert settings.value("paths/last_directory") == "C:/images"
    assert settings.value("unrelated/key") == "keep"
