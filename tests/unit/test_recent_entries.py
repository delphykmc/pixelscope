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
    """Simulate a backend whose immediate read does not observe the latest write."""

    def __init__(self) -> None:
        super().__init__()
        self.persisted: dict[str, object] = {}

    def value(self, key: str, default: object = None) -> object:
        return self.values.get(key, default)

    def set_value(self, key: str, value: object) -> None:
        self.persisted[key] = value

    def remove(self, key: str) -> None:
        self.persisted.pop(key, None)


def test_merge_recent_paths_preserves_batch_order_deduplicates_and_bounds(tmp_path: Path) -> None:
    existing = tuple((tmp_path / f"old-{index}.png").resolve() for index in range(5))
    opened = [existing[2], tmp_path / "new-a.png", tmp_path / "new-b.png"]

    merged = merge_recent_paths(existing, opened, limit=4)

    assert merged == (
        existing[2],
        (tmp_path / "new-a.png").resolve(),
        (tmp_path / "new-b.png").resolve(),
        existing[0],
    )


def test_repository_keeps_kinds_independent_and_mru_order(tmp_path: Path) -> None:
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


def test_repository_persists_backend_independent_json_strings(tmp_path: Path) -> None:
    storage = _Storage()
    repository = RecentEntriesRepository(storage)
    paths = [tmp_path / "a.png", tmp_path / "b.png"]

    repository.record(RecentEntryKind.IMAGE, paths)

    raw = storage.values["recent/images"]
    assert isinstance(raw, str)
    assert json.loads(raw) == [str(path.resolve()) for path in paths]
    assert repository.load(RecentEntryKind.IMAGE) == tuple(path.resolve() for path in paths)


def test_repository_runtime_cache_does_not_depend_on_immediate_backend_readback(
    tmp_path: Path,
) -> None:
    storage = _StaleReadStorage()
    repository = RecentEntriesRepository(storage)
    image = (tmp_path / "image.png").resolve()

    repository.record(RecentEntryKind.IMAGE, [image])

    assert "recent/images" in storage.persisted
    assert storage.value("recent/images", []) == []
    assert repository.load(RecentEntryKind.IMAGE) == (image,)


def test_repository_reads_pre_json_draft_values(tmp_path: Path) -> None:
    storage = _Storage()
    repository = RecentEntriesRepository(storage)
    first = (tmp_path / "first.png").resolve()
    second = (tmp_path / "second.png").resolve()

    storage.values["recent/images"] = [str(first), str(second)]
    storage.values["recent/folders"] = str((tmp_path / "folder").resolve())

    assert repository.load(RecentEntryKind.IMAGE) == (first, second)
    assert repository.load(RecentEntryKind.FOLDER) == ((tmp_path / "folder").resolve(),)


def test_repository_ignores_invalid_persisted_values_without_touching_storage(
    tmp_path: Path,
) -> None:
    storage = _Storage()
    repository = RecentEntriesRepository(storage)
    valid = (tmp_path / "valid.png").resolve()
    storage.values["recent/images"] = [
        str(valid),
        "relative.png",
        "",
        42,
        str(valid),
    ]

    assert repository.load(RecentEntryKind.IMAGE) == (valid,)
    assert storage.sync_count == 0


def test_remove_and_clear_only_mutate_history_namespace(tmp_path: Path) -> None:
    storage = _Storage()
    storage.values["settings/schema_version"] = 5
    repository = RecentEntriesRepository(storage)
    image = tmp_path / "image.png"
    folder = tmp_path / "folder"

    repository.record(RecentEntryKind.IMAGE, [image])
    repository.record(RecentEntryKind.FOLDER, [folder])
    repository.remove(RecentEntryKind.IMAGE, image)

    assert repository.load(RecentEntryKind.IMAGE) == ()
    assert repository.load(RecentEntryKind.FOLDER) == (folder.resolve(),)
    assert storage.values["settings/schema_version"] == 5

    repository.clear()

    assert repository.load(RecentEntryKind.FOLDER) == ()
    assert storage.values["settings/schema_version"] == 5


def test_real_qsettings_history_survives_reconstruction_and_clear(
    tmp_path: Path,
) -> None:
    ini_path = tmp_path / "pixelscope-recent.ini"
    settings = QSettings(str(ini_path), QSettings.Format.IniFormat)
    settings.clear()
    settings.setValue("settings/schema_version", 5)
    settings.setValue("settings/files/default_open_directory", str(tmp_path / "owned"))
    settings.sync()

    repository = RecentEntriesRepository(QSettingsAdapter(settings), limit=3)
    images = [tmp_path / f"image-{index}.png" for index in range(4)]
    folder = tmp_path / "dataset"
    comparison_set = tmp_path / "review.pixelscope"
    repository.record(RecentEntryKind.IMAGE, images)
    repository.record(RecentEntryKind.IMAGE, [images[1]])
    repository.record(RecentEntryKind.FOLDER, [folder])
    repository.record(RecentEntryKind.COMPARISON_SET, [comparison_set])

    reconstructed_settings = QSettings(str(ini_path), QSettings.Format.IniFormat)
    reconstructed = RecentEntriesRepository(
        QSettingsAdapter(reconstructed_settings),
        limit=3,
    )

    assert reconstructed.load(RecentEntryKind.IMAGE) == (
        images[1].resolve(),
        images[0].resolve(),
        images[2].resolve(),
    )
    assert reconstructed.load(RecentEntryKind.FOLDER) == (folder.resolve(),)
    assert reconstructed.load(RecentEntryKind.COMPARISON_SET) == (comparison_set.resolve(),)
    assert reconstructed_settings.value("settings/schema_version") == 5
    assert reconstructed_settings.value("settings/files/default_open_directory") == str(
        tmp_path / "owned"
    )

    reconstructed.clear()

    after_clear_settings = QSettings(str(ini_path), QSettings.Format.IniFormat)
    after_clear = RecentEntriesRepository(QSettingsAdapter(after_clear_settings), limit=3)
    assert all(after_clear.load(kind) == () for kind in RecentEntryKind)
    assert after_clear_settings.value("settings/schema_version") == 5
    assert after_clear_settings.value("settings/files/default_open_directory") == str(
        tmp_path / "owned"
    )
