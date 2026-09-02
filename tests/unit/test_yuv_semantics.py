from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from pydantic import ValidationError

from pixelscope.core.channel_views import split_document_channels
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineSelection
from pixelscope.core.roi import RoiBounds
from pixelscope.core.yuv import (
    NativeYuvFrame,
    analyze_yuv_roi,
    bt601_full_rgb_preview,
    selected_yuv_line_profile,
)
from pixelscope.io.yuv_profile import YuvProfile
from pixelscope.io.yuv_reader import YuvReadError, read_yuv, required_yuv_file_size


def make_profile(layout: str, *, width: int = 4, height: int = 4) -> YuvProfile:
    return YuvProfile(
        name="synthetic",
        width=width,
        height=height,
        channel_layout=layout,
    )


def write_yuv(
    path: Path,
    profile: YuvProfile,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    y = np.arange(profile.width * profile.height, dtype=np.uint8).reshape(
        profile.height, profile.width
    )
    scale_x = 1 if profile.channel_layout == "YUV444" else 2
    scale_y = 2 if profile.channel_layout == "YUV420" else 1
    chroma_shape = (profile.height // scale_y, profile.width // scale_x)
    u = (np.arange(np.prod(chroma_shape), dtype=np.uint8).reshape(chroma_shape) + 40)
    v = (np.arange(np.prod(chroma_shape), dtype=np.uint8).reshape(chroma_shape) + 180)
    uv = np.empty((chroma_shape[0], chroma_shape[1] * 2), dtype=np.uint8)
    uv[:, 0::2] = u
    uv[:, 1::2] = v
    path.write_bytes(y.tobytes() + uv.tobytes())
    return y, u, v


@pytest.mark.parametrize(
    ("layout", "u_shape", "cardinality"),
    (
        ("YUV444", (4, 4), (16, 16, 16)),
        ("YUV422", (4, 2), (16, 8, 8)),
        ("YUV420", (2, 2), (16, 4, 4)),
    ),
)
def test_decode_native_planes_and_uv_deinterleave(
    tmp_path: Path,
    layout: str,
    u_shape: tuple[int, int],
    cardinality: tuple[int, int, int],
) -> None:
    profile = make_profile(layout)
    path = tmp_path / f"source_{layout}.yuv"
    expected_y, expected_u, expected_v = write_yuv(path, profile)

    frame = read_yuv(path, profile)

    assert frame.y.shape == (4, 4)
    assert frame.u.shape == u_shape
    assert frame.v.shape == u_shape
    assert frame.sample_cardinality == cardinality
    np.testing.assert_array_equal(frame.y, expected_y)
    np.testing.assert_array_equal(frame.u, expected_u)
    np.testing.assert_array_equal(frame.v, expected_v)
    assert required_yuv_file_size(profile) == path.stat().st_size


def test_bt601_full_preview_is_presentation_only() -> None:
    y = np.array([[32, 96], [160, 224]], dtype=np.uint8)
    u = np.array([[32]], dtype=np.uint8)
    v = np.array([[224]], dtype=np.uint8)
    frame = NativeYuvFrame(y=y, u=u, v=v, layout="YUV420")

    preview = bt601_full_rgb_preview(frame)
    document = ImageDocument.from_yuv(frame, "color.yuv")

    expected = np.empty((2, 2, 3), dtype=np.uint8)
    for row in range(2):
        for column in range(2):
            yy = float(y[row, column])
            cb = float(u[0, 0]) - 128.0
            cr = float(v[0, 0]) - 128.0
            expected[row, column] = np.clip(
                np.rint(
                    (
                        yy + 1.402 * cr,
                        yy - 0.344136 * cb - 0.714136 * cr,
                        yy + 1.772 * cb,
                    )
                ),
                0,
                255,
            ).astype(np.uint8)

    np.testing.assert_array_equal(preview, expected)
    np.testing.assert_array_equal(document.preview, expected)
    assert document.source is frame.y
    assert document.yuv_frame is frame
    assert document.pixel_at(1, 1) == (224, 32, 224)
    assert tuple(int(value) for value in document.preview[1, 1]) != document.pixel_at(1, 1)


@pytest.mark.parametrize(
    ("layout", "coordinate", "expected"),
    (
        ("YUV444", (3, 2), (11, 51, 191)),
        ("YUV422", (3, 2), (11, 45, 185)),
        ("YUV420", (3, 2), (11, 43, 183)),
    ),
)
def test_cursor_coordinates_map_to_native_chroma(
    layout: str,
    coordinate: tuple[int, int],
    expected: tuple[int, int, int],
) -> None:
    scale_x = 1 if layout == "YUV444" else 2
    scale_y = 2 if layout == "YUV420" else 1
    y = np.arange(16, dtype=np.uint8).reshape(4, 4)
    count = (4 // scale_y) * (4 // scale_x)
    u = (np.arange(count, dtype=np.uint8) + 40).reshape(4 // scale_y, 4 // scale_x)
    v = (np.arange(count, dtype=np.uint8) + 180).reshape(4 // scale_y, 4 // scale_x)
    frame = NativeYuvFrame(y=y, u=u, v=v, layout=layout)

    assert frame.pixel_at(*coordinate) == expected


def test_split_views_keep_native_y_u_v_resolution() -> None:
    frame = NativeYuvFrame(
        y=np.arange(16, dtype=np.uint8).reshape(4, 4),
        u=np.array([[10, 20], [30, 40]], dtype=np.uint8),
        v=np.array([[50, 60], [70, 80]], dtype=np.uint8),
        layout="YUV420",
    )
    document = ImageDocument.from_yuv(frame, "split.yuv")

    split = split_document_channels(document)

    assert [item.channel_layout for item in split] == ["CHANNEL_Y", "CHANNEL_U", "CHANNEL_V"]
    assert [item.source.shape for item in split if item.source is not None] == [
        (4, 4),
        (2, 2),
        (2, 2),
    ]
    for item in split:
        assert item.preview is not None
        assert np.array_equal(item.preview[..., 0], item.preview[..., 1])
        assert np.array_equal(item.preview[..., 1], item.preview[..., 2])


@pytest.mark.parametrize(
    ("layout", "sample_counts"),
    (
        ("YUV444", (16, 16, 16)),
        ("YUV422", (16, 8, 8)),
        ("YUV420", (16, 4, 4)),
    ),
)
def test_statistics_and_histogram_use_native_sample_cardinality(
    layout: str,
    sample_counts: tuple[int, int, int],
) -> None:
    scale_x = 1 if layout == "YUV444" else 2
    scale_y = 2 if layout == "YUV420" else 1
    y = np.arange(16, dtype=np.uint8).reshape(4, 4)
    chroma_shape = (4 // scale_y, 4 // scale_x)
    u = np.full(chroma_shape, 73, dtype=np.uint8)
    v = np.full(chroma_shape, 201, dtype=np.uint8)
    frame = NativeYuvFrame(y=y, u=u, v=v, layout=layout)

    result = analyze_yuv_roi(frame, RoiBounds(0, 0, 4, 4))

    assert result.channel_names == ("Y", "U", "V")
    assert result.channel_sample_counts == sample_counts
    assert tuple(int(np.sum(counts)) for counts in result.histogram.counts) == sample_counts
    assert result.channel_statistics[1].mean == 73.0
    assert result.channel_statistics[2].mean == 201.0


def test_odd_roi_maps_to_native_chroma_footprint() -> None:
    frame = NativeYuvFrame(
        y=np.arange(36, dtype=np.uint8).reshape(6, 6),
        u=np.arange(9, dtype=np.uint8).reshape(3, 3),
        v=(np.arange(9, dtype=np.uint8) + 100).reshape(3, 3),
        layout="YUV420",
    )

    y_roi, u_roi, v_roi = frame.roi_planes(RoiBounds(1, 1, 3, 3))
    result = analyze_yuv_roi(frame, RoiBounds(1, 1, 3, 3))

    assert y_roi.shape == (3, 3)
    assert u_roi.shape == (2, 2)
    assert v_roi.shape == (2, 2)
    np.testing.assert_array_equal(u_roi, frame.u[0:2, 0:2])
    assert result.channel_sample_counts == (9, 4, 4)


@pytest.mark.parametrize("layout", ("YUV422", "YUV420"))
def test_horizontal_line_profile_keeps_native_chroma_positions(layout: str) -> None:
    scale_y = 2 if layout == "YUV420" else 1
    frame = NativeYuvFrame(
        y=np.arange(16, dtype=np.uint8).reshape(4, 4),
        u=np.arange((4 // scale_y) * 2, dtype=np.uint8).reshape(4 // scale_y, 2),
        v=(np.arange((4 // scale_y) * 2, dtype=np.uint8) + 100).reshape(
            4 // scale_y, 2
        ),
        layout=layout,
    )

    result = selected_yuv_line_profile(frame, LineSelection(0, 0, 3, 0))

    assert result.channel_names == ("Y", "U", "V")
    np.testing.assert_array_equal(result.positions[0], [0.0, 1.0, 2.0, 3.0])
    np.testing.assert_array_equal(result.positions[1], [0.0, 2.0])
    np.testing.assert_array_equal(result.positions[2], [0.0, 2.0])
    assert [len(values) for values in result.values] == [4, 2, 2]


def test_vertical_yuv420_line_profile_keeps_native_chroma_positions() -> None:
    frame = NativeYuvFrame(
        y=np.arange(16, dtype=np.uint8).reshape(4, 4),
        u=np.arange(4, dtype=np.uint8).reshape(2, 2),
        v=(np.arange(4, dtype=np.uint8) + 100).reshape(2, 2),
        layout="YUV420",
    )

    result = selected_yuv_line_profile(frame, LineSelection(0, 0, 0, 3))

    np.testing.assert_array_equal(result.positions[0], [0.0, 1.0, 2.0, 3.0])
    np.testing.assert_array_equal(result.positions[1], [0.0, 2.0])
    np.testing.assert_array_equal(result.positions[2], [0.0, 2.0])


def test_profile_geometry_and_file_size_are_strict(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="width must be even"):
        make_profile("YUV422", width=3, height=4)
    with pytest.raises(ValidationError, match="height must be even"):
        make_profile("YUV420", width=4, height=3)

    profile = make_profile("YUV420")
    short = tmp_path / "short.yuv"
    short.write_bytes(b"\0" * (profile.expected_file_size - 1))
    long = tmp_path / "long.yuv"
    long.write_bytes(b"\0" * (profile.expected_file_size + 1))
    with pytest.raises(YuvReadError, match="does not match profile"):
        read_yuv(short, profile)
    with pytest.raises(YuvReadError, match="does not match profile"):
        read_yuv(long, profile)


def test_rgb_gray_and_bayer_document_semantics_are_unchanged() -> None:
    rgb = np.array([[[1, 2, 3], [4, 5, 6]]], dtype=np.uint8)
    rgb_document = ImageDocument.from_array(rgb, "rgb.png")
    assert rgb_document.pixel_at(1, 0) == (4, 5, 6)
    assert [item.channel_layout for item in split_document_channels(rgb_document)] == [
        "CHANNEL_R",
        "CHANNEL_G",
        "CHANNEL_B",
    ]

    gray = np.array([[7, 8]], dtype=np.uint8)
    gray_document = ImageDocument.from_array(gray, "gray.png")
    assert gray_document.pixel_at(1, 0) == 8
    assert split_document_channels(gray_document) == []

    bayer = np.arange(16, dtype=np.uint16).reshape(4, 4)
    bayer_document = ImageDocument.from_array(
        bayer,
        "bayer.raw",
        channel_layout="BAYER",
        bit_depth=12,
        raw_profile=SimpleNamespace(bayer_pattern="RGGB"),
    )
    assert {item.channel_layout for item in split_document_channels(bayer_document)} == {
        "CHANNEL_R",
        "CHANNEL_Gr",
        "CHANNEL_Gb",
        "CHANNEL_B",
    }
