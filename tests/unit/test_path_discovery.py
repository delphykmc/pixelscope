from __future__ import annotations

from pathlib import Path

from pixelscope.io.path_discovery import discover_image_inputs, pair_folders


def test_folder_discovery_is_natural_sorted_and_filters_files(tmp_path: Path) -> None:
    for name in ("image10.png", "image2.bmp", "image1.png", "notes.txt"):
        (tmp_path / name).write_bytes(b"x")
    inputs = discover_image_inputs((tmp_path,))
    assert [item.path.name for item in inputs] == ["image1.png", "image2.bmp", "image10.png"]


def test_raw_sidecar_is_optional_and_discovered_when_present(tmp_path: Path) -> None:
    (tmp_path / "with.raw").write_bytes(b"x")
    (tmp_path / "with.json").write_text("{}", encoding="utf-8")
    (tmp_path / "without.raw").write_bytes(b"x")
    inputs = discover_image_inputs((tmp_path,))
    assert [item.path.name for item in inputs] == ["with.raw", "without.raw"]
    assert inputs[0].raw_profile_path == tmp_path / "with.json"
    assert inputs[1].raw_profile_path is None


def test_two_folders_pair_by_natural_sort_position(tmp_path: Path) -> None:
    folder_a, folder_b = tmp_path / "a", tmp_path / "b"
    folder_a.mkdir()
    folder_b.mkdir()
    for name in ("a10.png", "a2.png"):
        (folder_a / name).write_bytes(b"x")
    for name in ("b01.png", "b02.png", "b03.png"):
        (folder_b / name).write_bytes(b"x")
    pairs = pair_folders(folder_a, folder_b)
    assert [(a.path.name, b.path.name) for a, b in pairs] == [
        ("a2.png", "b01.png"),
        ("a10.png", "b02.png"),
    ]
