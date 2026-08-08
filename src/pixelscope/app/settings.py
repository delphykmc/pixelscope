from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import QSettings

from pixelscope.core.performance_settings import (
    DEFAULT_DIFFERENCE_CACHE_BYTES,
    DEFAULT_SOURCE_RESIDENCY_BYTES,
    MIB,
    PerformanceSettings,
)

CURRENT_SETTINGS_SCHEMA_VERSION: Final = 4
DEFAULT_DIFFERENCE_CACHE_MIB: Final = DEFAULT_DIFFERENCE_CACHE_BYTES // MIB
MIN_DIFFERENCE_CACHE_MIB: Final = 64
MAX_DIFFERENCE_CACHE_MIB: Final = 8192
DEFAULT_SOURCE_RESIDENCY_MIB: Final = DEFAULT_SOURCE_RESIDENCY_BYTES // MIB
MIN_SOURCE_RESIDENCY_MIB: Final = 128
MAX_SOURCE_RESIDENCY_MIB: Final = 32768
DEFAULT_DIFFERENCE_THRESHOLD: Final = 10
MIN_DIFFERENCE_THRESHOLD: Final = 0
MAX_DIFFERENCE_THRESHOLD: Final = 2_147_483_647
DEFAULT_DIFFERENCE_GAIN: Final = 1
MIN_DIFFERENCE_GAIN: Final = 1
MAX_DIFFERENCE_GAIN: Final = 1000

SCHEMA_VERSION_KEY: Final = "settings/schema_version"
DONT_SHOW_RAW_JSON_PROFILES_KEY: Final = "settings/general/dont_show_raw_json_profiles"
REQUIRE_EXACT_RAW_FILE_SIZE_KEY: Final = "settings/general/require_exact_raw_file_size"
DEFAULT_OPEN_DIRECTORY_KEY: Final = "settings/files/default_open_directory"
DEFAULT_EXPORT_DIRECTORY_KEY: Final = "settings/files/default_export_directory"
DIFFERENCE_THRESHOLD_KEY: Final = "settings/analysis/difference_threshold"
DIFFERENCE_GAIN_KEY: Final = "settings/analysis/difference_gain"
DIFFERENCE_CACHE_MIB_KEY: Final = "settings/performance/difference_cache_mib"
SOURCE_RESIDENCY_MIB_KEY: Final = "settings/performance/source_residency_mib"
LEGACY_DONT_SHOW_RAW_JSON_PROFILES_KEY: Final = "raw/dont_show_json_profiles"

OWNED_SETTINGS_KEYS: Final = (
    SCHEMA_VERSION_KEY,
    DONT_SHOW_RAW_JSON_PROFILES_KEY,
    REQUIRE_EXACT_RAW_FILE_SIZE_KEY,
    DEFAULT_OPEN_DIRECTORY_KEY,
    DEFAULT_EXPORT_DIRECTORY_KEY,
    DIFFERENCE_THRESHOLD_KEY,
    DIFFERENCE_GAIN_KEY,
    DIFFERENCE_CACHE_MIB_KEY,
    SOURCE_RESIDENCY_MIB_KEY,
)

_TRUE_STRINGS = frozenset({"true", "1", "yes", "on"})
_FALSE_STRINGS = frozenset({"false", "0", "no", "off"})


