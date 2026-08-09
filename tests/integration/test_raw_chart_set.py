from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from numpy.typing import NDArray

from pixelscope.core.bayer import render_bayer_preview
from pixelscope.core.display_transform import DisplayTransform, to_display_uint8
from pixelscope.io.image_reader import read_image
from pixelscope.io.path_discovery import discover_image_inputs
from pixelscope.io.raw_profile import RawProfile
from pixelscope.io.raw_reader import read_raw

DATASET = Path(__file__).parents[2] / "test_data" / "manual" / "raw_chart_set"
COVERAGE_PATCH_SIZE = 256
EXPECTED_RAW_ORDER = [
    "01_gray_08bit_u8.raw",
    "01_gray_10bit_u16le_lsb.raw",
    "01_gray_12bit_u16le_lsb.raw",
    "01_gray_14bit_u16le_lsb.raw",
    "01_gray_16bit_u16le.raw",
    "02_bayer_10bit_01_rggb_u16le_lsb.raw",
    "02_bayer_10bit_02_rggb_mipi_raw10.raw",
    "02_bayer_12bit_01_rggb_u16le_msb.raw",
    "02_bayer_12bit_02_rggb_mipi_raw12.raw",
    "02_bayer_14bit_01_rggb_mipi_raw14.raw",
]


def _manifest() -> dict[str, Any]:
    return json.loads((DATASET / "manifest.json").read_text(encoding="utf-8"))


def _entry_by_raw(manifest: dict[str, Any], raw_name: str) -> dict[str, Any]:
    return next(entry for entry in manifest["files"] if entry["raw"] == raw_name)


def _load_entry(entry: dict[str, Any]) -> NDArray[np.generic]:
    profile = RawProfile.load_json(DATASET / entry["profile"])
    return read_raw(DATASET / entry["raw"], profile)


def _require_binaries(entries: list[dict[str, Any]]) -> None:
    missing = [entry["raw"] for entry in entries if not (DATASET / entry["raw"]).is_file()]
    if missing:
        pytest.skip("RAW chart binaries are not installed: " + ", ".join(missing))


def _sample_rggb(rgb: NDArray[np.float64]) -> NDArray[np.float64]:
    mosaic = np.empty(rgb.shape[:2], dtype=np.float64)
    mosaic[0::2, 0::2] = rgb[0::2, 0::2, 0]
    mosaic[0::2, 1::2] = rgb[0::2, 1::2, 1]
    mosaic[1::2, 0::2] = rgb[1::2, 0::2, 1]
    mosaic[1::2, 1::2] = rgb[1::2, 1::2, 2]
    return mosaic


def test_raw_chart_set_natural_sort_keeps_gray_before_bayer() -> None:
    discovered = discover_image_inputs((DATASET,))
    assert [item.path.name for item in discovered] == EXPECTED_RAW_ORDER
    assert all(item.raw_profile_path is not None for item in discovered)


def test_raw_chart_set_manifest_profiles_and_pixels_are_consistent() -> None:
    manifest = _manifest()
    entries = manifest["files"]
    assert len(entries) == 10
    assert [entry["raw"] for entry in entries] == EXPECTED_RAW_ORDER
    _require_binaries(entries)
    assert manifest["bayer_chart_version"] == 3
    assert manifest["references"]["coverage_patch"]["size"] == COVERAGE_PATCH_SIZE
    assert {
        (entry["storage_format"], entry["bit_depth"], entry["channel_layout"])
        for entry in entries
        if entry["channel_layout"] == "BAYER"
    } == {
        ("unpacked", 10, "BAYER"),
        ("unpacked", 12, "BAYER"),
        ("mipi_raw10", 10, "BAYER"),
        ("mipi_raw12", 12, "BAYER"),
        ("mipi_raw14", 14, "BAYER"),
    }

    for entry in entries:
        raw_path = DATASET / entry["raw"]
        profile_path = DATASET / entry["profile"]
        assert raw_path.is_file()
        assert profile_path.is_file()
        assert raw_path.stem == profile_path.stem
        assert hashlib.sha256(raw_path.read_bytes()).hexdigest() == entry["sha256"]
        profile = RawProfile.load_json(profile_path)
        image = read_raw(raw_path, profile)
        assert image.shape == (1080, 1920)
        assert int(image.min()) == entry["minimum"]
        assert int(image.max()) == entry["maximum"]
        assert profile.minimum_row_bytes == entry["stride_bytes"]


def test_unpacked_and_mipi_variants_decode_to_identical_bayer_mosaics() -> None:
    manifest = _manifest()
    raw10_unpacked_entry = _entry_by_raw(
        manifest,
        "02_bayer_10bit_01_rggb_u16le_lsb.raw",
    )
    raw10_mipi_entry = _entry_by_raw(
        manifest,
        "02_bayer_10bit_02_rggb_mipi_raw10.raw",
    )
    raw12_unpacked_entry = _entry_by_raw(
        manifest,
        "02_bayer_12bit_01_rggb_u16le_msb.raw",
    )
    raw12_mipi_entry = _entry_by_raw(
        manifest,
        "02_bayer_12bit_02_rggb_mipi_raw12.raw",
    )
    entries = [
        raw10_unpacked_entry,
        raw10_mipi_entry,
        raw12_unpacked_entry,
        raw12_mipi_entry,
    ]
    _require_binaries(entries)

    np.testing.assert_array_equal(
        _load_entry(raw10_unpacked_entry),
        _load_entry(raw10_mipi_entry),
    )
    np.testing.assert_array_equal(
        _load_entry(raw12_unpacked_entry),
        _load_entry(raw12_mipi_entry),
    )


