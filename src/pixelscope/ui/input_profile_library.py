from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4
from weakref import WeakMethod

from pydantic import ValidationError
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pixelscope.io.raw_profile import RawProfile
from pixelscope.io.yuv_profile import YuvProfile

InputProfile = RawProfile | YuvProfile
_SETTINGS_KEY = "InputProfiles/library_v1"
_VERSION = 1
_RECENT_LIMIT = 12


def interpretation_key(profile: InputProfile) -> str:
    """Stable content key: neither the user-visible name nor a source path is identity."""
    kind = "raw" if isinstance(profile, RawProfile) else "yuv"
    payload = profile.dict(exclude={"name"})
    encoded = json.dumps(
        {"kind": kind, "interpretation": payload},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ProfileEntry:
    id: str
    label: str
    profile: InputProfile
    origin: str


class InputProfileLibrary:
    """Versioned, path-free local profile snapshots owned by the input dialogs.

    No source path, decoded image, document ID or generation is persisted.
    Unknown future versions are read-only; corrupt records are not trusted.
    """

    def __init__(self, settings: QSettings | None = None) -> None:
        self.settings = settings if settings is not None else QSettings()
        self.error: str | None = None
        self.read_only = False
        self._recent: list[dict[str, object]] = []
        self._favorites: list[dict[str, object]] = []
        self._load()

    @staticmethod
    def _kind(profile: InputProfile) -> str:
        return "raw" if isinstance(profile, RawProfile) else "yuv"

    @staticmethod
    def _decode(record: object) -> ProfileEntry | None:
        if not isinstance(record, dict):
            return None
        kind = record.get("kind")
        payload = record.get("profile")
        if kind not in ("raw", "yuv") or not isinstance(payload, dict):
            return None
        try:
            if kind == "raw":
                profile: InputProfile = RawProfile.parse_obj(payload)
            else:
                profile = YuvProfile.parse_obj(payload)
        except (ValidationError, ValueError, TypeError):
            return None
        uid = record.get("id", "")
        label = record.get("label", profile.name)
        origin = record.get("origin", "Saved")
        if not isinstance(uid, str) or not isinstance(label, str) or not isinstance(origin, str):
            return None
        if not label.strip():
            label = profile.name
        return ProfileEntry(uid, label, profile, origin)

    def _load(self) -> None:
        stored = self.settings.value(_SETTINGS_KEY)
        if stored is None:
            return
        if not isinstance(stored, str):
            self.error = "Input profile settings are not a JSON string."
            self.read_only = True
            return
        try:
            payload = json.loads(stored)
        except (TypeError, ValueError):
            self.error = "Input profile settings are malformed."
            self.read_only = True
            return
        if not isinstance(payload, dict) or payload.get("version") != _VERSION:
            self.error = "Input profile library has an unsupported schema version."
            self.read_only = True
            return
        recent = payload.get("recent")
        favorites = payload.get("favorites")
        if not isinstance(recent, list) or not isinstance(favorites, list):
            self.error = "Input profile library has invalid collections."
            self.read_only = True
            return
        for row in recent[:_RECENT_LIMIT]:
            entry = self._decode(row)
            if entry is not None:
                self._recent.append(self._encode(entry))
        for row in favorites:
            entry = self._decode(row)
            if entry is not None and entry.id:
                self._favorites.append(self._encode(entry))
        if len(self._recent) != min(len(recent), _RECENT_LIMIT) or len(self._favorites) != len(
            favorites
        ):
            self.error = "Some invalid saved input profiles were ignored."

    @staticmethod
    def _encode(entry: ProfileEntry) -> dict[str, object]:
        return {
            "id": entry.id,
            "kind": InputProfileLibrary._kind(entry.profile),
            "label": entry.label,
            "origin": entry.origin,
            "profile": entry.profile.dict(),
        }

    def _save(self) -> None:
        if self.read_only:
            raise ValueError(self.error or "Input profile library is read-only")
        self.settings.setValue(
            _SETTINGS_KEY,
            json.dumps(
                {"version": _VERSION, "recent": self._recent, "favorites": self._favorites},
                ensure_ascii=False,
                sort_keys=True,
            ),
        )

    def recent(self, kind: str) -> tuple[ProfileEntry, ...]:
        return tuple(
            entry
            for row in self._recent
            if (entry := self._decode(row)) is not None and self._kind(entry.profile) == kind
        )

    def favorites(self, kind: str) -> tuple[ProfileEntry, ...]:
        return tuple(
            entry
            for row in self._favorites
            if (entry := self._decode(row)) is not None
            and self._kind(entry.profile) == kind
        )

    def record_recent(self, profile: InputProfile, origin: str = "Manual") -> None:
        key = interpretation_key(profile)
        self._recent = [
            row
            for row in self._recent
            if (entry := self._decode(row)) is not None and interpretation_key(entry.profile) != key
        ]
        self._recent.insert(0, self._encode(ProfileEntry("", profile.name, profile, origin)))
        del self._recent[_RECENT_LIMIT:]
        self._save()

    def add_favorite(self, profile: InputProfile, label: str) -> str:
        if not label.strip():
            raise ValueError("Favorite name must not be empty")
        uid = uuid4().hex
        self._favorites.append(self._encode(ProfileEntry(uid, label.strip(), profile, "Favorite")))
        self._save()
        return uid

    def rename_favorite(self, uid: str, label: str) -> None:
        if not label.strip():
            raise ValueError("Favorite name must not be empty")
        for index, row in enumerate(self._favorites):
            entry = self._decode(row)
            if entry is not None and entry.id == uid:
                self._favorites[index] = self._encode(
                    ProfileEntry(uid, label.strip(), entry.profile, entry.origin)
                )
                self._save()
                return
        raise KeyError(uid)

    def remove_favorite(self, uid: str) -> None:
        found = [row for row in self._favorites if row.get("id") == uid]
        if not found:
            raise KeyError(uid)
        self._favorites = [row for row in self._favorites if row.get("id") != uid]
        self._save()

    def reset(self) -> None:
        """Explicit input-profile-only reset, including unsupported older schema."""
        self.settings.remove(_SETTINGS_KEY)
        self._recent.clear()
        self._favorites.clear()
        self.read_only = False
        self.error = None


class ProfileLibraryControls(QWidget):
    """Reusable dialog-local controls; never a source registration authority."""

    def __init__(
        self,
        kind: str,
        get_profile: Callable[[], InputProfile],
        apply_profile: Callable[[InputProfile], None],
        parent: QWidget | None = None,
        settings: QSettings | None = None,
    ) -> None:
        super().__init__(parent)
        self.kind = kind
        # WeakMethod avoids child-widget -> parent-dialog Python reference cycles.
        self._get_profile = WeakMethod(get_profile)
        self._apply_profile = WeakMethod(apply_profile)
        self.library = InputProfileLibrary(settings)
        self.origin = "Manual"

        self.recent_box = QComboBox()
        self.recent_box.setObjectName("inputProfileRecent")
        self.favorite_box = QComboBox()
        self.favorite_box.setObjectName("inputProfileFavorites")
        self.add_button = QPushButton("Add favorite")
        self.rename_button = QPushButton("Rename")
        self.remove_button = QPushButton("Remove")

        row = QHBoxLayout()
        row.addWidget(self.add_button)
        row.addWidget(self.rename_button)
        row.addWidget(self.remove_button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Recent input profiles"))
        layout.addWidget(self.recent_box)
        layout.addWidget(QLabel("Favorite input profiles"))
        layout.addWidget(self.favorite_box)
        layout.addLayout(row)

        self.recent_box.currentIndexChanged.connect(self._select_recent)  # type: ignore[attr-defined]
        self.favorite_box.currentIndexChanged.connect(self._select_favorite)  # type: ignore[attr-defined]
        self.add_button.clicked.connect(self._add_favorite)  # type: ignore[attr-defined]
        self.rename_button.clicked.connect(self._rename_favorite)  # type: ignore[attr-defined]
        self.remove_button.clicked.connect(self._remove_favorite)  # type: ignore[attr-defined]
        self.refresh()

    def refresh(self) -> None:
        for combo, entries, placeholder in (
            (self.recent_box, self.library.recent(self.kind), "Select recent…"),
            (self.favorite_box, self.library.favorites(self.kind), "Select favorite…"),
        ):
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(placeholder, "")
            for entry in entries:
                description = f"{entry.label} · {entry.profile.width}×{entry.profile.height}"
                combo.addItem(description, entry.id or interpretation_key(entry.profile))
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
        self.add_button.setEnabled(not self.library.read_only)
        self.rename_button.setEnabled(not self.library.read_only)
        self.remove_button.setEnabled(not self.library.read_only)
        if self.library.error is not None:
            self.setToolTip(self.library.error)

    def _select_recent(self, index: int) -> None:
        if index <= 0:
            return
        entries = self.library.recent(self.kind)
        if index <= len(entries):
            self.origin = "Recent"
            apply_profile = self._apply_profile()
            if apply_profile is not None:
                apply_profile(entries[index - 1].profile)

    def _select_favorite(self, index: int) -> None:
        if index <= 0:
            return
        entries = self.library.favorites(self.kind)
        if index <= len(entries):
            self.origin = "Favorite"
            apply_profile = self._apply_profile()
            if apply_profile is not None:
                apply_profile(entries[index - 1].profile)

    def _selected_favorite(self) -> ProfileEntry | None:
        index = self.favorite_box.currentIndex()
        entries = self.library.favorites(self.kind)
        return entries[index - 1] if 0 < index <= len(entries) else None

    def _add_favorite(self) -> None:
        try:
            get_profile = self._get_profile()
            if get_profile is None:
                return
            profile = get_profile()
        except (ValidationError, ValueError) as exc:
            QMessageBox.warning(self, "Invalid profile", str(exc))
            return
        label, ok = QInputDialog.getText(
            self, "Favorite profile", "Display name:", text=profile.name
        )
        if not ok or not label.strip():
            return
        try:
            self.library.add_favorite(profile, label)
        except ValueError as exc:
            QMessageBox.warning(self, "Cannot save favorite", str(exc))
        self.refresh()

    def _rename_favorite(self) -> None:
        entry = self._selected_favorite()
        if entry is None:
            return
        label, ok = QInputDialog.getText(self, "Rename favorite", "Display name:", text=entry.label)
        if ok and label.strip():
            self.library.rename_favorite(entry.id, label)
            self.refresh()

    def _remove_favorite(self) -> None:
        entry = self._selected_favorite()
        if entry is not None:
            self.library.remove_favorite(entry.id)
            self.refresh()
