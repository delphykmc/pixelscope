from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from pixelscope.io.raw_profile import RawProfile


class RawReadError(ValueError):
    """Raised when a byte stream does not satisfy its RAW profile."""


def required_file_size(profile: RawProfile) -> int:
    item_size = 1 if profile.dtype == "uint8" else 2
    return (
        profile.offset_bytes
        + (profile.height - 1) * profile.stride_bytes
        + profile.width * item_size
    )


def read_raw(path: str | Path, profile: RawProfile) -> NDArray[np.generic]:
    """Return a strided memmap-backed view for an unpacked RAW file."""

    if profile.packing not in ("unpacked_u8", "unpacked_u16"):
        raise NotImplementedError(f"{profile.packing} is reserved for a future release")
    source_path = Path(path)
    try:
        actual_size = source_path.stat().st_size
    except OSError as exc:
        raise RawReadError(f"Cannot access RAW file: {exc}") from exc
    required = required_file_size(profile)
    if actual_size < required:
        raise RawReadError(
            f"RAW file is too small: {actual_size} bytes, at least {required} required"
        )
    base_dtype = np.dtype(np.uint8 if profile.dtype == "uint8" else np.uint16)
    if base_dtype.itemsize > 1:
        base_dtype = base_dtype.newbyteorder("<" if profile.endianness == "little" else ">")
    mapped = np.memmap(source_path, mode="r", dtype=np.uint8)
    view: NDArray[Any] = np.ndarray(
        shape=(profile.height, profile.width),
        dtype=base_dtype,
        buffer=mapped,
        offset=profile.offset_bytes,
        strides=(profile.stride_bytes, base_dtype.itemsize),
    )
    return view
