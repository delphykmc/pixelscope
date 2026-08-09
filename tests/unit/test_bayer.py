from __future__ import annotations

import numpy as np

from pixelscope.core.bayer import (
    analyze_bayer_roi,
    bayer_channel_at,
    render_bayer_preview,
    split_bayer_channels,
)
from pixelscope.core.channel_views import split_document_channels
from pixelscope.core.display_transform import DisplayTransform
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineSelection, selected_bayer_line_profile
from pixelscope.core.roi import RoiBounds
from pixelscope.io.raw_profile import RawProfile


def _rggb_source() -> np.ndarray:
    return np.array(
        [
            [10, 20, 11, 21],
            [30, 40, 31, 41],
            [12, 22, 13, 23],
            [32, 42, 33, 43],
        ],
        dtype=np.uint16,
    )


def _profile() -> RawProfile:
    return RawProfile(
        name="test",
        width=4,
        height=4,
        dtype="uint16",
        stride_bytes=8,
        bit_depth=10,
        packing="unpacked_u16",
        channel_layout="BAYER",
        bayer_pattern="RGGB",
        black_level=(0, 0, 0, 0),
        white_level=1023,
    )


def test_bayer_planes_statistics_and_pixel_names() -> None:
    source = _rggb_source()
    channels = dict(split_bayer_channels(source, "RGGB"))
    assert channels["R"].tolist() == [[10, 11], [12, 13]]
    assert channels["Gr"].tolist() == [[20, 21], [22, 23]]
    assert channels["Gb"].tolist() == [[30, 31], [32, 33]]
    assert channels["B"].tolist() == [[40, 41], [42, 43]]
    assert bayer_channel_at("RGGB", 0, 0) == "R"
    assert bayer_channel_at("RGGB", 1, 0) == "Gr"
    assert bayer_channel_at("RGGB", 0, 1) == "Gb"
    assert bayer_channel_at("RGGB", 1, 1) == "B"

    result = analyze_bayer_roi(
        source,
        RoiBounds(0, 0, 4, 4),
        "RGGB",
        bins=1024,
        value_range=(0.0, 1024.0),
    )
    assert result.channel_names == ("R", "Gr", "Gb", "B")
    assert [statistics.mean for statistics in result.channel_statistics] == [
        11.5,
        21.5,
        31.5,
        41.5,
    ]
    assert result.histogram.channel_names == result.channel_names
    assert result.channel_sample_counts == (4, 4, 4, 4)


def test_full_frame_even_rggb_plane_sample_counts() -> None:
    source = np.zeros((2160, 3840), dtype=np.uint16)
    result = analyze_bayer_roi(
        source,
        RoiBounds(0, 0, 3840, 2160),
        "RGGB",
        bins=16,
        value_range=(0.0, 1024.0),
    )
    assert result.channel_sample_counts == (2_073_600,) * 4
    assert sum(result.channel_sample_counts) == source.size


def test_odd_bayer_roi_uses_global_phase_and_actual_plane_sizes() -> None:
    source = np.arange(7 * 9, dtype=np.uint16).reshape(7, 9)
    bounds = RoiBounds(1, 1, 5, 3)
    channels = dict(split_bayer_channels(source, "RGGB", bounds))
    assert channels["R"].tolist() == source[2:4:2, 2:6:2].tolist()
    assert channels["Gr"].tolist() == source[2:4:2, 1:6:2].tolist()
    assert channels["Gb"].tolist() == source[1:4:2, 2:6:2].tolist()
    assert channels["B"].tolist() == source[1:4:2, 1:6:2].tolist()
    result = analyze_bayer_roi(
        source,
        bounds,
        "RGGB",
        bins=64,
        value_range=(0.0, 64.0),
    )
    expected_counts = tuple(channels[name].size for name in ("R", "Gr", "Gb", "B"))
    assert result.channel_sample_counts == expected_counts
    assert result.channel_sample_counts == (2, 3, 4, 6)
    assert sum(result.channel_sample_counts) == bounds.width * bounds.height


def test_bayer_line_retains_every_other_source_position() -> None:
    result = selected_bayer_line_profile(
        _rggb_source(),
        LineSelection(0, 0, 3),
        "RGGB",
    )
    assert result.channel_names == ("R", "Gr", "Gb", "B")
    assert [positions.tolist() for positions in result.positions] == [
        [0.0, 2.0],
        [1.0, 3.0],
        [0.0, 2.0],
        [1.0, 3.0],
    ]
    assert [values.tolist() for values in result.values] == [
        [10.0, 11.0],
        [20.0, 21.0],
        [30.0, 31.0],
        [40.0, 41.0],
    ]


def test_vertical_bayer_line_retains_every_other_source_position() -> None:
    result = selected_bayer_line_profile(
        _rggb_source(),
        LineSelection(0, 0, 0, 3),
        "RGGB",
    )
    assert result.channel_names == ("R", "Gr", "Gb", "B")
    assert [positions.tolist() for positions in result.positions] == [
        [0.0, 2.0],
        [0.0, 2.0],
        [1.0, 3.0],
        [1.0, 3.0],
    ]


def test_bayer_preview_and_channel_views_are_visually_distinct() -> None:
    source = _rggb_source()
    transform = DisplayTransform(display_low=0.0, display_high=1023.0)
    preview = render_bayer_preview(source, "RGGB", (0, 0, 0, 0), 10)
    assert preview.shape == (4, 4, 3)
    assert np.all(preview[..., 1] >= preview[..., 0])
    document = ImageDocument.from_array(
        source,
        "raw",
        channel_layout="BAYER",
        bit_depth=10,
        raw_profile=_profile(),
        display_transform=transform,
        prepared_preview=preview,
    )
    views = split_document_channels(document)
    assert [view.channel_layout for view in views] == [
        "CHANNEL_R",
        "CHANNEL_Gr",
        "CHANNEL_Gb",
        "CHANNEL_B",
    ]
    assert all(view.shape == (2, 2) for view in views)

    rgb = ImageDocument.from_array(
        np.dstack(
            (
                np.full((3, 5), 10, dtype=np.uint8),
                np.full((3, 5), 20, dtype=np.uint8),
                np.full((3, 5), 30, dtype=np.uint8),
            )
        ),
        "rgb",
    )
    rgb_views = split_document_channels(rgb)
    assert [view.channel_layout for view in rgb_views] == [
        "CHANNEL_R",
        "CHANNEL_G",
        "CHANNEL_B",
    ]
    assert all(view.shape == (3, 5) for view in rgb_views)
