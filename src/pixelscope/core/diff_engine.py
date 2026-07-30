from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def _validate_pair(a: NDArray[np.generic], b: NDArray[np.generic]) -> None:
    if a.shape != b.shape:
        raise ValueError(f"image shape mismatch: A{a.shape} != B{b.shape}")
    if a.size == 0:
        raise ValueError("images must not be empty")
    if not np.issubdtype(a.dtype, np.number) or not np.issubdtype(b.dtype, np.number):
        raise TypeError("difference operands must be numeric arrays")


def signed_difference(
    a: NDArray[np.generic], b: NDArray[np.generic]
) -> NDArray[np.int32] | NDArray[np.int64] | NDArray[np.float64]:
    """Calculate A-B after promotion, preventing integer wrap-around."""

    _validate_pair(a, b)
    if np.issubdtype(a.dtype, np.integer) and np.issubdtype(b.dtype, np.integer):
        if a.dtype.itemsize <= 2 and b.dtype.itemsize <= 2:
            compact_result: NDArray[np.int32] = np.subtract(a, b, dtype=np.int32)
            return compact_result
        integer_result: NDArray[np.int64] = np.subtract(a, b, dtype=np.int64)
        return integer_result
    float_result: NDArray[np.float64] = np.subtract(a.astype(np.float64), b.astype(np.float64))
    return float_result


def absolute_difference(
    a: NDArray[np.generic], b: NDArray[np.generic]
) -> NDArray[np.int32] | NDArray[np.int64] | NDArray[np.float64]:
    """Return abs(A-B) based on the overflow-safe signed result."""

    signed = signed_difference(a, b)
    if signed.dtype == np.dtype(np.int32):
        compact_result: NDArray[np.int32] = np.abs(signed)
        return compact_result
    if signed.dtype == np.dtype(np.int64):
        integer_result: NDArray[np.int64] = np.abs(signed)
        return integer_result
    float_result: NDArray[np.float64] = np.abs(signed)
    return float_result
