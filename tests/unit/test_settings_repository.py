from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from pixelscope.app.settings import (
    CURRENT_SETTINGS_SCHEMA_VERSION,
    DEFAULT_DIFFERENCE_CACHE_MIB,
    DIFFERENCE_CACHE_MIB_KEY,
    DONT_SHOW_RAW_JSON_PROFILES_KEY,
    LEGACY_DONT_SHOW_RAW_JSON_PROFILES_KEY,
    MAX_DIFFERENCE_CACHE_MIB,
    MIN_DIFFERENCE_CACHE_MIB,
    SCHEMA_VERSION_KEY,
    ApplicationSettings,
    QSettingsAdapter,
    SettingsRepository,
    UnsupportedSettingsSchemaError,
)
from pixelscope.core.performance_settings import MIB


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path: Path) -> None:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    settings = QSettings()
    settings.clear()
    settings.sync()


def _repository() -> tuple[SettingsRepository, QSettings]:
    settings = QSettings()
    return SettingsRepository(QSettingsAdapter(settings)), settings


def test_application_settings_defaults_custom_validation_and_immutability() -> None:
    defaults = ApplicationSettings()
    assert defaults.dont_show_raw_json_profiles is False
    assert defaults.difference_cache_mib == 512
    custom = ApplicationSettings(True, 1024)
    runtime = custom.performance_settings()
    assert runtime.difference_cache_bytes == 1024 * MIB

    with pytest.raises(ValueError):
        ApplicationSettings(difference_cache_mib=MIN_DIFFERENCE_CACHE_MIB - 1)
    with pytest.raises(ValueError):
        ApplicationSettings(difference_cache_mib=MAX_DIFFERENCE_CACHE_MIB + 1)
    with pytest.raises(TypeError):
        ApplicationSettings(dont_show_raw_json_profiles=1)  # type: ignore[arg-type]
    with pytest.raises(FrozenInstanceError):
        custom.difference_cache_mib = 256  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        runtime.difference_cache_bytes = 256 * MIB  # type: ignore[misc]


def test_fresh_repository_normalizes_defaults_and_schema() -> None:
    repository, settings = _repository()

    loaded = repository.load()

    assert loaded == ApplicationSettings()
    assert settings.value(SCHEMA_VERSION_KEY, type=int) == CURRENT_SETTINGS_SCHEMA_VERSION
    assert settings.value(DONT_SHOW_RAW_JSON_PROFILES_KEY, type=bool) is False
    assert settings.value(DIFFERENCE_CACHE_MIB_KEY, type=int) == DEFAULT_DIFFERENCE_CACHE_MIB


def test_saved_state_round_trips_and_converts_mib_to_runtime_bytes() -> None:
    repository, _settings = _repository()
    expected = ApplicationSettings(True, 1536)

    repository.save(expected)
    loaded = repository.load()

    assert loaded == expected
    assert loaded.performance_settings().difference_cache_bytes == 1536 * MIB


@pytest.mark.parametrize(
    ("persisted", "expected"),
    [(True, True), (False, False), ("true", True), ("false", False), ("1", True), ("0", False)],
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

    loaded = repository.load()

    assert loaded.dont_show_raw_json_profiles is False
    assert settings.value(DONT_SHOW_RAW_JSON_PROFILES_KEY, type=bool) is False


@pytest.mark.parametrize(
    "persisted",
    ["not-a-number", 0, -1, MIN_DIFFERENCE_CACHE_MIB - 1, MAX_DIFFERENCE_CACHE_MIB + 1],
)
def test_invalid_cache_budget_falls_back_and_normalizes(persisted: object) -> None:
    repository, settings = _repository()
    settings.setValue(SCHEMA_VERSION_KEY, CURRENT_SETTINGS_SCHEMA_VERSION)
    settings.setValue(DONT_SHOW_RAW_JSON_PROFILES_KEY, False)
    settings.setValue(DIFFERENCE_CACHE_MIB_KEY, persisted)

    loaded = repository.load()

    assert loaded.difference_cache_mib == DEFAULT_DIFFERENCE_CACHE_MIB
    assert settings.value(DIFFERENCE_CACHE_MIB_KEY, type=int) == DEFAULT_DIFFERENCE_CACHE_MIB


def test_future_schema_uses_safe_defaults_without_rewrite() -> None:
    repository, settings = _repository()
    future = CURRENT_SETTINGS_SCHEMA_VERSION + 10
    settings.setValue(SCHEMA_VERSION_KEY, future)
    settings.setValue(DONT_SHOW_RAW_JSON_PROFILES_KEY, True)
    settings.setValue(DIFFERENCE_CACHE_MIB_KEY, 1024)

    loaded = repository.load()

    assert loaded == ApplicationSettings()
    assert repository.future_schema_version == future
    assert settings.value(SCHEMA_VERSION_KEY, type=int) == future
    assert settings.value(DIFFERENCE_CACHE_MIB_KEY, type=int) == 1024
    with pytest.raises(UnsupportedSettingsSchemaError):
        repository.save(ApplicationSettings(True, 2048))


def test_reset_only_changes_application_settings_keys() -> None:
    repository, settings = _repository()
    repository.save(ApplicationSettings(True, 2048))
    settings.setValue("ui/window_geometry", "geometry")
    settings.setValue("paths/last_directory", "C:/images")
    settings.setValue("unrelated/key", "keep")

    reset = repository.reset()

    assert reset == ApplicationSettings()
    assert settings.value(DONT_SHOW_RAW_JSON_PROFILES_KEY, type=bool) is False
    assert settings.value(DIFFERENCE_CACHE_MIB_KEY, type=int) == 512
    assert settings.value("ui/window_geometry") == "geometry"
    assert settings.value("paths/last_directory") == "C:/images"
    assert settings.value("unrelated/key") == "keep"
