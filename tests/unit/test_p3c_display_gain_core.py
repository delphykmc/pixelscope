from __future__ import annotations

import numpy as np
import pytest

from pixelscope.core import display_transform as display_transform_module
from pixelscope.core.diff_engine import (
    compact_absolute_difference,
    normalized_absolute_difference,
)
from pixelscope.core.display_transform import (
    DisplayTransform,
    render_ordinary_display_preview,
    to_display_uint8,
)
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineSelection, selected_line_profile
from pixelscope.core.statistics import histogram, image_statistics


def test_gray_anchor_zero_gain_known_values_clipping_and_source_identity() -> None:
    source = np.array([[0, 32, 64, 100, 255]], dtype=np.uint8)
    original = source.copy()
    document = ImageDocument.from_array(source, "gray", channel_layout="GRAY")
    assert document.preview is not None

    preview = render_ordinary_display_preview(
        source,
        channel_layout="GRAY",
        transform=document.display_transform,
        canonical_preview=document.preview,
        gain=4.0,
    )

    assert preview.tolist() == [[0, 128, 255, 255, 255]]
    assert np.array_equal(source, original)
    assert document.source is source


def test_rgb_anchor_zero_gain_is_channel_uniform_and_source_is_unchanged() -> None:
    source = np.array([[[10, 20, 30], [60, 90, 120]]], dtype=np.uint8)
    original = source.copy()
    document = ImageDocument.from_array(source, "rgb", channel_layout="RGB")
    assert document.preview is not None

    preview = render_ordinary_display_preview(
        source,
        channel_layout="RGB",
        transform=document.display_transform,
        canonical_preview=document.preview,
        gain=2.0,
    )

    assert np.array_equal(
        preview,
        np.array([[[20, 40, 60], [120, 180, 240]]], dtype=np.uint8),
    )
    assert np.array_equal(source, original)


def test_ordinary_gain_one_returns_canonical_preview_object_without_arithmetic() -> None:
    source = np.arange(12, dtype=np.uint8).reshape(2, 2, 3)
    document = ImageDocument.from_array(source, "rgb", channel_layout="RGB")
    assert document.preview is not None

    preview = render_ordinary_display_preview(
        source,
        channel_layout="RGB",
        transform=document.display_transform,
        canonical_preview=document.preview,
        gain=1.0,
    )

    assert preview is document.preview


def test_rgba_gain_preserves_canonical_alpha_and_only_converts_rgb_view(
    monkeypatch: object,
) -> None:
    source = np.array([[[10, 20, 30, 77], [100, 70, 65, 201]]], dtype=np.uint8)
    original = source.copy()
    document = ImageDocument.from_array(source, "rgba", channel_layout="RGBA")
    assert document.preview is not None
    canonical_alpha = document.preview[..., 3].copy()
    converted_shapes: list[tuple[int, ...]] = []
    original_converter = display_transform_module.to_display_uint8

    def spy_converter(
        values: np.ndarray,
        transform: DisplayTransform | None = None,
    ) -> np.ndarray:
        converted_shapes.append(values.shape)
        return original_converter(values, transform)

    monkeypatch.setattr(  # type: ignore[attr-defined]
        display_transform_module,
        "to_display_uint8",
        spy_converter,
    )

    preview = render_ordinary_display_preview(
        source,
        channel_layout="RGBA",
        transform=document.display_transform,
        canonical_preview=document.preview,
        gain=4.0,
    )

    assert converted_shapes == [(1, 2, 3)]
    assert np.array_equal(preview[..., 3], canonical_alpha)
    assert preview[0, 0, :3].tolist() == [40, 80, 120]
    assert preview[0, 1, :3].tolist() == [255, 255, 255]
    assert np.array_equal(source, original)


def test_split_rgb_channel_gain_keeps_colored_presentation_and_native_plane() -> None:
    source = np.array([[10, 100]], dtype=np.uint8)
    original = source.copy()
    canonical = np.zeros((1, 2, 3), dtype=np.uint8)
    canonical[..., 0] = source

    preview = render_ordinary_display_preview(
        source,
        channel_layout="CHANNEL_R",
        transform=DisplayTransform(),
        canonical_preview=canonical,
        gain=2.0,
    )

    assert preview[..., 0].tolist() == [[20, 200]]
    assert not np.any(preview[..., 1:])
    assert np.array_equal(source, original)


def test_difference_layout_rejects_generic_display_gain() -> None:
    source = np.array([[1, 2]], dtype=np.uint8)
    canonical = to_display_uint8(source)
    with pytest.raises(ValueError, match="Difference presentation"):
        render_ordinary_display_preview(
            source,
            channel_layout="DIFFERENCE",
            transform=DisplayTransform(),
            canonical_preview=canonical,
            gain=2.0,
        )


def test_ordinary_display_gain_does_not_change_analysis_or_difference_domains() -> None:
    source = np.array(
        [[[10, 20, 30], [40, 50, 60], [70, 80, 90]]],
        dtype=np.uint8,
    )
    peer_same = np.array(
        [[[11, 18, 35], [35, 55, 58], [75, 75, 100]]],
        dtype=np.uint8,
    )
    peer_mixed = peer_same.astype(np.uint16) * np.uint16(4)
    document = ImageDocument.from_array(source, "rgb", channel_layout="RGB", bit_depth=8)
    peer_document = ImageDocument.from_array(
        peer_same,
        "peer",
        channel_layout="RGB",
        bit_depth=8,
    )
    assert document.preview is not None
    original_source = source.copy()
    original_generation = document.generation
    cache_identity_before = tuple(
        sorted(
            (
                (document.document_id, document.generation),
                (peer_document.document_id, peer_document.generation),
            )
        )
    )
    statistics_before = image_statistics(source)
    histogram_before = histogram(source, 256, (0.0, 256.0))
    line_before = selected_line_profile(source, LineSelection(0, 0, 2, 0))
    native_difference_before = compact_absolute_difference(source, peer_same)
    mixed_difference_before = normalized_absolute_difference(source, peer_mixed, 8, 10)

    _ = render_ordinary_display_preview(
        source,
        channel_layout="RGB",
        transform=document.display_transform,
        canonical_preview=document.preview,
        gain=8.0,
    )

    cache_identity_after = tuple(
        sorted(
            (
                (document.document_id, document.generation),
                (peer_document.document_id, peer_document.generation),
            )
        )
    )
    assert cache_identity_after == cache_identity_before
    assert document.generation == original_generation
    assert document.source is source
    assert np.array_equal(source, original_source)
    assert document.pixel_at(0, 0) == (10, 20, 30)
    assert image_statistics(source) == statistics_before
    histogram_after = histogram(source, 256, (0.0, 256.0))
    assert all(
        np.array_equal(after, before)
        for after, before in zip(histogram_after.counts, histogram_before.counts, strict=True)
    )
    assert np.array_equal(histogram_after.edges, histogram_before.edges)
    line_after = selected_line_profile(source, LineSelection(0, 0, 2, 0))
    assert all(
        np.array_equal(after, before)
        for after, before in zip(line_after.values, line_before.values, strict=True)
    )
    assert np.array_equal(compact_absolute_difference(source, peer_same), native_difference_before)
    assert np.array_equal(
        normalized_absolute_difference(source, peer_mixed, 8, 10),
        mixed_difference_before,
    )
