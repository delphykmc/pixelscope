from __future__ import annotations

import numpy as np
import pytest

from pixelscope.core.bayer import BAYER_CHANNEL_NAMES, bayer_channel_positions
from pixelscope.core.channel_views import split_document_channels
from pixelscope.core.diff_engine import compact_absolute_difference, normalized_absolute_difference
from pixelscope.core.display_transform import DisplayTransform, to_display_uint8
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineSelection, selected_line_profile
from pixelscope.core.raw_display import raw_display_transform, raw_full_scale, render_raw_preview
from pixelscope.core.statistics import histogram, image_statistics
from pixelscope.io.raw_profile import RawProfile


def _gray_profile(*, white_level: int = 3800) -> RawProfile:
    return RawProfile(
        name="raw12-gray",
        width=5,
        height=1,
        stride_bytes=10,
        bit_depth=12,
        channel_layout="GRAY",
        black_level=64,
        white_level=white_level,
    )


@pytest.mark.parametrize("bit_depth", [10, 12, 14])
def test_raw_native_preview_uses_effective_full_scale(bit_depth: int) -> None:
    full_scale = raw_full_scale(bit_depth)
    source = np.array([[0, full_scale]], dtype=np.uint16)
    preview = render_raw_preview(
        source,
        channel_layout="GRAY",
        bit_depth=bit_depth,
        black_level=64,
        gain=1.0,
    )
    assert preview.tolist() == [[0, 255]]


def test_gain_one_does_not_redefine_black_or_white_as_display_endpoints() -> None:
    profile = _gray_profile(white_level=3800)
    source = np.array([[0, 64, profile.white_level, 4095]], dtype=np.uint16)
    preview = render_raw_preview(
        source,
        channel_layout=profile.channel_layout,
        bit_depth=profile.bit_depth,
        black_level=profile.black_level,
        gain=1.0,
    )
    expected = np.rint(source.astype(np.float32) * np.float32(255.0 / 4095.0)).astype(np.uint8)
    assert np.array_equal(preview, expected)
    assert int(preview[0, 1]) > 0
    assert int(preview[0, 2]) < 255


def test_white_level_metadata_does_not_change_p3b_preview() -> None:
    first = _gray_profile(white_level=3800)
    second = _gray_profile(white_level=4000)
    source = np.array([[0, 64, 1024, 2048, 4095]], dtype=np.uint16)

    previews = [
        render_raw_preview(
            source,
            channel_layout=profile.channel_layout,
            bit_depth=profile.bit_depth,
            black_level=profile.black_level,
            gain=4.0,
        )
        for profile in (first, second)
    ]
    assert np.array_equal(previews[0], previews[1])


def test_black_anchored_gain_matches_known_values_and_does_not_underflow() -> None:
    source = np.array([[60, 63, 64, 65, 70]], dtype=np.uint16)
    original = source.copy()
    transform = raw_display_transform(12, 64, 4.0)
    preview = to_display_uint8(source, transform)

    gained = np.array([[48, 60, 64, 68, 88]], dtype=np.float32)
    expected = np.rint(np.clip(gained / np.float32(4095.0), 0.0, 1.0) * 255.0).astype(
        np.uint8
    )
    assert np.array_equal(preview, expected)
    assert np.array_equal(source, original)

    below_black = np.array([[0, 60]], dtype=np.uint16)
    below_preview = to_display_uint8(below_black, transform)
    assert below_preview.tolist() == [[0, 3]]


def test_gain_clips_only_at_final_display_conversion() -> None:
    source = np.array([[0, 64, 4095]], dtype=np.uint16)
    transform = DisplayTransform(
        display_low=0.0,
        display_high=4095.0,
        gain=4.0,
        gain_anchor=64.0,
    )
    preview = to_display_uint8(source, transform)
    assert preview[0, 0] == 0
    assert preview[0, 1] == round(64 * 255 / 4095)
    assert preview[0, 2] == 255


@pytest.mark.parametrize("pattern", ["RGGB", "GRBG", "GBRG", "BGGR"])
def test_bayer_tuple_black_anchor_follows_cfa_parity_without_source_mutation(pattern: str) -> None:
    anchors = (64, 72, 80, 96)
    source = np.zeros((4, 4), dtype=np.uint16)
    positions = bayer_channel_positions(pattern)
    expected_gained = np.zeros((4, 4), dtype=np.float32)
    for name, anchor in zip(BAYER_CHANNEL_NAMES, anchors):
        row, column = positions[name]
        source[row::2, column::2] = anchor + 1
        expected_gained[row::2, column::2] = anchor + 4
    original = source.copy()

    preview = render_raw_preview(
        source,
        channel_layout="BAYER",
        bit_depth=12,
        black_level=anchors,
        bayer_pattern=pattern,
        gain=4.0,
    )
    expected_gray = np.rint(expected_gained * np.float32(255.0 / 4095.0)).astype(np.uint8)
    assert np.array_equal(preview[..., 1], expected_gray)
    assert np.array_equal(source, original)


