from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass

from numpy.typing import NDArray
import numpy as np

DocumentGeneration = tuple[str, int]
DifferenceCacheKey = tuple[DocumentGeneration, DocumentGeneration]


@dataclass(frozen=True)
class CachedDifferenceMap:
    """One compact, channel-complete native-domain absolute map."""

    absolute: NDArray[np.generic]
    data_range: float
    channel_layout: str
    bayer_pattern: str | None

    @property
    def nbytes(self) -> int:
        return int(self.absolute.nbytes)


@dataclass(frozen=True)
class DifferenceCachePutResult:
    stored: bool
    evicted_keys: tuple[DifferenceCacheKey, ...]


class DifferenceMapCache:
    """Byte-budget LRU for compact Difference maps.

    The cache owns no UI or settings persistence. Its fixed budget is supplied at
    construction time and is intended to be selected once during application
    startup. Access through :meth:`get` updates LRU order.
    """

    def __init__(self, budget_bytes: int) -> None:
        if budget_bytes <= 0:
            raise ValueError("difference cache budget must be positive")
        self._budget_bytes = int(budget_bytes)
        self._used_bytes = 0
        self._entries: OrderedDict[DifferenceCacheKey, CachedDifferenceMap] = OrderedDict()

    @property
    def budget_bytes(self) -> int:
        return self._budget_bytes

    @property
    def used_bytes(self) -> int:
        return self._used_bytes

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    def __contains__(self, key: object) -> bool:
        return key in self._entries

    def get(self, key: DifferenceCacheKey) -> CachedDifferenceMap | None:
        value = self._entries.get(key)
        if value is not None:
            self._entries.move_to_end(key)
        return value

    def peek(self, key: DifferenceCacheKey) -> CachedDifferenceMap | None:
        """Return an entry without changing LRU order."""

        return self._entries.get(key)

    def put(
        self,
        key: DifferenceCacheKey,
        value: CachedDifferenceMap,
    ) -> DifferenceCachePutResult:
        evicted: list[DifferenceCacheKey] = []
        evicted.extend(self.discard_stale_generations(dict(key)))
        if key in self._entries:
            self._remove(key)

        if value.nbytes > self._budget_bytes:
            return DifferenceCachePutResult(False, tuple(evicted))

        self._entries[key] = value
        self._used_bytes += value.nbytes
        while self._used_bytes > self._budget_bytes and self._entries:
            oldest_key, oldest_value = self._entries.popitem(last=False)
            self._used_bytes -= oldest_value.nbytes
            evicted.append(oldest_key)
        return DifferenceCachePutResult(key in self._entries, tuple(evicted))

    def remove(self, key: DifferenceCacheKey) -> bool:
        if key not in self._entries:
            return False
        self._remove(key)
        return True

    def discard_stale_generations(
        self,
        current_generations: Mapping[str, int],
    ) -> tuple[DifferenceCacheKey, ...]:
        """Drop entries that reference a known document at an older generation."""

        stale = tuple(
            key
            for key in self._entries
            if any(
                document_id in current_generations
                and current_generations[document_id] != generation
                for document_id, generation in key
            )
        )
        for key in stale:
            self._remove(key)
        return stale

    def clear(self) -> None:
        self._entries.clear()
        self._used_bytes = 0

    def keys(self) -> tuple[DifferenceCacheKey, ...]:
        """Return keys from least to most recently used for diagnostics/tests."""

        return tuple(self._entries)

    def _remove(self, key: DifferenceCacheKey) -> None:
        value = self._entries.pop(key)
        self._used_bytes -= value.nbytes
