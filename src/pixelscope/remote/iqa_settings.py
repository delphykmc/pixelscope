"""Typed machine-local settings for Remote IQA submission and shared storage."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import PureWindowsPath
from urllib.parse import urlsplit

MAX_STORAGE_ROOTS = 32
MAX_STORAGE_ROOT_ID_LENGTH = 64
MAX_CLIENT_PATH_LENGTH = 2048
MAX_SERVER_URL_LENGTH = 2048
_STORAGE_ROOT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


@dataclass(frozen=True)
class RemoteIqaStorageRoot:
    """One portable logical root mapped to this machine's Windows/UNC path."""

    storage_root_id: str
    client_path: str

    def __post_init__(self) -> None:
        root_id = self.storage_root_id.strip()
        if (
            root_id != self.storage_root_id
            or _STORAGE_ROOT_ID_RE.fullmatch(root_id) is None
        ):
            raise ValueError(
                "storage_root_id must be a portable 1-64 character identifier "
                "using letters, digits, '.', '_' or '-'"
            )
        path = self.client_path.strip()
        if path != self.client_path or not path or len(path) > MAX_CLIENT_PATH_LENGTH:
            raise ValueError(
                "client_path must be a non-empty bounded absolute Windows/UNC path"
            )
        if "\x00" in path:
            raise ValueError("client_path must not contain NUL")
        parsed = PureWindowsPath(path)
        if not parsed.is_absolute() or not parsed.drive:
            raise ValueError("client_path must be an absolute drive or UNC path")


@dataclass(frozen=True)
class RemoteIqaSettings:
    """Remote-IQA configuration owned by ApplicationSettings/SettingsRepository."""

    server_base_url: str = ""
    storage_roots: tuple[RemoteIqaStorageRoot, ...] = ()
    staging_root_id: str | None = None

    def __post_init__(self) -> None:
        url = self.server_base_url.strip()
        if url != self.server_base_url or len(url) > MAX_SERVER_URL_LENGTH:
            raise ValueError("server_base_url must be trimmed and bounded")
        if url:
            parsed = urlsplit(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("server_base_url must be an absolute HTTP(S) URL")
            if parsed.username is not None or parsed.password is not None:
                raise ValueError("credentials must not be stored in server_base_url")
            if parsed.query or parsed.fragment:
                raise ValueError("server_base_url must not contain query or fragment")
        if len(self.storage_roots) > MAX_STORAGE_ROOTS:
            raise ValueError(
                f"at most {MAX_STORAGE_ROOTS} storage roots may be configured"
            )
        ids = [root.storage_root_id for root in self.storage_roots]
        if len(set(ids)) != len(ids):
            raise ValueError("storage_root_id values must be unique")
        if self.staging_root_id is not None and self.staging_root_id not in ids:
            raise ValueError("staging_root_id must reference a configured storage root")

    @property
    def submission_configured(self) -> bool:
        return bool(self.server_base_url and self.storage_roots)

    def root(self, storage_root_id: str) -> RemoteIqaStorageRoot | None:
        return next(
            (
                item
                for item in self.storage_roots
                if item.storage_root_id == storage_root_id
            ),
            None,
        )


def serialize_storage_roots(roots: tuple[RemoteIqaStorageRoot, ...]) -> str:
    """Return deterministic JSON suitable for one QSettings value."""

    return json.dumps(
        [
            {"storage_root_id": item.storage_root_id, "client_path": item.client_path}
            for item in roots
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def parse_storage_roots(
    value: object,
) -> tuple[tuple[RemoteIqaStorageRoot, ...], bool]:
    """Parse a QSettings value, returning defaults plus validity on corruption."""

    if value in (None, ""):
        return (), True
    if not isinstance(value, str):
        return (), False
    try:
        raw = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return (), False
    if not isinstance(raw, list) or len(raw) > MAX_STORAGE_ROOTS:
        return (), False
    roots: list[RemoteIqaStorageRoot] = []
    try:
        for item in raw:
            if not isinstance(item, dict) or set(item) != {
                "storage_root_id",
                "client_path",
            }:
                return (), False
            root_id = item["storage_root_id"]
            client_path = item["client_path"]
            if not isinstance(root_id, str) or not isinstance(client_path, str):
                return (), False
            roots.append(RemoteIqaStorageRoot(root_id, client_path))
        settings = RemoteIqaSettings(storage_roots=tuple(roots))
    except (TypeError, ValueError):
        return (), False
    return settings.storage_roots, True
