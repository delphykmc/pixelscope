from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from pixelscope.io.raw_format import container_bit_count, container_byte_count
from pixelscope.io.raw_profile import RawProfile


class RawReadError(ValueError):
    """Raised when a byte stream does not satisfy its RAW profile."""


def required_file_size(profile: RawProfile) -> int:
    return (
        profile.offset_bytes
        + (profile.height - 1) * profile.stride_bytes
        + profile.minimum_row_bytes
    )


def _map_source(path: Path, profile: RawProfile) -> NDArray[np.uint8]:
    try:
        actual_size = path.stat().st_size
    except OSError as exc:
        raise RawReadError(f"Cannot access RAW file: {exc}") from exc
    required = required_file_size(profile)
    if actual_size < required:
        raise RawReadError(
            f"RAW file is too small: {actual_size} bytes, at least {required} required"
        )
    return np.memmap(path, mode="r", dtype=np.uint8)


def _read_unpacked(
    mapped: NDArray[np.uint8],
    profile: RawProfile,
) -> NDArray[np.generic]:
    container_dtype = profile.container_dtype
    if container_dtype is None:
        raise RawReadError("Unpacked RAW profile has no sample container")
    item_size = container_byte_count(container_dtype)
    base_dtype = np.dtype(np.uint8 if item_size == 1 else np.uint16)
    if item_size > 1:
        if profile.endianness == "little":
            base_dtype = base_dtype.newbyteorder("<")
        else:
            base_dtype = base_dtype.newbyteorder(">")
    view: NDArray[Any] = np.ndarray(
        shape=(profile.height, profile.width),
        dtype=base_dtype,
        buffer=mapped,
        offset=profile.offset_bytes,
        strides=(profile.stride_bytes, item_size),
    )
    container_bits = container_bit_count(container_dtype)
    if profile.bit_depth == container_bits:
        return view
    decoded = np.asarray(view, dtype=np.uint16)
    if profile.bit_alignment == "msb":
        return decoded >> (container_bits - profile.bit_depth)
    mask = np.uint16((1 << profile.bit_depth) - 1)
    return decoded & mask


def _packed_rows(
    mapped: NDArray[np.uint8],
    profile: RawProfile,
) -> NDArray[np.uint8]:
    rows: NDArray[Any] = np.ndarray(
        shape=(profile.height, profile.minimum_row_bytes),
        dtype=np.uint8,
        buffer=mapped,
        offset=profile.offset_bytes,
        strides=(profile.stride_bytes, 1),
    )
    return rows


def _decode_mipi_raw10(rows: NDArray[np.uint8]) -> NDArray[np.uint16]:
    groups = rows.reshape(rows.shape[0], -1, 5).astype(np.uint16)
    result = np.empty((rows.shape[0], groups.shape[1] * 4), dtype=np.uint16)
    low = groups[:, :, 4]
    result[:, 0::4] = (groups[:, :, 0] << 2) | (low & 0x03)
    result[:, 1::4] = (groups[:, :, 1] << 2) | ((low >> 2) & 0x03)
    result[:, 2::4] = (groups[:, :, 2] << 2) | ((low >> 4) & 0x03)
    result[:, 3::4] = (groups[:, :, 3] << 2) | ((low >> 6) & 0x03)
    return result


def _decode_mipi_raw12(rows: NDArray[np.uint8]) -> NDArray[np.uint16]:
    groups = rows.reshape(rows.shape[0], -1, 3).astype(np.uint16)
    result = np.empty((rows.shape[0], groups.shape[1] * 2), dtype=np.uint16)
    low = groups[:, :, 2]
    result[:, 0::2] = (groups[:, :, 0] << 4) | (low & 0x0F)
    result[:, 1::2] = (groups[:, :, 1] << 4) | ((low >> 4) & 0x0F)
    return result


def _decode_mipi_raw14(rows: NDArray[np.uint8]) -> NDArray[np.uint16]:
    groups = rows.reshape(rows.shape[0], -1, 7).astype(np.uint16)
    result = np.empty((rows.shape[0], groups.shape[1] * 4), dtype=np.uint16)
    byte4 = groups[:, :, 4]
    byte5 = groups[:, :, 5]
    byte6 = groups[:, :, 6]
    low0 = byte4 & 0x3F
    low1 = ((byte4 >> 6) & 0x03) | ((byte5 & 0x0F) << 2)
    low2 = ((byte5 >> 4) & 0x0F) | ((byte6 & 0x03) << 4)
    low3 = (byte6 >> 2) & 0x3F
    result[:, 0::4] = (groups[:, :, 0] << 6) | low0
    result[:, 1::4] = (groups[:, :, 1] << 6) | low1
    result[:, 2::4] = (groups[:, :, 2] << 6) | low2
    result[:, 3::4] = (groups[:, :, 3] << 6) | low3
    return result


def read_raw(path: str | Path, profile: RawProfile) -> NDArray[np.generic]:
    """Decode one supported unpacked or MIPI-packed RAW file."""

    source_path = Path(path)
    mapped = _map_source(source_path, profile)
    if profile.storage_format == "unpacked":
        return _read_unpacked(mapped, profile)
    rows = _packed_rows(mapped, profile)
    if profile.storage_format == "mipi_raw10":
        return _decode_mipi_raw10(rows)
    if profile.storage_format == "mipi_raw12":
        return _decode_mipi_raw12(rows)
    if profile.storage_format == "mipi_raw14":
        return _decode_mipi_raw14(rows)
    raise RawReadError(f"Unsupported RAW storage format: {profile.storage_format}")