def test_bayer_split_channel_uses_its_named_black_anchor() -> None:
    source = np.array([[73, 74]], dtype=np.uint16)
    preview = render_raw_preview(
        source,
        channel_layout="CHANNEL_Gr",
        bit_depth=12,
        black_level=(64, 72, 80, 96),
        gain=4.0,
    )
    expected = np.rint(np.array([[76, 80]], dtype=np.float32) * (255.0 / 4095.0)).astype(
        np.uint8
    )
    assert np.array_equal(preview, expected)


def test_display_gain_leaves_native_analysis_and_difference_inputs_unchanged() -> None:
    profile = _gray_profile()
    source_a = np.array([[60, 64, 70, 512, 1023]], dtype=np.uint16)
    source_b = np.array([[64, 64, 80, 500, 900]], dtype=np.uint16)
    document = ImageDocument.from_array(
        source_a,
        "raw",
        channel_layout="GRAY",
        bit_depth=12,
        raw_profile=profile,
        display_transform=DisplayTransform(display_low=0.0, display_high=4095.0),
        prepared_preview=render_raw_preview(
            source_a,
            channel_layout="GRAY",
            bit_depth=12,
            black_level=profile.black_level,
        ),
    )
    original_source = source_a.copy()
    original_generation = document.generation
    original_nbytes = source_a.nbytes
    statistics_before = image_statistics(source_a)
    histogram_before = histogram(source_a, 4096, (0.0, 4096.0))
    line_before = selected_line_profile(source_a, LineSelection(0, 0, 4, 0))
    native_difference_before = compact_absolute_difference(source_a, source_b)
    normalized_difference_before = normalized_absolute_difference(source_a, source_b, 12, 10)

    _ = render_raw_preview(
        document.source,
        channel_layout="GRAY",
        bit_depth=12,
        black_level=profile.black_level,
        gain=8.0,
    )

    statistics_after = image_statistics(source_a)
    histogram_after = histogram(source_a, 4096, (0.0, 4096.0))
    line_after = selected_line_profile(source_a, LineSelection(0, 0, 4, 0))
    native_difference_after = compact_absolute_difference(source_a, source_b)
    normalized_difference_after = normalized_absolute_difference(source_a, source_b, 12, 10)

    assert document.generation == original_generation
    assert document.source is not None
    assert document.source.nbytes == original_nbytes
    assert np.array_equal(document.source, original_source)
    assert document.pixel_at(0, 0) == 60
    assert statistics_after == statistics_before
    assert np.array_equal(histogram_after.counts[0], histogram_before.counts[0])
    assert np.array_equal(histogram_after.edges, histogram_before.edges)
    assert np.array_equal(line_after.values[0], line_before.values[0])
    assert np.array_equal(native_difference_after, native_difference_before)
    assert np.array_equal(normalized_difference_after, normalized_difference_before)


def test_split_channels_remain_native_when_bayer_display_gain_changes() -> None:
    profile = RawProfile(
        name="split",
        width=4,
        height=4,
        stride_bytes=8,
        bit_depth=12,
        channel_layout="BAYER",
        bayer_pattern="RGGB",
        black_level=(64, 72, 80, 96),
        white_level=3800,
    )
    source = np.arange(16, dtype=np.uint16).reshape(4, 4) + np.uint16(100)
    document = ImageDocument.from_array(
        source,
        "split",
        channel_layout="BAYER",
        bit_depth=12,
        raw_profile=profile,
        display_transform=DisplayTransform(display_low=0.0, display_high=4095.0),
        prepared_preview=render_raw_preview(
            source,
            channel_layout="BAYER",
            bit_depth=12,
            black_level=profile.black_level,
            bayer_pattern="RGGB",
        ),
    )
    before = split_document_channels(document)
    expected = [channel.source.copy() for channel in before if channel.source is not None]

    _ = render_raw_preview(
        source,
        channel_layout="BAYER",
        bit_depth=12,
        black_level=profile.black_level,
        bayer_pattern="RGGB",
        gain=4.0,
    )
    after = split_document_channels(document)

    assert [channel.channel_layout for channel in after] == [
        "CHANNEL_R",
        "CHANNEL_Gr",
        "CHANNEL_Gb",
        "CHANNEL_B",
    ]
    assert all(channel.source is not None for channel in after)
    for channel, expected_source in zip(after, expected, strict=True):
        assert channel.source is not None
        assert np.array_equal(channel.source, expected_source)


def test_standard_uint8_display_behavior_is_unchanged() -> None:
    source = np.array([[0, 64, 128, 255]], dtype=np.uint8)
    assert np.array_equal(to_display_uint8(source), source)
