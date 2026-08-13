from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QSettings

from pixelscope.app.recent_entries import RecentEntriesRepository
from pixelscope.app.settings import QSettingsAdapter
from pixelscope.core.recent_entries import RecentEntryKind, merge_recent_paths


class _Storage:
    def __init__(self) -> None:
        self.values: dict[str, object] = {}
        self.sync_count = 0

    def value(self, key: str, default: object = None) -> object:
        return self.values.get(key, default)

    def set_value(self, key: str, value: object) -> None:
        self.values[key] = value

    def remove(self, key: str) -> None:
        self.values.pop(key, None)

    def sync(self) -> None:
        self.sync_count += 1


class _StaleReadStorage(_Storage):
    def __init__(self) -> None:
        super().__init__()
        self.persisted: dict[str, object] = {}

    def set_value(self, key: str, value: object) -> None:
        self.persisted[key] = value

    def remove(self, key: str) -> None:
        self.persisted.pop(key, None)


def test_merge_recent_paths_preserves_batch_order_deduplicates_and_bounds(tmp_path: Path) -> None:
    existing = tuple((tmp_path / f"old-{index}.png").resolve() for index in range(5))
    opened = [existing[2], tmp_path / "new-a.png", tmp_path / "new-b.png"]

    assert merge_recent_paths(existing, opened, limit=4) == (
        existing[2],
        (tmp_path / "new-a.png").resolve(),
        (tmp_path / "new-b.png").resolve(),
        existing[0],
    )


def test_repository_keeps_typed_histories_independent(tmp_path: Path) -> None:
    storage = _Storage()
    repository = RecentEntriesRepository(storage, limit=3)
    images = [tmp_path / "a.png", tmp_path / "b.png", tmp_path / "c.png"]
    folder = tmp_path / "folder"
    comparison_set = tmp_path / "review.pixelscope"

    repository.record(RecentEntryKind.IMAGE, images)
    repository.record(RecentEntryKind.FOLDER, [folder])
    repository.record(RecentEntryKind.COMPARISON_SET, [comparison_set])
    repository.record(RecentEntryKind.IMAGE, [images[1]])

    assert repository.load(RecentEntryKind.IMAGE) == (
        images[1].resolve(),
        images[0].resolve(),
        images[2].resolve(),
    )
    assert repository.load(RecentEntryKind.FOLDER) == (folder.resolve(),)
    assert repository.load(RecentEntryKind.COMPARISON_SET) == (comparison_set.resolve(),)


def test_repository_uses_json_and_runtime_cache_for_qsettings_compatibility(tmp_path: Path) -> None:
    storage = _StaleReadStorage()
    repository = RecentEntriesRepository(storage)
    image = (tmp_path / "image.png").resolve()

    repository.record(RecentEntryKind.IMAGE, [image])

    raw = storage.persisted["recent/images"]
    assert isinstance(raw, str)
    assert json.loads(raw) == [str(image)]
    assert storage.value("recent/images", []) == []
    assert repository.load(RecentEntryKind.IMAGE) == (image,)


def test_repository_ignores_invalid_persisted_entries_without_rewriting(tmp_path: Path) -> None:
    storage = _Storage()
    repository = RecentEntriesRepository(storage)
    first = (tmp_path / "first.png").resolve()
    second = (tmp_path / "second.png").resolve()
    storage.values["recent/images"] = [str(first), "relative.png", "", 42, str(second)]

    assert repository.load(RecentEntryKind.IMAGE) == (first, second)
    assert storage.sync_count == 0


def test_draft_session_key_migrates_to_comparison_set_key_on_write(tmp_path: Path) -> None:
    storage = _Storage()
    old = (tmp_path / "old.pixelscope").resolve()
    new = (tmp_path / "new.pixelscope").resolve()
    storage.values["recent/sessions"] = json.dumps([str(old)])
    repository = RecentEntriesRepository(storage)

    assert repository.load(RecentEntryKind.COMPARISON_SET) == (old,)

    repository.record(RecentEntryKind.COMPARISON_SET, [new])

    assert "recent/sessions" not in storage.values
    assert json.loads(str(storage.values["recent/comparison_sets"])) == [str(new), str(old)]


def test_typed_clear_does_not_touch_application_settings(tmp_path: Path) -> None:
    storage = _Storage()
    storage.values["settings/schema_version"] = 5
    repository = RecentEntriesRepository(storage)
    image = tmp_path / "image.png"
    folder = tmp_path / "folder"

    repository.record(RecentEntryKind.IMAGE, [image])
    repository.record(RecentEntryKind.FOLDER, [folder])
    repository.clear(RecentEntryKind.IMAGE)

    assert repository.load(RecentEntryKind.IMAGE) == ()
    assert repository.load(RecentEntryKind.FOLDER) == (folder.resolve(),)
    assert storage.values["settings/schema_version"] == 5


def test_real_qsettings_history_survives_reconstruction_and_clear(tmp_path: Path) -> None:
    ini_path = tmp_path / "pixelscope-recent.ini"
    settings = QSettings(str(ini_path), QSettings.Format.IniFormat)
    settings.clear()
    settings.setValue("settings/schema_version", 5)
    settings.sync()

    repository = RecentEntriesRepository(QSettingsAdapter(settings), limit=3)
    images = [tmp_path / f"image-{index}.png" for index in range(4)]
    folder = tmp_path / "dataset"
    comparison_set = tmp_path / "review.pixelscope"
    repository.record(RecentEntryKind.IMAGE, images)
    repository.record(RecentEntryKind.IMAGE, [images[1]])
    repository.record(RecentEntryKind.FOLDER, [folder])
    repository.record(RecentEntryKind.COMPARISON_SET, [comparison_set])

    reconstructed = RecentEntriesRepository(
        QSettingsAdapter(QSettings(str(ini_path), QSettings.Format.IniFormat)),
        limit=3,
    )
    assert reconstructed.load(RecentEntryKind.IMAGE) == (
        images[1].resolve(),
        images[0].resolve(),
        images[2].resolve(),
    )
    assert reconstructed.load(RecentEntryKind.FOLDER) == (folder.resolve(),)
    assert reconstructed.load(RecentEntryKind.COMPARISON_SET) == (comparison_set.resolve(),)

    reconstructed.clear()
    after_clear_settings = QSettings(str(ini_path), QSettings.Format.IniFormat)
    after_clear = RecentEntriesRepository(QSettingsAdapter(after_clear_settings), limit=3)
    assert all(after_clear.load(kind) == () for kind in RecentEntryKind)
    assert after_clear_settings.value("settings/schema_version") == 5
