from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import QSettings

from pixelscope.core.performance_settings import (
    DEFAULT_DIFFERENCE_CACHE_BYTES,
    MIB,
    PerformanceSettings,
)

CURRENT_SETTINGS_SCHEMA_VERSION: Final = 1
DEFAULT_DIFFERENCE_CACHE_MIB: Final = DEFAULT_DIFFERENCE_CACHE_BYTES // MIB
MIN_DIFFERENCE_CACHE_MIB: Final = 64
MAX_DIFFERENCE_CACHE_MIB: Final = 8192

SCHEMA_VERSION_KEY: Final = "settings/schema_version"
DONT_SHOW_RAW_JSON_PROFILES_KEY: Final = "settings/general/dont_show_raw_json_profiles"
DIFFERENCE_CACHE_MIB_KEY: Final = "settings/performance/difference_cache_mib"
LEGACY_DONT_SHOW_RAW_JSON_PROFILES_KEY: Final = "raw/dont_show_json_profiles"

OWNED_SETTINGS_KEYS: Final = (
    SCHEMA_VERSION_KEY,
    DONT_SHOW_RAW_JSON_PROFILES_KEY,
    DIFFERENCE_CACHE_MIB_KEY,
)

_TRUE_STRINGS = frozenset({"true", "1", "yes", "on"})
_FALSE_STRINGS = frozenset({"false", "0", "no", "off"})


@dataclass(frozen=True)
class ApplicationSettings:
    """Typed persisted preferences owned by the application-settings domain."""

    dont_show_raw_json_profiles: bool = False
    difference_cache_mib: int = DEFAULT_DIFFERENCE_CACHE_MIB

    def __post_init__(self) -> None:
        if not isinstance(self.dont_show_raw_json_profiles, bool):
            raise TypeError("dont_show_raw_json_profiles must be bool")
        if not isinstance(self.difference_cache_mib, int) or isinstance(
            self.difference_cache_mib, bool
        ):
            raise TypeError("difference_cache_mib must be int")
        if not MIN_DIFFERENCE_CACHE_MIB <= self.difference_cache_mib <= MAX_DIFFERENCE_CACHE_MIB:
            raise ValueError(
                "difference cache budget must be between "
                f"{MIN_DIFFERENCE_CACHE_MIB} and {MAX_DIFFERENCE_CACHE_MIB} MiB"
            )

    def performance_settings(self) -> PerformanceSettings:
        """Build the immutable runtime snapshot consumed at application startup."""

        return PerformanceSettings(difference_cache_bytes=self.difference_cache_mib * MIB)


class UnsupportedSettingsSchemaError(RuntimeError):
    """Raised when a write would overwrite a newer settings schema."""


class QSettingsAdapter:
    """Narrow persistence adapter; domain code does not depend on raw key usage."""

    def __init__(self, settings: QSettings | None = None) -> None:
        self._settings = settings if settings is not None else QSettings()

    def value(self, key: str, default: object = None) -> object:
        return self._settings.value(key, default)

    def contains(self, key: str) -> bool:
        return self._settings.contains(key)

    def set_value(self, key: str, value: object) -> None:
        self._settings.setValue(key, value)

    def remove(self, key: str) -> None:
        self._settings.remove(key)

    def sync(self) -> None:
        self._settings.sync()


