from __future__ import annotations

import numpy as np
import pytest

from pixelscope.core.performance_settings import MIB
from pixelscope.core.residency import ResidencyManager


@pytest.mark.parametrize(
    ("shape", "dtype"),
    (
        ((5, 7), np.uint8),
        ((5, 7), np.uint16),
        ((5, 7, 3), np.uint8),
        ((5, 7, 3), np.uint16),
    ),
)
def test_records_exact_native_source_nbytes(
    shape: tuple[int, ...], dtype: type[np.generic]
) -> None:
    source = np.zeros(shape, dtype=dtype)
    manager = ResidencyManager(source.nbytes * 2)

    manager.record("source", int(source.nbytes))

    assert manager.used_bytes == source.nbytes
    assert manager.resident_count == 1


def test_twenty_one_fhd_rgb8_sources_fit_in_128_mib() -> None:
    source_bytes = 1920 * 1080 * 3
    manager = ResidencyManager(128 * MIB)

    for index in range(21):
        manager.record(f"fhd-{index}", source_bytes)

    assert manager.used_bytes == 21 * source_bytes
    assert manager.used_bytes < manager.budget_bytes
    assert manager.resident_count == 21
    assert manager.eviction_candidates(set()) == ()


def test_lru_touch_remove_reregister_and_changed_size_are_deterministic() -> None:
    manager = ResidencyManager(10)
    manager.record("a", 3)
    manager.record("b", 4)
    manager.record("c", 2)
    assert manager.resident_document_ids == ("a", "b", "c")

    assert manager.touch("a")
    assert manager.resident_document_ids == ("b", "c", "a")
    assert manager.touch("a")
    assert manager.resident_document_ids == ("b", "c", "a")
    assert not manager.touch("missing")

    manager.record("c", 5)
    assert manager.used_bytes == 12
    assert manager.resident_document_ids == ("b", "c", "a")
    assert manager.remove("c")
    assert not manager.remove("c")
    assert manager.used_bytes == 7

    manager.record("c", 1)
    assert manager.resident_document_ids == ("b", "a", "c")
    assert manager.used_bytes == 8


def test_budget_planning_uses_oldest_unprotected_until_exact_boundary() -> None:
    manager = ResidencyManager(10)
    manager.record("a", 3)
    manager.record("b", 4)
    assert manager.eviction_candidates(set()) == ()

    manager.record("c", 3)
    assert manager.eviction_candidates(set()) == ()

    manager.record("d", 6)
    assert manager.eviction_candidates(set()) == ("a", "b")
    assert manager.resident_document_ids == ("a", "b", "c", "d")
    assert manager.used_bytes == 16


def test_budget_planning_skips_one_or_several_protected_sources() -> None:
    manager = ResidencyManager(6)
    for document_id in ("a", "b", "c", "d"):
        manager.record(document_id, 3)

    assert manager.eviction_candidates({"a"}) == ("b", "c")
    assert manager.eviction_candidates({"a", "b"}) == ("c", "d")
    assert manager.eviction_candidates({"a", "b", "c", "d"}) == ()


def test_oversized_source_obeys_soft_protection_policy() -> None:
    manager = ResidencyManager(8)
    manager.record("small", 2)
    manager.record("oversized", 12)

    assert manager.eviction_candidates({"oversized"}) == ("small",)
    assert manager.eviction_candidates(set()) == ("small", "oversized")


def test_minimal_diagnostics_follow_record_touch_and_remove() -> None:
    manager = ResidencyManager(5)
    assert manager.budget_bytes == 5
    assert manager.used_bytes == 0
    assert manager.resident_count == 0
    assert manager.over_budget_bytes == 0

    manager.record("a", 8)
    assert manager.used_bytes == 8
    assert manager.resident_count == 1
    assert manager.over_budget_bytes == 3
    manager.remove("a")
    assert manager.used_bytes == 0
    assert manager.resident_count == 0
    assert manager.over_budget_bytes == 0


@pytest.mark.parametrize("budget", (0, -1, True, 1.5))
def test_budget_must_be_a_positive_integer(budget: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        ResidencyManager(budget)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("document_id", "source_nbytes"),
    (("", 1), ("a", 0), ("a", -1), ("a", True), (1, 1)),
)
def test_records_require_valid_ids_and_positive_integer_bytes(
    document_id: object, source_nbytes: object
) -> None:
    manager = ResidencyManager(10)
    with pytest.raises((TypeError, ValueError)):
        manager.record(document_id, source_nbytes)  # type: ignore[arg-type]
