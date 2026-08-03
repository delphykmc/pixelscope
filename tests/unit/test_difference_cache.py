from __future__ import annotations

import numpy as np
import pytest

from pixelscope.core.difference_cache import (
    CachedDifferenceMap,
    DifferenceCacheKey,
    DifferenceMapCache,
)
from pixelscope.core.performance_settings import (
    DEFAULT_DIFFERENCE_CACHE_BYTES,
    MIB,
    PerformanceSettings,
)


def _key(a: str, a_generation: int, b: str, b_generation: int) -> DifferenceCacheKey:
    first = (a, a_generation)
    second = (b, b_generation)
    return (first, second) if first <= second else (second, first)


def _cached(size: int, value: int = 0) -> CachedDifferenceMap:
    return CachedDifferenceMap(
        np.full(size, value, dtype=np.uint8),
        255.0,
        "RGB",
        None,
    )


def test_default_performance_settings_use_512_mib_difference_cache() -> None:
    settings = PerformanceSettings()
    assert MIB == 1024 * 1024
    assert settings.difference_cache_bytes == 512 * MIB
    assert DEFAULT_DIFFERENCE_CACHE_BYTES == settings.difference_cache_bytes
    with pytest.raises(ValueError, match="positive"):
        PerformanceSettings(difference_cache_bytes=0)


def test_difference_cache_uses_byte_budget_and_true_lru_order() -> None:
    cache = DifferenceMapCache(8)
    first = _key("a", 0, "b", 0)
    second = _key("c", 0, "d", 0)
    third = _key("e", 0, "f", 0)

    assert cache.put(first, _cached(4, 1)).stored
    assert cache.put(second, _cached(4, 2)).stored
    assert cache.budget_bytes == 8
    assert cache.used_bytes == 8
    assert cache.entry_count == 2
    assert cache.keys() == (first, second)

    assert cache.get(first) is not None
    assert cache.keys() == (second, first)
    result = cache.put(third, _cached(4, 3))

    assert result.stored
    assert result.evicted_keys == (second,)
    assert cache.keys() == (first, third)
    assert cache.used_bytes == 8
    assert cache.entry_count == 2


def test_difference_cache_rejects_one_oversized_map_without_evicting_others() -> None:
    cache = DifferenceMapCache(4)
    retained = _key("a", 0, "b", 0)
    oversized = _key("c", 0, "d", 0)
    cache.put(retained, _cached(4))

    result = cache.put(oversized, _cached(5))

    assert not result.stored
    assert result.evicted_keys == ()
    assert cache.keys() == (retained,)
    assert cache.used_bytes == 4


def test_difference_cache_drops_stale_document_generations() -> None:
    cache = DifferenceMapCache(32)
    stale = _key("a", 0, "b", 0)
    unrelated = _key("c", 0, "d", 0)
    current = _key("a", 1, "e", 0)
    cache.put(stale, _cached(4))
    cache.put(unrelated, _cached(4))

    result = cache.put(current, _cached(4))

    assert result.evicted_keys == (stale,)
    assert cache.keys() == (unrelated, current)
    assert cache.used_bytes == 8


def test_explicit_stale_generation_discard_preserves_unknown_documents() -> None:
    cache = DifferenceMapCache(32)
    stale = _key("a", 2, "b", 0)
    retained = _key("c", 0, "d", 0)
    cache.put(stale, _cached(4))
    cache.put(retained, _cached(4))

    evicted = cache.discard_stale_generations({"a": 3})

    assert evicted == (stale,)
    assert cache.keys() == (retained,)
    assert cache.remove(retained)
    assert not cache.remove(retained)
    assert cache.used_bytes == 0
    assert cache.entry_count == 0
