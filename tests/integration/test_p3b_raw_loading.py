from __future__ import annotations

from pathlib import Path

import numpy as np

from pixelscope.core.raw_display import render_raw_preview
from pixelscope.io.image_reader import read_raw_document
from pixelscope.io.raw_profile import RawProfile


def _write_profile(
    path: Path,
    *,
    white_level: int,
    black_level: int | tuple[int, int, int, int] = 64,
) -> RawProfile:
    profile = RawProfile(
        name="raw12-gray",
        width=5,
        height=1,
        stride_bytes=10,
        storage_format="unpacked",
        container_dtype="uint16",
        endianness="little",
        bit_depth=12,
        bit_alignment="lsb",
        channel_layout="GRAY",
        black_level=black_level,
        white_level=white_level,
    )
    profile.save_json(path)
    return profile


def test_raw_document_load_preserves_native_codes_and_ignores_white_for_preview(
    tmp_path: Path,
) -> None:
    source = np.array([[0, 60, 64, 3800, 4095]], dtype=np.uint16)
    raw_path = tmp_path / "sample.raw"
    raw_path.write_bytes(source.astype("<u2", copy=False).tobytes())
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    first = _write_profile(first_path, white_level=3800)
    second = _write_profile(second_path, white_level=4000)

    first_document = read_raw_document(raw_path, first_path)
    second_document = read_raw_document(raw_path, second_path)

    assert first_document.source is not None
    assert second_document.source is not None
    assert np.array_equal(first_document.source, source)
    assert np.array_equal(second_document.source, source)
    assert first_document.pixel_at(3, 0) == 3800
    assert first_document.bit_depth == 12
    assert first_document.preview is not None
    assert second_document.preview is not None
    assert np.array_equal(first_document.preview, second_document.preview)
    assert np.array_equal(
        first_document.preview,
        render_raw_preview(
            source,
            channel_layout="GRAY",
            bit_depth=12,
            black_level=first.black_level,
            gain=1.0,
        ),
    )
    assert first.white_level != second.white_level


def test_gray_tuple_black_level_json_profile_keeps_legacy_minimum_gain_anchor(
    tmp_path: Path,
) -> None:
    source = np.array([[0, 60, 64, 100, 4095]], dtype=np.uint16)
    raw_path = tmp_path / "tuple-black.raw"
    raw_path.write_bytes(source.astype("<u2", copy=False).tobytes())
    profile_path = tmp_path / "tuple-black.json"
    levels = (64, 72, 80, 96)
    _write_profile(profile_path, white_level=3800, black_level=levels)

    document = read_raw_document(raw_path, profile_path)

    assert document.raw_profile is not None
    assert document.raw_profile.black_level == levels
    assert document.source is not None
    assert np.array_equal(document.source, source)
    assert document.preview is not None
    assert np.array_equal(
        document.preview,
        render_raw_preview(
            source,
            channel_layout="GRAY",
            bit_depth=12,
            black_level=levels,
            gain=1.0,
        ),
    )
    tuple_gain = render_raw_preview(
        source,
        channel_layout="GRAY",
        bit_depth=12,
        black_level=levels,
        gain=4.0,
    )
    legacy_minimum_gain = render_raw_preview(
        source,
        channel_layout="GRAY",
        bit_depth=12,
        black_level=min(levels),
        gain=4.0,
    )
    assert np.array_equal(tuple_gain, legacy_minimum_gain)
