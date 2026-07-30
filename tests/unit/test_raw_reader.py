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
        "width": 3,
        "height": 2,
        "stride_bytes": 8,
        "offset_bytes": 2,
        "dtype": "uint16",
        "endianness": "little",
        "bit_depth": 12,
        "packing": "unpacked_u16",
        "channel_layout": "GRAY",
        "black_level": 0,
        "white_level": 4095,
    }
    values.update(changes)
    return RawProfile(**values)


def test_profile_validation() -> None:
    assert make_profile().width == 3
    with pytest.raises(ValidationError):
        make_profile(stride_bytes=4)
    with pytest.raises(ValidationError):
        make_profile(white_level=5000)
    with pytest.raises(ValidationError):
        make_profile(channel_layout="BAYER", bayer_pattern=None)


def test_profile_accepts_case_insensitive_bayer_and_four_black_levels() -> None:
    profile = make_profile(
        channel_layout="bayer",
        bayer_pattern="RGGB",
        black_level=[64, 65, 66, 67],
    )
    assert profile.channel_layout == "BAYER"
    assert profile.black_level == (64, 65, 66, 67)
    assert profile.display_black_level == 64


def test_raw_file_size_and_stride(tmp_path: Path) -> None:
    profile = make_profile()
    path = tmp_path / "stride.raw"
    payload = bytearray(required_file_size(profile))
    payload[2:8] = np.array([1, 2, 3], dtype="<u2").tobytes()
    payload[10:16] = np.array([4, 5, 6], dtype="<u2").tobytes()
    path.write_bytes(payload)
    image = read_raw(path, profile)
    assert image.tolist() == [[1, 2, 3], [4, 5, 6]]
    assert image.strides == (8, 2)


def test_big_endian(tmp_path: Path) -> None:
    profile = make_profile(width=2, height=1, stride_bytes=4, offset_bytes=0, endianness="big")
    path = tmp_path / "big.raw"
    path.write_bytes(np.array([1, 513], dtype=">u2").tobytes())
    assert read_raw(path, profile).tolist() == [[1, 513]]


def test_too_small_file(tmp_path: Path) -> None:
    path = tmp_path / "short.raw"
    path.write_bytes(b"\0" * 4)
    with pytest.raises(RawReadError, match="too small"):
        read_raw(path, make_profile())


def test_reserved_mipi_is_not_silently_decoded(tmp_path: Path) -> None:
    profile = make_profile(packing="mipi_raw12")
    path = tmp_path / "mipi.raw"
    path.write_bytes(b"\0" * 32)
    with pytest.raises(NotImplementedError, match="future"):
        read_raw(path, profile)
