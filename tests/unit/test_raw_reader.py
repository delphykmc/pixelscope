from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from pixelscope.io.raw_profile import RawProfile
from pixelscope.io.raw_reader import RawReadError, read_raw, required_file_size


def make_profile(**changes: object) -> RawProfile:
    values: dict[str, object] = {
        "name": "test",
        "width": 4,
        "height": 2,
        "stride_bytes": 8,
        "offset_bytes": 0,
        "storage_format": "unpacked",
        "container_dtype": "uint16",
        "endianness": "little",
        "bit_depth": 12,
        "bit_alignment": "lsb",
        "channel_layout": "GRAY",
        "black_level": 0,
        "white_level": 4095,
    }
    values.update(changes)
    return RawProfile(**values)


def test_profile_validates_storage_rules_and_migrates_legacy_fields() -> None:
    profile = make_profile()
    assert profile.minimum_row_bytes == 8
    assert profile.dtype == "uint16"
    assert profile.packing == "unpacked_u16"

    legacy = RawProfile(
        name="legacy",
        width=4,
        height=2,
        stride_bytes=8,
        dtype="uint16",
        endianness="little",
        bit_depth=10,
        packing="unpacked_u16",
        channel_layout="GRAY",
        black_level=0,
        white_level=1023,
    )
    assert legacy.storage_format == "unpacked"
    assert legacy.container_dtype == "uint16"
    assert legacy.bit_alignment == "lsb"
    assert "packing" not in legacy.dict()
    assert "dtype" not in legacy.dict()

    with pytest.raises(ValidationError, match="bit_depth exceeds"):
        make_profile(container_dtype="uint8", bit_depth=10)
    with pytest.raises(ValidationError, match="multiple of 4"):
        make_profile(
            width=6,
            stride_bytes=8,
            storage_format="mipi_raw12",
            container_dtype=None,
            endianness=None,
            bit_depth=12,
            bit_alignment=None,
        )
    with pytest.raises(ValidationError, match="requires bit_depth=10"):
        make_profile(
            storage_format="mipi_raw10",
            container_dtype=None,
            endianness=None,
            bit_depth=12,
            bit_alignment=None,
        )


def test_unpacked_stride_endianness_and_bit_alignment(tmp_path: Path) -> None:
    lsb_profile = make_profile(width=4, height=1, stride_bytes=10, offset_bytes=2)
    lsb_path = tmp_path / "lsb.raw"
    payload = bytearray(required_file_size(lsb_profile))
    payload[2:10] = np.array([0xF001, 0x0002, 0x0ABC, 0x0FFF], dtype="<u2").tobytes()
    lsb_path.write_bytes(payload)
    assert read_raw(lsb_path, lsb_profile).tolist() == [[1, 2, 0xABC, 0xFFF]]

    msb_profile = make_profile(
        width=4,
        height=1,
        stride_bytes=8,
        endianness="big",
        bit_alignment="msb",
    )
    values = np.array([1, 2, 0xABC, 0xFFF], dtype=np.uint16)
    msb_path = tmp_path / "msb.raw"
    msb_path.write_bytes((values << 4).astype(">u2").tobytes())
    assert read_raw(msb_path, msb_profile).tolist() == [values.tolist()]


def test_mipi_raw10_known_layout_and_row_padding(tmp_path: Path) -> None:
    profile = make_profile(
        storage_format="mipi_raw10",
        container_dtype=None,
        endianness=None,
        bit_depth=10,
        bit_alignment=None,
        stride_bytes=7,
        white_level=1023,
    )
    row = bytes([0x00, 0x00, 0x00, 0xFF, 0xE4, 0xAA, 0xBB])
    path = tmp_path / "raw10.raw"
    path.write_bytes(row + row[:5])
    assert required_file_size(profile) == 12
    assert read_raw(path, profile).tolist() == [
        [0, 1, 2, 1023],
        [0, 1, 2, 1023],
    ]


def test_mipi_raw12_known_layout(tmp_path: Path) -> None:
    profile = make_profile(
        storage_format="mipi_raw12",
        container_dtype=None,
        endianness=None,
        bit_depth=12,
        bit_alignment=None,
        stride_bytes=6,
    )
    row = bytes([0xAB, 0x12, 0x3C, 0x45, 0x78, 0x96])
    path = tmp_path / "raw12.raw"
    path.write_bytes(row + row)
    assert read_raw(path, profile).tolist() == [
        [0xABC, 0x123, 0x456, 0x789],
        [0xABC, 0x123, 0x456, 0x789],
    ]


def test_mipi_raw14_known_layout(tmp_path: Path) -> None:
    profile = make_profile(
        storage_format="mipi_raw14",
        container_dtype=None,
        endianness=None,
        bit_depth=14,
        bit_alignment=None,
        stride_bytes=7,
        white_level=16383,
    )
    row = bytes([0x00, 0x01, 0x04, 0xFF, 0x81, 0x40, 0xFC])
    path = tmp_path / "raw14.raw"
    path.write_bytes(row + row)
    assert read_raw(path, profile).tolist() == [
        [1, 66, 260, 16383],
        [1, 66, 260, 16383],
    ]


def test_too_small_file(tmp_path: Path) -> None:
    path = tmp_path / "short.raw"
    path.write_bytes(b"\0" * 4)
    with pytest.raises(RawReadError, match="too small"):
        read_raw(path, make_profile())
