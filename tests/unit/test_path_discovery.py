from __future__ import annotations

from pathlib import Path

from pixelscope.io.path_discovery import (
    SUPPORTED_IMAGE_FILTER,
    SUPPORTED_IMAGE_SUFFIXES,
    discover_image_inputs,
)


def test_supported_image_contract_matches_unified_picker() -> None:
    assert SUPPORTED_IMAGE_SUFFIXES == {".png", ".bmp", ".jpg", ".jpeg", ".raw"}
    assert SUPPORTED_IMAGE_FILTER == "Supported Images (*.png *.bmp *.jpg *.jpeg *.raw)"
    assert "*.*" not in SUPPORTED_IMAGE_FILTER


def test_folder_discovery_is_natural_sorted_and_filters_files(tmp_path: Path) -> None:
    for name in (
        "image10.png",
        "image2.bmp",
        "image1.jpg",
        "image3.jpeg",
        "notes.txt",
        "profile.json",
        "preview.tiff",
    ):
        (tmp_path / name).write_bytes(b"x")
    inputs = discover_image_inputs((tmp_path,))
    assert [item.path.name for item in inputs] == [
        "image1.jpg",
        "image2.bmp",
        "image3.jpeg",
        "image10.png",
    ]


def test_raw_sidecar_is_optional_and_discovered_when_present(tmp_path: Path) -> None:
    (tmp_path / "with.raw").write_bytes(b"x")
    (tmp_path / "with.json").write_text("{}", encoding="utf-8")
    (tmp_path / "without.raw").write_bytes(b"x")
    inputs = discover_image_inputs((tmp_path,))
    assert [item.path.name for item in inputs] == ["with.raw", "without.raw"]
    assert inputs[0].raw_profile_path == tmp_path / "with.json"
    assert inputs[1].raw_profile_path is None
