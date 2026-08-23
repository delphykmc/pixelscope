from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from pixelscope.app.iqa_history import (
    RECENT_IQA_RESULTS_KEY,
    RecentIqaResultsRepository,
)
from pixelscope.remote.iqa_history import (
    RECENT_IQA_ENTRY_VERSION,
    RECENT_IQA_RESULT_LIMIT,
    IqaResultIdentity,
    LocalIqaResultLocator,
    LogicalIqaResultLocator,
    RecentIqaResultEntry,
    locator_for_manual_result,
    parse_recent_iqa_entry,
    serialize_recent_iqa_entry,
)
from pixelscope.remote.iqa_settings import RemoteIqaSettings, RemoteIqaStorageRoot


@dataclass
class _MemoryStorage:
    values: dict[str, object] = field(default_factory=dict)
    sync_count: int = 0

    def value(self, key: str, default: object = None) -> object:
        return self.values.get(key, default)

    def set_value(self, key: str, value: object) -> None:
        self.values[key] = value

    def remove(self, key: str) -> None:
        self.values.pop(key, None)

    def sync(self) -> None:
        self.sync_count += 1


def _entry(index: int) -> RecentIqaResultEntry:
    return RecentIqaResultEntry(
        LogicalIqaResultLocator("shared", f"results/run-{index}"),
        IqaResultIdentity(f"result-{index}", 2),
    )


def test_recent_entry_round_trip_preserves_typed_locator_and_identity() -> None:
    entry = RecentIqaResultEntry(
        LogicalIqaResultLocator("results", "published/job-42"),
        IqaResultIdentity("result-42", 2),
    )

    encoded = serialize_recent_iqa_entry(entry)

    assert encoded["version"] == RECENT_IQA_ENTRY_VERSION
    assert parse_recent_iqa_entry(encoded) == entry


def test_malformed_and_future_recent_entries_are_ignored() -> None:
    valid = serialize_recent_iqa_entry(_entry(1))
    future = dict(valid, version=RECENT_IQA_ENTRY_VERSION + 1)
    traversal = {
        **valid,
        "locator": {
            "kind": "logical",
            "storage_root_id": "shared",
            "relative_path": "../escape",
        },
    }

    assert parse_recent_iqa_entry(future) is None
    assert parse_recent_iqa_entry(traversal) is None
    assert parse_recent_iqa_entry({"version": RECENT_IQA_ENTRY_VERSION}) is None


def test_repository_is_bounded_mru_and_deduplicates_by_locator() -> None:
    storage = _MemoryStorage()
    repository = RecentIqaResultsRepository(storage)

    for index in range(RECENT_IQA_RESULT_LIMIT + 3):
        repository.record(_entry(index))

    loaded = repository.load()
    assert len(loaded) == RECENT_IQA_RESULT_LIMIT
    assert loaded[0].result_id == f"result-{RECENT_IQA_RESULT_LIMIT + 2}"
    assert loaded[-1].result_id == "result-3"

    replacement = RecentIqaResultEntry(
        loaded[-1].locator,
        IqaResultIdentity("replacement", 2),
    )
    repository.record(replacement)

    loaded = repository.load()
    assert len(loaded) == RECENT_IQA_RESULT_LIMIT
    assert loaded[0] == replacement
    assert sum(item.locator == replacement.locator for item in loaded) == 1


def test_repository_skips_bad_records_without_dropping_valid_history() -> None:
    storage = _MemoryStorage()
    valid = serialize_recent_iqa_entry(_entry(7))
    storage.values[RECENT_IQA_RESULTS_KEY] = json.dumps(
        [
            {**valid, "version": RECENT_IQA_ENTRY_VERSION + 1},
            {"garbage": True},
            valid,
        ]
    )
    repository = RecentIqaResultsRepository(storage)

    assert repository.load() == (_entry(7),)


def test_manual_v2_uses_most_specific_resolvable_root_but_v1_stays_local(
    tmp_path: Path,
) -> None:
    shared = tmp_path / "IQA"
    results = shared / "results"
    result = results / "2026" / "run-17"
    result.mkdir(parents=True)
    settings = RemoteIqaSettings(
        storage_roots=(
            RemoteIqaStorageRoot("shared", str(shared)),
            RemoteIqaStorageRoot("results", str(results)),
        )
    )

    v2_locator = locator_for_manual_result(result, settings, schema_version=2)
    v1_locator = locator_for_manual_result(result, settings, schema_version=1)

    assert v2_locator == LogicalIqaResultLocator("results", "2026/run-17")
    assert v1_locator == LocalIqaResultLocator(str(result))


def test_manual_v2_symlink_escape_stays_local_when_supported(tmp_path: Path) -> None:
    shared = tmp_path / "IQA"
    outside = tmp_path / "outside"
    target = outside / "run-17"
    shared.mkdir()
    target.mkdir(parents=True)
    link = shared / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlink is unavailable: {exc}")
    opened = link / "run-17"
    settings = RemoteIqaSettings(storage_roots=(RemoteIqaStorageRoot("shared", str(shared)),))

    locator = locator_for_manual_result(opened, settings, schema_version=2)

    assert locator == LocalIqaResultLocator(str(opened))


def test_clear_is_independent_observer_metadata() -> None:
    storage = _MemoryStorage()
    repository = RecentIqaResultsRepository(storage)
    repository.record(_entry(1))
    storage.values["settings/schema_version"] = 6

    repository.clear()

    assert RECENT_IQA_RESULTS_KEY not in storage.values
    assert storage.values["settings/schema_version"] == 6
    assert storage.sync_count >= 2