class SettingsRepository:
    """Load, validate, migrate, save, and reset application preferences."""

    def __init__(self, adapter: QSettingsAdapter | None = None) -> None:
        self._adapter = adapter if adapter is not None else QSettingsAdapter()
        self._future_schema_version: int | None = None

    @property
    def future_schema_version(self) -> int | None:
        return self._future_schema_version

    @property
    def is_read_only_compatibility_mode(self) -> bool:
        return self._future_schema_version is not None

    def load(self) -> ApplicationSettings:
        schema_version = self._parse_schema_version(self._adapter.value(SCHEMA_VERSION_KEY))
        if schema_version is not None and schema_version > CURRENT_SETTINGS_SCHEMA_VERSION:
            self._future_schema_version = schema_version
            return ApplicationSettings()

        self._future_schema_version = None
        if schema_version == CURRENT_SETTINGS_SCHEMA_VERSION:
            settings, normalized = self._load_current_values()
            if normalized:
                self._write_current(settings)
            return settings

        settings = self._load_legacy_or_unversioned()
        self._write_current(settings)
        self._adapter.remove(LEGACY_DONT_SHOW_RAW_JSON_PROFILES_KEY)
        self._adapter.sync()
        return settings

    def save(self, settings: ApplicationSettings) -> ApplicationSettings:
        self._guard_writable_schema()
        self._write_current(settings)
        self._adapter.remove(LEGACY_DONT_SHOW_RAW_JSON_PROFILES_KEY)
        self._adapter.sync()
        return settings

    def reset(self) -> ApplicationSettings:
        self._guard_writable_schema()
        for key in OWNED_SETTINGS_KEYS:
            self._adapter.remove(key)
        self._adapter.remove(LEGACY_DONT_SHOW_RAW_JSON_PROFILES_KEY)
        defaults = ApplicationSettings()
        self._write_current(defaults)
        self._adapter.sync()
        return defaults

    def _load_current_values(self) -> tuple[ApplicationSettings, bool]:
        raw_bool = self._adapter.value(DONT_SHOW_RAW_JSON_PROFILES_KEY)
        dont_show, bool_valid = self._parse_bool(raw_bool)
        raw_cache = self._adapter.value(DIFFERENCE_CACHE_MIB_KEY)
        cache_mib, cache_valid = self._parse_cache_mib(raw_cache)
        settings = ApplicationSettings(
            dont_show_raw_json_profiles=dont_show,
            difference_cache_mib=cache_mib,
        )
        return settings, not (bool_valid and cache_valid)

    def _load_legacy_or_unversioned(self) -> ApplicationSettings:
        raw_bool = (
            self._adapter.value(DONT_SHOW_RAW_JSON_PROFILES_KEY)
            if self._adapter.contains(DONT_SHOW_RAW_JSON_PROFILES_KEY)
            else self._adapter.value(LEGACY_DONT_SHOW_RAW_JSON_PROFILES_KEY)
        )
        dont_show, _ = self._parse_bool(raw_bool)
        cache_mib, _ = self._parse_cache_mib(self._adapter.value(DIFFERENCE_CACHE_MIB_KEY))
        return ApplicationSettings(
            dont_show_raw_json_profiles=dont_show,
            difference_cache_mib=cache_mib,
        )

    def _write_current(self, settings: ApplicationSettings) -> None:
        self._adapter.set_value(SCHEMA_VERSION_KEY, CURRENT_SETTINGS_SCHEMA_VERSION)
        self._adapter.set_value(
            DONT_SHOW_RAW_JSON_PROFILES_KEY,
            settings.dont_show_raw_json_profiles,
        )
        self._adapter.set_value(DIFFERENCE_CACHE_MIB_KEY, settings.difference_cache_mib)
        self._adapter.sync()

    def _guard_writable_schema(self) -> None:
        schema_version = self._parse_schema_version(self._adapter.value(SCHEMA_VERSION_KEY))
        if schema_version is not None and schema_version > CURRENT_SETTINGS_SCHEMA_VERSION:
            self._future_schema_version = schema_version
            raise UnsupportedSettingsSchemaError(
                f"settings schema {schema_version} is newer than supported schema "
                f"{CURRENT_SETTINGS_SCHEMA_VERSION}"
            )
        self._future_schema_version = None

    @staticmethod
    def _parse_schema_version(value: object) -> int | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            parsed = int(str(value).strip())
        except (TypeError, ValueError):
            return None
        return parsed if parsed >= 0 else None

    @staticmethod
    def _parse_bool(value: object) -> tuple[bool, bool]:
        if isinstance(value, bool):
            return value, True
        if value is None:
            return False, False
        normalized = str(value).strip().casefold()
        if normalized in _TRUE_STRINGS:
            return True, True
        if normalized in _FALSE_STRINGS:
            return False, True
        return False, False

    @staticmethod
    def _parse_cache_mib(value: object) -> tuple[int, bool]:
        if value is None:
            return DEFAULT_DIFFERENCE_CACHE_MIB, False
        if isinstance(value, bool):
            return DEFAULT_DIFFERENCE_CACHE_MIB, False
        try:
            parsed = int(str(value).strip())
        except (TypeError, ValueError):
            return DEFAULT_DIFFERENCE_CACHE_MIB, False
        if not MIN_DIFFERENCE_CACHE_MIB <= parsed <= MAX_DIFFERENCE_CACHE_MIB:
            return DEFAULT_DIFFERENCE_CACHE_MIB, False
        return parsed, True