def test_bayer_bit_depth_variants_share_the_same_normalized_scene() -> None:
    manifest = _manifest()
    entries = [
        _entry_by_raw(manifest, "02_bayer_10bit_02_rggb_mipi_raw10.raw"),
        _entry_by_raw(manifest, "02_bayer_12bit_02_rggb_mipi_raw12.raw"),
        _entry_by_raw(manifest, "02_bayer_14bit_01_rggb_mipi_raw14.raw"),
    ]
    _require_binaries(entries)
    decoded = [_load_entry(entry).astype(np.float64) for entry in entries]
    normalized = [
        image / float((1 << entry["bit_depth"]) - 1)
        for image, entry in zip(decoded, entries, strict=True)
    ]
    scene_mask = np.ones(normalized[0].shape, dtype=bool)
    scene_mask[-COVERAGE_PATCH_SIZE:, -COVERAGE_PATCH_SIZE:] = False

    np.testing.assert_allclose(
        normalized[0][scene_mask],
        normalized[1][scene_mask],
        atol=(1.0 / 1023.0) + (1.0 / 4095.0),
        rtol=0.0,
    )
    np.testing.assert_allclose(
        normalized[1][scene_mask],
        normalized[2][scene_mask],
        atol=(1.0 / 4095.0) + (1.0 / 16383.0),
        rtol=0.0,
    )


def test_bayer_main_scene_is_sampled_from_the_true_rgb_reference() -> None:
    manifest = _manifest()
    references = manifest["references"]
    raw14_entry = _entry_by_raw(
        manifest,
        "02_bayer_14bit_01_rggb_mipi_raw14.raw",
    )
    _require_binaries([raw14_entry])

    source_rgb = read_image(DATASET / references["source_rgb"])
    assert source_rgb.source is not None
    rgb = source_rgb.source.astype(np.float64) / 255.0
    expected_mosaic = _sample_rggb(rgb)
    actual_mosaic = _load_entry(raw14_entry).astype(np.float64) / 16383.0
    scene_mask = np.ones(actual_mosaic.shape, dtype=bool)
    scene_mask[-COVERAGE_PATCH_SIZE:, -COVERAGE_PATCH_SIZE:] = False

    np.testing.assert_allclose(
        actual_mosaic[scene_mask],
        expected_mosaic[scene_mask],
        atol=(1.0 / 255.0) + (1.0 / 16383.0),
        rtol=0.0,
    )


def test_bayer_code_coverage_patch_is_complete_and_cfa_neutral() -> None:
    manifest = _manifest()
    entries = [
        entry
        for entry in manifest["files"]
        if entry["channel_layout"] == "BAYER"
        and entry["storage_format"] in {"mipi_raw10", "mipi_raw12", "mipi_raw14"}
    ]
    _require_binaries(entries)

    for entry in entries:
        patch = _load_entry(entry)[-COVERAGE_PATCH_SIZE:, -COVERAGE_PATCH_SIZE:]
        top_left = patch[0::2, 0::2]
        np.testing.assert_array_equal(top_left, patch[0::2, 1::2])
        np.testing.assert_array_equal(top_left, patch[1::2, 0::2])
        np.testing.assert_array_equal(top_left, patch[1::2, 1::2])
        assert np.unique(patch).size == 1 << entry["bit_depth"]


def test_bayer_reference_images_match_the_decoded_raw_preview() -> None:
    manifest = _manifest()
    references = manifest["references"]
    raw14_entry = _entry_by_raw(
        manifest,
        "02_bayer_14bit_01_rggb_mipi_raw14.raw",
    )
    _require_binaries([raw14_entry])
    raw14_profile = RawProfile.load_json(DATASET / raw14_entry["profile"])
    raw14 = read_raw(DATASET / raw14_entry["raw"], raw14_profile)
    transform = DisplayTransform(
        display_low=0.0,
        display_high=float((1 << raw14_profile.bit_depth) - 1),
    )

    source_rgb = read_image(DATASET / references["source_rgb"])
    mosaic_gray = read_image(DATASET / references["mosaic_gray"])
    pixelscope_preview = read_image(DATASET / references["pixelscope_preview"])
    assert source_rgb.source is not None
    assert mosaic_gray.source is not None
    assert pixelscope_preview.source is not None
    assert source_rgb.source.shape == (1080, 1920, 3)
    np.testing.assert_array_equal(
        mosaic_gray.source,
        to_display_uint8(raw14, transform),
    )
    np.testing.assert_array_equal(
        pixelscope_preview.source,
        render_bayer_preview(
            raw14,
            raw14_profile.bayer_pattern or "RGGB",
            raw14_profile.black_level,
            raw14_profile.bit_depth,
        ),
    )
