from __future__ import annotations

from dataclasses import dataclass

MIB = 1024 * 1024
DEFAULT_DIFFERENCE_CACHE_BYTES = 512 * MIB
DEFAULT_SOURCE_RESIDENCY_BYTES = 1024 * MIB


@dataclass(frozen=True)
class PerformanceSettings:
    """Immutable startup-only performance limits injected into runtime services."""

    difference_cache_bytes: int = DEFAULT_DIFFERENCE_CACHE_BYTES
    source_residency_bytes: int = DEFAULT_SOURCE_RESIDENCY_BYTES

    def __post_init__(self) -> None:
        if self.difference_cache_bytes <= 0:
            raise ValueError("difference cache budget must be positive")
        if self.source_residency_bytes <= 0:
            raise ValueError("source residency budget must be positive")
