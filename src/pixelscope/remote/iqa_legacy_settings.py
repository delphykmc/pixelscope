"""Legacy public P5 settings ownership retained outside Base for historical tooling."""

from __future__ import annotations

from PySide6.QtCore import QSettings

from pixelscope.remote.iqa_settings import (
    RemoteIqaSettings,
    parse_storage_roots,
    serialize_storage_roots,
)

SERVER_URL_KEY = "settings/remote_iqa/server_base_url"
STORAGE_ROOTS_KEY = "settings/remote_iqa/storage_roots_json"
STAGING_ROOT_ID_KEY = "settings/remote_iqa/staging_root_id"
LEGACY_REMOTE_IQA_KEYS = (SERVER_URL_KEY, STORAGE_ROOTS_KEY, STAGING_ROOT_ID_KEY)


class LegacyRemoteIqaSettingsRepository:
    """Read/write the retired public P5 configuration without Base ownership."""

    def __init__(self, settings: QSettings | None = None) -> None:
        self._settings = settings if settings is not None else QSettings()

    def load(self) -> RemoteIqaSettings:
        raw_url = self._settings.value(SERVER_URL_KEY, "")
        url = raw_url.strip() if isinstance(raw_url, str) else ""
        roots, _valid = parse_storage_roots(self._settings.value(STORAGE_ROOTS_KEY, ""))
        raw_staging = self._settings.value(STAGING_ROOT_ID_KEY, "")
        staging = raw_staging.strip() if isinstance(raw_staging, str) else ""
        try:
            return RemoteIqaSettings(
                server_base_url=url,
                storage_roots=roots,
                staging_root_id=staging or None,
            )
        except (TypeError, ValueError):
            return RemoteIqaSettings()

    def save(self, settings: RemoteIqaSettings) -> RemoteIqaSettings:
        self._settings.setValue(SERVER_URL_KEY, settings.server_base_url)
        self._settings.setValue(STORAGE_ROOTS_KEY, serialize_storage_roots(settings.storage_roots))
        self._settings.setValue(STAGING_ROOT_ID_KEY, settings.staging_root_id or "")
        self._settings.sync()
        return settings

    def reset(self) -> RemoteIqaSettings:
        for key in LEGACY_REMOTE_IQA_KEYS:
            self._settings.remove(key)
        self._settings.sync()
        return RemoteIqaSettings()


def load_legacy_remote_iqa_settings(owner: object) -> RemoteIqaSettings:
    """Load historical P5 settings from the explicit extension-owned repository."""

    repository = getattr(owner, "remote_iqa_settings_repository", None)
    if isinstance(repository, LegacyRemoteIqaSettingsRepository):
        return repository.load()
    return LegacyRemoteIqaSettingsRepository().load()
