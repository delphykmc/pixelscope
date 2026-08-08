from __future__ import annotations

import ctypes
import os
import sys
from dataclasses import dataclass

MIB = 1024 * 1024
DEFAULT_DIFFERENCE_CACHE_BYTES = 128 * MIB
DEFAULT_SOURCE_RESIDENCY_BYTES = 256 * MIB


def detect_physical_memory_bytes() -> int | None:
    """Return installed physical memory without adding a runtime dependency."""

    if sys.platform == "win32":

        class _MemoryStatusEx(ctypes.Structure):
            _fields_ = (
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            )

        status = _MemoryStatusEx()
        status.dwLength = ctypes.sizeof(status)
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            global_memory_status = kernel32.GlobalMemoryStatusEx
            global_memory_status.argtypes = (ctypes.POINTER(_MemoryStatusEx),)
            global_memory_status.restype = ctypes.c_int
            if global_memory_status(ctypes.byref(status)):
                return int(status.ullTotalPhys)
        except (AttributeError, OSError):
            return None
        return None

    try:
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        page_count = int(os.sysconf("SC_PHYS_PAGES"))
    except (AttributeError, OSError, TypeError, ValueError):
        return None
    total = page_size * page_count
    return total if total > 0 else None


def memory_budgets_fit_physical_memory(
    source_residency_bytes: int,
    difference_cache_bytes: int,
    physical_memory_bytes: int | None,
) -> bool:
    """Keep configured budgets within the conservative machine envelope."""

    limit = recommended_combined_memory_limit_bytes(physical_memory_bytes)
    if limit is None:
        return True
    return source_residency_bytes + difference_cache_bytes <= limit


def recommended_combined_memory_limit_bytes(
    physical_memory_bytes: int | None,
) -> int | None:
    """Return the recommended 50% RAM envelope, when RAM is detectable."""

    if physical_memory_bytes is None or physical_memory_bytes <= 0:
        return None
    return physical_memory_bytes // 2


@dataclass(frozen=True)
class PerformanceSettings:
    """Immutable startup-only performance limits injected into runtime services."""

    difference_cache_bytes: int = DEFAULT_DIFFERENCE_CACHE_BYTES
    source_residency_bytes: int = DEFAULT_SOURCE_RESIDENCY_BYTES

    def __post_init__(self) -> None:
        self._validate_budget("difference cache", self.difference_cache_bytes)
        self._validate_budget("source residency", self.source_residency_bytes)

    @staticmethod
    def _validate_budget(name: str, value: object) -> None:
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"{name} budget must be an integer")
        if value <= 0:
            raise ValueError(f"{name} budget must be positive")
