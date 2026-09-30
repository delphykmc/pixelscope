from __future__ import annotations

from pathlib import Path

from pixelscope.io.raw_profile import RawProfile
from pixelscope.io.raw_reader import read_raw, required_file_size


def _profile(bit_order: str) -> RawProfile:
    return RawProfile(
        name="packed-stream",
        width=5,
        height=2,
        stride_bytes=9,
        offset_bytes=0,
        storage_format="packed_stream",
        container_dtype=None,
        endianness=None,
        bit_depth=10,
        bit_alignment=None,
        packed_bit_order=bit_order,
        channel_layout="GRAY",
        black_level=0,
        white_level=1023,
    )


def test_packed_stream_profile_uses_bit_depth_for_minimum_row_size() -> None:
    profile = _profile("msb")

    assert profile.minimum_row_bytes == 7
    assert profile.container_dtype is None
    assert profile.endianness is None
    assert profile.bit_alignment is None
    assert profile.packed_bit_order == "msb"
    assert required_file_size(profile) == 18


def test_packed_stream_decodes_msb_first_and_skips_row_padding(tmp_path: Path) -> None:
    profile = _profile("msb")
    row0 = bytes.fromhex("00001009ffffc0")
    row1 = bytes.fromhex("ffe00404030000")
    path = tmp_path / "packed-msb.raw"
    path.write_bytes(row0 + b"\xaa\xbb" + row1 + b"\xcc\xdd")

    assert read_raw(path, profile).tolist() == [
        [0, 1, 2, 511, 1023],
        [1023, 512, 257, 3, 0],
    ]


def test_packed_stream_decodes_lsb_first_and_skips_row_padding(tmp_path: Path) -> None:
    profile = _profile("lsb")
    row0 = bytes.fromhex("000420c07fff03")
    row1 = bytes.fromhex("ff0318d0000000")
    path = tmp_path / "packed-lsb.raw"
    path.write_bytes(row0 + b"\xaa\xbb" + row1 + b"\xcc\xdd")

    assert read_raw(path, profile).tolist() == [
        [0, 1, 2, 511, 1023],
        [1023, 512, 257, 3, 0],
    ]
