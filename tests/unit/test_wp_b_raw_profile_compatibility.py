from __future__ import annotations

import json
from pathlib import Path

import pytest

from pixelscope.io.path_discovery import (
    RAW_LIKE_IMAGE_SUFFIXES,
    SUPPORTED_IMAGE_FILTER,
    discover_image_inputs,
    discover_registration_inputs,
    image_input_for_path,
    raw_profile_sidecar_for_path,
)
from pixelscope.io.raw_format import minimum_row_bytes
from pixelscope.io.raw_profile import RawProfile


def _write_imgprops(path: Path, **overrides: object) -> None:
    payload: dict[str, object] = {
        "width": 4080,
        "height": 3060,
        "imageType": "BAYER12",
        "pattern": "GBRG",
        "sensorBitWidth": 12,
        "pedestal": 256,
    }
    payload.update(overrides)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_imgprops_maps_supported_bayer_fields_and_ignores_unknown_attributes(
    tmp_path: Path,
) -> None:
    sidecar = tmp_path / "frame.imgprops"
    _write_imgprops(
        sidecar,
        producer="external-camera-stack",
        packing="mipi_raw12",
        stride=999999,
    )

    profile = RawProfile.load_imgprops(sidecar)

    assert profile.width == 4080
    assert profile.height == 3060
    assert profile.channel_layout == "BAYER"
    assert profile.bayer_pattern == "GBRG"
    assert profile.bit_depth == 12
    assert profile.black_level == 256
    assert profile.white_level == 4095
    assert profile.storage_format == "unpacked"
    assert profile.container_dtype == "uint16"
    assert profile.endianness == "little"
    assert profile.bit_alignment == "lsb"
    assert profile.offset_bytes == 0
    assert profile.stride_bytes == 8160


def test_imgprops_rejects_inconsistent_or_incomplete_metadata(tmp_path: Path) -> None:
    mismatch = tmp_path / "mismatch.imgprops"
    _write_imgprops(mismatch, imageType="BAYER10")
    with pytest.raises(ValueError, match="does not match sensorBitWidth"):
        RawProfile.load_imgprops(mismatch)

    incomplete = tmp_path / "incomplete.imgprops"
    _write_imgprops(incomplete)
    payload = json.loads(incomplete.read_text(encoding="utf-8"))
    del payload["pattern"]
    incomplete.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="pattern is required"):
        RawProfile.load_imgprops(incomplete)


def test_imgprops_requires_json_object_and_valid_json(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.imgprops"
    invalid.write_text("not-json", encoding="utf-8")
    with pytest.raises(ValueError, match="Cannot parse .imgprops"):
        RawProfile.load_imgprops(invalid)

    array_root = tmp_path / "array.imgprops"
    array_root.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="root must be a JSON object"):
        RawProfile.load_imgprops(array_root)


def test_raw_sidecar_precedence_is_json_then_imgprops(tmp_path: Path) -> None:
    source = tmp_path / "frame.data"
    source.write_bytes(b"\x00" * 32)
    imgprops = tmp_path / "frame.imgprops"
    json_sidecar = tmp_path / "frame.json"
    _write_imgprops(imgprops, width=4, height=4)
    json_sidecar.write_text("{}", encoding="utf-8")

    assert raw_profile_sidecar_for_path(source) == json_sidecar
    assert image_input_for_path(source) is not None
    assert image_input_for_path(source).raw_profile_path == json_sidecar  # type: ignore[union-attr]

    json_sidecar.unlink()
    assert raw_profile_sidecar_for_path(source) == imgprops
    assert image_input_for_path(source).raw_profile_path == imgprops  # type: ignore[union-attr]


def test_raw_like_extensions_share_discovery_without_affecting_ordinary_images(
    tmp_path: Path,
) -> None:
    paths = [
        tmp_path / "a.raw",
        tmp_path / "b.data",
        tmp_path / "c.yuv",
        tmp_path / "d.png",
        tmp_path / "ignored.txt",
    ]
    for path in paths:
        path.write_bytes(b"payload")

    discovered = discover_image_inputs(paths)

    assert [item.path.name for item in discovered] == ["a.raw", "b.data", "c.yuv", "d.png"]
    assert frozenset({".raw", ".data", ".yuv"}) == RAW_LIKE_IMAGE_SUFFIXES
    assert "*.raw" in SUPPORTED_IMAGE_FILTER
    assert "*.data" in SUPPORTED_IMAGE_FILTER
    assert "*.yuv" in SUPPORTED_IMAGE_FILTER
    assert "*.png" in SUPPORTED_IMAGE_FILTER


def test_registration_discovery_preserves_folder_lazy_and_direct_profile_resolution(
    tmp_path: Path,
) -> None:
    folder = tmp_path / "folder"
    folder.mkdir()
    folder_data = folder / "image2.data"
    folder_yuv = folder / "image10.yuv"
    direct_raw = tmp_path / "direct.raw"
    for path in (folder_data, folder_yuv, direct_raw):
        path.write_bytes(b"binary")

    discovery = discover_registration_inputs((folder, direct_raw))

    assert [record.image_input.path.name for record in discovery.items] == [
        "image2.data",
        "image10.yuv",
        "direct.raw",
    ]
    assert [record.from_folder for record in discovery.items] == [True, True, False]
    assert [record.resolve_raw_profile for record in discovery.items] == [False, False, True]
    assert [record.select_on_complete for record in discovery.items] == [False, False, True]


def test_minimum_stride_uses_storage_specific_row_layout() -> None:
    width = 4080

    assert minimum_row_bytes(width, "unpacked", "uint16") == 8160
    assert minimum_row_bytes(width, "unpacked", "uint8") == 4080
    assert minimum_row_bytes(width, "mipi_raw10", None) == 5100
    assert minimum_row_bytes(width, "mipi_raw12", None) == 6120
    assert minimum_row_bytes(width, "mipi_raw14", None) == 7140
