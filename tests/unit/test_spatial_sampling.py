from __future__ import annotations

import numpy as np
import pytest

from pixelscope.core.bayer import bayer_channel_positions
from pixelscope.core.channel_views import split_document_channels
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.roi import RoiBounds
from pixelscope.core.spatial_sampling import SpatialSampling
from pixelscope.core.yuv import NativeYuvFrame
from pixelscope.io.raw_profile import RawProfile


def test_identity_sampling_and_reference_lookup_keep_native_coordinates() -> None:
    document = ImageDocument.from_array(np.arange(12, dtype=np.uint16).reshape(3, 4), "gray")

    assert document.shape == (3, 4)
    assert document.reference_shape == (3, 4)
    assert document.pixel_at(3, 2) == 11
    assert document.spatial_sampling == SpatialSampling.identity((3, 4))
    lookup = document.sample_lookup_at_reference(3, 2)
    assert lookup is not None
    assert lookup.reference_xy == (3, 2)
    assert lookup.sample_xy == (3, 2)
    assert lookup.actual_sample_reference_site == (3, 2)
    assert lookup.value == 11
    assert document.sample_lookup_at_reference(4, 2) is None


@pytest.mark.parametrize(
    ("layout", "shape", "expected_step", "expected_uv_shape"),
    [
        ("YUV444", (5, 7), (1, 1), (5, 7)),
        ("YUV422", (5, 8), (1, 2), (5, 4)),
        ("YUV420", (6, 8), (2, 2), (3, 4)),
    ],
)
def test_yuv_channel_views_attach_native_cell_sampling(
    layout: str,
    shape: tuple[int, int],
    expected_step: tuple[int, int],
    expected_uv_shape: tuple[int, int],
) -> None:
    rows, columns = shape
    y = np.arange(rows * columns, dtype=np.uint8).reshape(shape)
    u = np.arange(np.prod(expected_uv_shape), dtype=np.uint8).reshape(expected_uv_shape)
    v = (u + 50).astype(np.uint8)
    document = ImageDocument.from_yuv(NativeYuvFrame(y, u, v, layout), "native.yuv")  # type: ignore[arg-type]
    y_view, u_view, v_view = split_document_channels(document)

    assert y_view.spatial_sampling == SpatialSampling.identity(shape)
    for view, expected_value in ((u_view, int(u[-1, -1])), (v_view, int(v[-1, -1]))):
        sampling = view.spatial_sampling
        assert sampling is not None
        assert sampling.sampling_semantics == "cell_footprint"
        assert (sampling.row_step, sampling.column_step) == expected_step
        assert view.shape == expected_uv_shape
        assert view.reference_shape == shape
        assert np.shares_memory(view.source, u if view is u_view else v)
        lookup = view.sample_lookup_at_reference(columns - 1, rows - 1)
        assert lookup is not None
        assert lookup.sample_xy == (expected_uv_shape[1] - 1, expected_uv_shape[0] - 1)
        assert lookup.value == expected_value


def test_cell_footprint_roi_uses_floor_origin_and_ceil_end() -> None:
    sampling = SpatialSampling.cell_footprint((6, 8), (3, 4), row_step=2, column_step=2)

    assert sampling.reference_roi_to_sample_bounds(RoiBounds(1, 1, 5, 3)) == RoiBounds(0, 0, 3, 2)
    assert sampling.presentation_rect == (0.0, 0.0, 8.0, 6.0)


@pytest.mark.parametrize("pattern", ("RGGB", "GRBG", "GBRG", "BGGR"))
def test_bayer_views_keep_phase_lattice_and_strided_native_planes(pattern: str) -> None:
    source = np.arange(5 * 7, dtype=np.uint16).reshape(5, 7)
    profile = RawProfile(
        name="raw",
        width=7,
        height=5,
        dtype="uint16",
        stride_bytes=14,
        bit_depth=10,
        packing="unpacked_u16",
        channel_layout="BAYER",
        bayer_pattern=pattern,
        black_level=(0, 0, 0, 0),
        white_level=1023,
    )
    document = ImageDocument.from_array(source, "raw", channel_layout="BAYER", raw_profile=profile)
    positions = bayer_channel_positions(pattern)

    for view in split_document_channels(document):
        channel = view.sample_channel
        assert channel is not None
        row_phase, column_phase = positions[channel]
        sampling = view.spatial_sampling
        assert sampling is not None
        assert sampling.sampling_semantics == "point_lattice"
        assert (sampling.row_phase, sampling.column_phase) == (row_phase, column_phase)
        assert view.reference_shape == source.shape
        assert np.shares_memory(view.source, source)
        assert view.source is not None and view.source.strides == source[::2, ::2].strides

        valid = view.sample_lookup_at_reference(column_phase, row_phase)
        assert valid is not None
        assert valid.sample_xy == (0, 0)
        assert valid.actual_sample_reference_site == (column_phase, row_phase)
        assert valid.value == int(source[row_phase, column_phase])
        invalid = view.sample_lookup_at_reference((column_phase + 1) % 2, row_phase)
        assert invalid is not None
        assert invalid.sample_xy is None
        assert invalid.value is None


def test_point_lattice_odd_roi_and_presentation_rect() -> None:
    sampling = SpatialSampling.point_lattice(
        (5, 7), (2, 3), row_step=2, column_step=2, row_phase=1, column_phase=1
    )

    assert sampling.reference_roi_to_sample_bounds(RoiBounds(0, 0, 1, 1)) is None
    assert sampling.reference_roi_to_sample_bounds(RoiBounds(1, 1, 5, 3)) == RoiBounds(0, 0, 3, 2)
    assert sampling.presentation_rect == (0.5, 0.5, 6.0, 4.0)


def test_sampling_rejects_inconsistent_shapes_and_invalid_lattice_phase() -> None:
    with pytest.raises(ValueError, match="sample_shape"):
        SpatialSampling.cell_footprint((5, 7), (2, 3), row_step=2, column_step=2)
    with pytest.raises(ValueError, match="phase"):
        SpatialSampling.point_lattice(
            (4, 4), (2, 2), row_step=2, column_step=2, row_phase=2, column_phase=0
        )
