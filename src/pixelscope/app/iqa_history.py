"""Best-effort persistence for bounded Recent IQA Result observer metadata."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Protocol

from pixelscope.remote.iqa_history import (
    MAX_RECENT_IQA_JSON_CHARS,
    RECENT_IQA_RESULT_LIMIT,
    IqaResultLocator,
    RecentIqaResultEntry,
    parse_recent_iqa_entry,
    serialize_recent_iqa_entry,
)

RECENT_IQA_RESULTS_KEY = "recent/iqa_results"
_MAX_DECODED_RECENT_ITEMS = 64


class RecentIqaSettingsStorage(Protocol):
    def value(self, key: str, default: object = None) -> object:
        ...

    def set_value(self, key: str, value: object) -> None:
        ...

    def remove(self, key: str) -> None:
        ...

    def sync(self) -> None:
        ...


class RecentIqaResultsRepository:
    """Persist only typed historical Result locators and observed Result identity."""

    def __init__(self, storage: RecentIqaSettingsStorage) -> None:
        self._storage = storage

    def load(self) -> tuple[RecentIqaResultEntry, ...]:
        value = self._storage.value(RECENT_IQA_RESULTS_KEY, "")
        if value in (None, ""):
            return ()
        if not isinstance(value, str) or len(value) > MAX_RECENT_IQA_JSON_CHARS:
            return ()
        try:
            raw = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return ()
        if not isinstance(raw, list) or len(raw) > _MAX_DECODED_RECENT_ITEMS:
            return ()
        entries: list[RecentIqaResultEntry] = []
        seen: set[tuple[str, str, str]] = set()
        for item in raw:
            entry = parse_recent_iqa_entry(item)
            if entry is None or entry.dedup_key in seen:
                continue
            seen.add(entry.dedup_key)
            entries.append(entry)
            if len(entries) == RECENT_IQA_RESULT_LIMIT:
                break
        return tuple(entries)

    def record(self, entry: RecentIqaResultEntry) -> tuple[RecentIqaResultEntry, ...]:
        entries = [item for item in self.load() if item.dedup_key != entry.dedup_key]
        entries.insert(0, entry)
        bounded = tuple(entries[:RECENT_IQA_RESULT_LIMIT])
        self._write(bounded)
        return bounded

    def remove(self, locator: IqaResultLocator) -> tuple[RecentIqaResultEntry, ...]:
        key = locator.dedup_key
        entries = tuple(item for item in self.load() if item.dedup_key != key)
        self._write(entries)
        return entries

    def clear(self) -> None:
        self._storage.remove(RECENT_IQA_RESULTS_KEY)
        self._storage.sync()

    def replace(self, entries: Sequence[RecentIqaResultEntry]) -> None:
        """Test/support hook retaining the same count/dedup constraints as normal writes."""

        unique: list[RecentIqaResultEntry] = []
        seen: set[tuple[str, str, str]] = set()
        for entry in entries:
            if entry.dedup_key in seen:
                continue
            seen.add(entry.dedup_key)
            unique.append(entry)
            if len(unique) == RECENT_IQA_RESULT_LIMIT:
                break
        self._write(tuple(unique))

    def _write(self, entries: Sequence[RecentIqaResultEntry]) -> None:
        payload = json.dumps(
            [serialize_recent_iqa_entry(entry) for entry in entries],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        if len(payload) > MAX_RECENT_IQA_JSON_CHARS:
            raise ValueError("Recent IQA Result metadata exceeded persistence bound")
        self._storage.set_value(RECENT_IQA_RESULTS_KEY, payload)
        self._storage.sync()
