from __future__ import annotations

from pathlib import Path

from pixelscope.app.recent_entries import RecentEntriesRepository
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
