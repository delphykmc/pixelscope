from __future__ import annotations

from pathlib import Path

import pytest

from pixelscope.io.raw_format import BitOrder, minimum_row_bytes
from pixelscope.io.raw_profile import RawProfile
from pixelscope.io.raw_reader import RawReadError, read_raw, required_file_size


def _profile(
    bit_order: BitOrder,
    *,
    bit_depth: int = 10,
    width: int = 5,
    height: int = 2,
    stride_bytes: int | None = None,
) -> RawProfile:
    minimum = minimum_row_bytes(width, "packed_stream", None, bit_depth)
    return RawProfile(
        name="packed-stream",
        width=width,
        height=height,
        stride_bytes=minimum if stride_bytes is None else stride_bytes,
        offset_bytes=0,
        storage_format="packed_stream",
        container_dtype=None,
        endianness=None,
        bit_depth=bit_depth,
        bit_alignment=None,
        packed_bit_order=bit_order,
        channel_layout="GRAY",
        black_level=0,
        white_level=(1 << bit_depth) - 1,
    )


def _pack_row(values: list[int], bit_depth: int, bit_order: BitOrder) -> bytes:
    bits: list[int] = []
    for value in values:
        for bit_index in range(bit_depth):
            shift = bit_depth - 1 - bit_index if bit_order == "msb" else bit_index
            bits.append((value >> shift) & 1)

    bits.extend([0] * ((-len(bits)) % 8))
    packed = bytearray()
    for start in range(0, len(bits), 8):
        byte_value = 0
        for index, bit in enumerate(bits[start : start + 8]):
            shift = 7 - index if bit_order == "msb" else index
            byte_value |= bit << shift
        packed.append(byte_value)
    return bytes(packed)


def test_packed_stream_profile_uses_bit_depth_for_row_and_file_size() -> None:
    profile = _profile("msb", stride_bytes=9)

    assert profile.minimum_row_bytes == 7
    assert required_file_size(profile) == 18
    assert minimum_row_bytes(4000, "packed_stream", None, 10) == 5000
    assert profile.container_dtype is None
    assert profile.endianness is None
    assert profile.bit_alignment is None
    assert profile.packed_bit_order == "msb"


@pytest.mark.parametrize(
    ("bit_order", "row0", "row1"),
    [
        ("msb", "00001009ffffc0", "ffe00404030000"),
        ("lsb", "000420c07fff03", "ff0318d0000000"),
    ],
)
def test_packed_stream_known_vectors_skip_row_padding(
    tmp_path: Path,
    bit_order: BitOrder,
    row0: str,
    row1: str,
) -> None:
    profile = _profile(bit_order, stride_bytes=9)
    path = tmp_path / f"packed-{bit_order}.raw"
    path.write_bytes(
        bytes.fromhex(row0)
        + b"\xaa\xbb"
        + bytes.fromhex(row1)
        + b"\xcc\xdd"
    )

    assert read_raw(path, profile).tolist() == [
        [0, 1, 2, 511, 1023],
        [1023, 512, 257, 3, 0],
    ]


@pytest.mark.parametrize("bit_order", ["msb", "lsb"])
@pytest.mark.parametrize("bit_depth", [1, 8, 10, 15, 16])
def test_packed_stream_decodes_supported_bit_depth_boundaries(
    tmp_path: Path,
    bit_order: BitOrder,
    bit_depth: int,
) -> None:
    maximum = (1 << bit_depth) - 1
    values = [0, 1 << (bit_depth - 1), maximum]
    profile = _profile(
        bit_order,
        bit_depth=bit_depth,
        width=len(values),
        height=1,
    )
    row = _pack_row(values, bit_depth, bit_order)
    path = tmp_path / f"packed-{bit_depth}-{bit_order}.raw"
    path.write_bytes(row)

    assert len(row) == profile.minimum_row_bytes
    assert read_raw(path, profile).tolist() == [values]


def test_packed_stream_enforces_full_stored_row_file_size_contract(tmp_path: Path) -> None:
    profile = _profile("msb", stride_bytes=9)
    required = required_file_size(profile)

    truncated = tmp_path / "truncated.raw"
    truncated.write_bytes(bytes(required - 1))
    with pytest.raises(RawReadError, match="too small"):
        read_raw(truncated, profile)

    exact = tmp_path / "exact.raw"
    exact.write_bytes(bytes(required))
    assert read_raw(exact, profile, require_exact_size=True).shape == (
        profile.height,
        profile.width,
    )

    oversized = tmp_path / "oversized.raw"
    oversized.write_bytes(bytes(required + 1))
    assert read_raw(oversized, profile).shape == (profile.height, profile.width)
    with pytest.raises(RawReadError, match="does not match profile"):
        read_raw(oversized, profile, require_exact_size=True)