@dataclass(frozen=True)
class ApplicationSettings:
    """Typed persisted preferences owned by the application-settings domain."""

    dont_show_raw_json_profiles: bool = False
    difference_cache_mib: int = DEFAULT_DIFFERENCE_CACHE_MIB
    default_open_directory: str = ""
    default_export_directory: str = ""
    require_exact_raw_file_size: bool = False
    difference_threshold: int = DEFAULT_DIFFERENCE_THRESHOLD
    difference_gain: int = DEFAULT_DIFFERENCE_GAIN
    source_residency_mib: int = DEFAULT_SOURCE_RESIDENCY_MIB

    def __post_init__(self) -> None:
        if not isinstance(self.dont_show_raw_json_profiles, bool):
            raise TypeError("dont_show_raw_json_profiles must be bool")
        if not isinstance(self.require_exact_raw_file_size, bool):
            raise TypeError("require_exact_raw_file_size must be bool")
        self._validate_int_range(
            "difference_cache_mib",
            self.difference_cache_mib,
            MIN_DIFFERENCE_CACHE_MIB,
            MAX_DIFFERENCE_CACHE_MIB,
        )
        self._validate_int_range(
            "source_residency_mib",
            self.source_residency_mib,
            MIN_SOURCE_RESIDENCY_MIB,
            MAX_SOURCE_RESIDENCY_MIB,
        )
        self._validate_int_range(
            "difference_threshold",
            self.difference_threshold,
            MIN_DIFFERENCE_THRESHOLD,
            MAX_DIFFERENCE_THRESHOLD,
        )
        self._validate_int_range(
            "difference_gain",
            self.difference_gain,
            MIN_DIFFERENCE_GAIN,
            MAX_DIFFERENCE_GAIN,
        )
        if not isinstance(self.default_open_directory, str):
            raise TypeError("default_open_directory must be str")
        if not isinstance(self.default_export_directory, str):
            raise TypeError("default_export_directory must be str")
        if "\x00" in self.default_open_directory or "\x00" in self.default_export_directory:
            raise ValueError("default directories must not contain NUL characters")

    @staticmethod
    def _validate_int_range(name: str, value: object, minimum: int, maximum: int) -> None:
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"{name} must be int")
        if not minimum <= value <= maximum:
            raise ValueError(f"{name} must be between {minimum} and {maximum}")

    def performance_settings(self) -> PerformanceSettings:
        """Build the immutable runtime snapshot consumed at application startup."""

        return PerformanceSettings(
            difference_cache_bytes=self.difference_cache_mib * MIB,
            source_residency_bytes=self.source_residency_mib * MIB,
        )


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

        if schema_version == 3:
            settings = self._load_schema_v3_values()
        elif schema_version == 2:
            settings = self._load_schema_v2_values()
        elif schema_version == 1:
            settings = self._load_schema_v1_values()
        else:
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
        dont_show, dont_show_valid = self._parse_bool(
            self._adapter.value(DONT_SHOW_RAW_JSON_PROFILES_KEY)
        )
        exact_size, exact_size_valid = self._parse_bool(
            self._adapter.value(REQUIRE_EXACT_RAW_FILE_SIZE_KEY)
        )
        cache_mib, cache_valid = self._parse_int_range(
            self._adapter.value(DIFFERENCE_CACHE_MIB_KEY),
            DEFAULT_DIFFERENCE_CACHE_MIB,
            MIN_DIFFERENCE_CACHE_MIB,
            MAX_DIFFERENCE_CACHE_MIB,
        )
        source_mib, source_valid = self._parse_int_range(
            self._adapter.value(SOURCE_RESIDENCY_MIB_KEY),
            DEFAULT_SOURCE_RESIDENCY_MIB,
            MIN_SOURCE_RESIDENCY_MIB,
            MAX_SOURCE_RESIDENCY_MIB,
        )
        threshold, threshold_valid = self._parse_int_range(
            self._adapter.value(DIFFERENCE_THRESHOLD_KEY),
            DEFAULT_DIFFERENCE_THRESHOLD,
            MIN_DIFFERENCE_THRESHOLD,
            MAX_DIFFERENCE_THRESHOLD,
        )
        gain, gain_valid = self._parse_int_range(
            self._adapter.value(DIFFERENCE_GAIN_KEY),
            DEFAULT_DIFFERENCE_GAIN,
            MIN_DIFFERENCE_GAIN,
            MAX_DIFFERENCE_GAIN,
        )
        open_directory, open_valid = self._parse_directory(
            self._adapter.value(DEFAULT_OPEN_DIRECTORY_KEY)
        )
        export_directory, export_valid = self._parse_directory(
            self._adapter.value(DEFAULT_EXPORT_DIRECTORY_KEY)
        )
        settings = ApplicationSettings(
            dont_show_raw_json_profiles=dont_show,
            difference_cache_mib=cache_mib,
            source_residency_mib=source_mib,
            default_open_directory=open_directory,
            default_export_directory=export_directory,
            require_exact_raw_file_size=exact_size,
            difference_threshold=threshold,
            difference_gain=gain,
        )
        valid = (
            dont_show_valid
            and exact_size_valid
            and cache_valid
            and source_valid
            and threshold_valid
            and gain_valid
            and open_valid
            and export_valid
        )
        return settings, not valid

    def _load_schema_v3_values(self) -> ApplicationSettings:
        """Preserve every v3 value while adding the decoded-source default."""

        dont_show, _ = self._parse_bool(self._adapter.value(DONT_SHOW_RAW_JSON_PROFILES_KEY))
        exact_size, _ = self._parse_bool(self._adapter.value(REQUIRE_EXACT_RAW_FILE_SIZE_KEY))
        cache_mib, _ = self._parse_int_range(
            self._adapter.value(DIFFERENCE_CACHE_MIB_KEY),
            DEFAULT_DIFFERENCE_CACHE_MIB,
            MIN_DIFFERENCE_CACHE_MIB,
            MAX_DIFFERENCE_CACHE_MIB,
        )
        threshold, _ = self._parse_int_range(
            self._adapter.value(DIFFERENCE_THRESHOLD_KEY),
            DEFAULT_DIFFERENCE_THRESHOLD,
            MIN_DIFFERENCE_THRESHOLD,
            MAX_DIFFERENCE_THRESHOLD,
        )
        gain, _ = self._parse_int_range(
            self._adapter.value(DIFFERENCE_GAIN_KEY),
            DEFAULT_DIFFERENCE_GAIN,
            MIN_DIFFERENCE_GAIN,
            MAX_DIFFERENCE_GAIN,
        )
        open_directory, _ = self._parse_directory(self._adapter.value(DEFAULT_OPEN_DIRECTORY_KEY))
        export_directory, _ = self._parse_directory(
            self._adapter.value(DEFAULT_EXPORT_DIRECTORY_KEY)
        )
        return ApplicationSettings(
            dont_show_raw_json_profiles=dont_show,
            difference_cache_mib=cache_mib,
            default_open_directory=open_directory,
            default_export_directory=export_directory,
            require_exact_raw_file_size=exact_size,
            difference_threshold=threshold,
            difference_gain=gain,
        )

    def _load_schema_v2_values(self) -> ApplicationSettings:
        dont_show, _ = self._parse_bool(self._adapter.value(DONT_SHOW_RAW_JSON_PROFILES_KEY))
        cache_mib, _ = self._parse_int_range(
            self._adapter.value(DIFFERENCE_CACHE_MIB_KEY),
            DEFAULT_DIFFERENCE_CACHE_MIB,
            MIN_DIFFERENCE_CACHE_MIB,
            MAX_DIFFERENCE_CACHE_MIB,
        )
        open_directory, _ = self._parse_directory(self._adapter.value(DEFAULT_OPEN_DIRECTORY_KEY))
        export_directory, _ = self._parse_directory(
            self._adapter.value(DEFAULT_EXPORT_DIRECTORY_KEY)
        )
        return ApplicationSettings(
            dont_show_raw_json_profiles=dont_show,
            difference_cache_mib=cache_mib,
            default_open_directory=open_directory,
            default_export_directory=export_directory,
        )

    def _load_schema_v1_values(self) -> ApplicationSettings:
        dont_show, _ = self._parse_bool(self._adapter.value(DONT_SHOW_RAW_JSON_PROFILES_KEY))
        cache_mib, _ = self._parse_int_range(
            self._adapter.value(DIFFERENCE_CACHE_MIB_KEY),
            DEFAULT_DIFFERENCE_CACHE_MIB,
            MIN_DIFFERENCE_CACHE_MIB,
            MAX_DIFFERENCE_CACHE_MIB,
        )
        return ApplicationSettings(
            dont_show_raw_json_profiles=dont_show,
            difference_cache_mib=cache_mib,
        )

    def _load_legacy_or_unversioned(self) -> ApplicationSettings:
        raw_bool = (
            self._adapter.value(DONT_SHOW_RAW_JSON_PROFILES_KEY)
            if self._adapter.contains(DONT_SHOW_RAW_JSON_PROFILES_KEY)
            else self._adapter.value(LEGACY_DONT_SHOW_RAW_JSON_PROFILES_KEY)
        )
        dont_show, _ = self._parse_bool(raw_bool)
        exact_size, _ = self._parse_bool(self._adapter.value(REQUIRE_EXACT_RAW_FILE_SIZE_KEY))
        cache_mib, _ = self._parse_int_range(
            self._adapter.value(DIFFERENCE_CACHE_MIB_KEY),
            DEFAULT_DIFFERENCE_CACHE_MIB,
            MIN_DIFFERENCE_CACHE_MIB,
            MAX_DIFFERENCE_CACHE_MIB,
        )
        threshold, _ = self._parse_int_range(
            self._adapter.value(DIFFERENCE_THRESHOLD_KEY),
            DEFAULT_DIFFERENCE_THRESHOLD,
            MIN_DIFFERENCE_THRESHOLD,
            MAX_DIFFERENCE_THRESHOLD,
        )
        gain, _ = self._parse_int_range(
            self._adapter.value(DIFFERENCE_GAIN_KEY),
            DEFAULT_DIFFERENCE_GAIN,
            MIN_DIFFERENCE_GAIN,
            MAX_DIFFERENCE_GAIN,
        )
        open_directory, _ = self._parse_directory(self._adapter.value(DEFAULT_OPEN_DIRECTORY_KEY))
        export_directory, _ = self._parse_directory(
            self._adapter.value(DEFAULT_EXPORT_DIRECTORY_KEY)
        )
        return ApplicationSettings(
            dont_show_raw_json_profiles=dont_show,
            difference_cache_mib=cache_mib,
            default_open_directory=open_directory,
            default_export_directory=export_directory,
            require_exact_raw_file_size=exact_size,
            difference_threshold=threshold,
            difference_gain=gain,
        )

    def _write_current(self, settings: ApplicationSettings) -> None:
        self._adapter.set_value(SCHEMA_VERSION_KEY, CURRENT_SETTINGS_SCHEMA_VERSION)
        self._adapter.set_value(
            DONT_SHOW_RAW_JSON_PROFILES_KEY,
            settings.dont_show_raw_json_profiles,
        )
        self._adapter.set_value(
            REQUIRE_EXACT_RAW_FILE_SIZE_KEY,
            settings.require_exact_raw_file_size,
        )
        self._adapter.set_value(DEFAULT_OPEN_DIRECTORY_KEY, settings.default_open_directory)
        self._adapter.set_value(DEFAULT_EXPORT_DIRECTORY_KEY, settings.default_export_directory)
        self._adapter.set_value(DIFFERENCE_THRESHOLD_KEY, settings.difference_threshold)
        self._adapter.set_value(DIFFERENCE_GAIN_KEY, settings.difference_gain)
        self._adapter.set_value(DIFFERENCE_CACHE_MIB_KEY, settings.difference_cache_mib)
        self._adapter.set_value(SOURCE_RESIDENCY_MIB_KEY, settings.source_residency_mib)
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
    def _parse_int_range(
        value: object,
        default: int,
        minimum: int,
        maximum: int,
    ) -> tuple[int, bool]:
        if value is None or isinstance(value, bool):
            return default, False
        try:
            parsed = int(str(value).strip())
        except (TypeError, ValueError):
            return default, False
        if not minimum <= parsed <= maximum:
            return default, False
        return parsed, True

    @staticmethod
    def _parse_directory(value: object) -> tuple[str, bool]:
        if value is None:
            return "", False
        if not isinstance(value, str):
            return "", False
        return value.strip(), True
