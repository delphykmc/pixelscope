from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from pixelscope.app.settings import (
    CURRENT_SETTINGS_SCHEMA_VERSION,
    DIFFERENCE_THRESHOLD_KEY,
    MAX_DIFFERENCE_THRESHOLD,
    SCHEMA_VERSION_KEY,
    ApplicationSettings,
    QSettingsAdapter,
    SettingsRepository,
)


def _repository(tmp_path: Path) -> tuple[SettingsRepository, QSettings]:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.clear()
    settings.sync()
    return SettingsRepository(QSettingsAdapter(settings)), settings


def test_native_difference_threshold_product_bound_is_uint16_max() -> None:
    assert MAX_DIFFERENCE_THRESHOLD == 65_535
    settings = ApplicationSettings(difference_threshold=65_535)
    assert settings.difference_threshold == 65_535
    with pytest.raises(ValueError):
        ApplicationSettings(difference_threshold=65_536)


def test_schema_v5_oversized_native_threshold_normalizes_to_uint16_max(
    tmp_path: Path,
) -> None:
    repository, settings = _repository(tmp_path)
    settings.setValue(SCHEMA_VERSION_KEY, CURRENT_SETTINGS_SCHEMA_VERSION)
    settings.setValue(DIFFERENCE_THRESHOLD_KEY, 100_000)
    settings.sync()

    loaded = repository.load()

    assert loaded.difference_threshold == MAX_DIFFERENCE_THRESHOLD
    persisted_threshold = settings.value(DIFFERENCE_THRESHOLD_KEY, type=int)
    assert persisted_threshold == MAX_DIFFERENCE_THRESHOLD
    persisted_schema = settings.value(SCHEMA_VERSION_KEY, type=int)
    assert persisted_schema == CURRENT_SETTINGS_SCHEMA_VERSION == 5
