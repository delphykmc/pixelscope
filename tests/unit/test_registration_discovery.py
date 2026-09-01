from __future__ import annotations

from pathlib import Path

import pytest

from pixelscope.io import path_discovery
from pixelscope.io.path_discovery import discover_registration_inputs


def test_discover_image_inputs_sorts_each_result_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for index in range(1, 41):
        (tmp_path / f"image{index}.png").write_bytes(b"x")

    original = path_discovery.natural_sort_key
    calls = 0

    def counting_key(path: Path) -> tuple[object, ...]:
        nonlocal calls
        calls += 1
        return original(path)

    monkeypatch.setattr(path_discovery, "natural_sort_key", counting_key)
    inputs = path_discovery.discover_image_inputs((tmp_path,))

    assert len(inputs) == 40
    assert calls == len(inputs)
    assert [item.path.name for item in inputs[:3]] == ["image1.png", "image2.png", "image3.png"]
    assert inputs[-1].path.name == "image40.png"


def test_registration_discovery_computes_trusted_metadata_and_sort_keys_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for index in range(1, 41):
        (tmp_path / f"image{index}.png").write_bytes(b"x")

    original = path_discovery.natural_sort_key
    calls = 0

    def counting_key(path: Path) -> tuple[object, ...]:
        nonlocal calls
        calls += 1
        return original(path)

    monkeypatch.setattr(path_discovery, "natural_sort_key", counting_key)
    result = discover_registration_inputs((tmp_path,))

    assert len(result.items) == 40
    assert calls == len(result.items)
    for record in result.items:
        assert record.canonical_path_key == str(record.image_input.path).casefold()
        assert record.canonical_folder_path == tmp_path.resolve()
        assert record.canonical_folder_key == str(tmp_path.resolve()).casefold()
        assert record.sort_key == original(record.image_input.path)


def test_registration_discovery_preserves_folder_then_direct_intent(tmp_path: Path) -> None:
    folder_a = tmp_path / "a"
    folder_b = tmp_path / "b"
    empty = tmp_path / "empty"
    for folder in (folder_a, folder_b, empty):
        folder.mkdir()
    for folder in (folder_a, folder_b):
        for name in ("image10.png", "image2.png"):
            (folder / name).write_bytes(b"x")

    explicit_duplicate = folder_a / "image2.png"
    result = discover_registration_inputs(
        (folder_b, folder_a, empty, folder_a, explicit_duplicate, explicit_duplicate)
    )

    assert result.folder_count == 3
    assert result.empty_folder_count == 1
    assert result.registered_folders == (folder_a.resolve(), folder_b.resolve())
    assert [record.image_input.path for record in result.items] == [
        (folder_a / "image2.png").resolve(),
        (folder_a / "image10.png").resolve(),
        (folder_b / "image2.png").resolve(),
        (folder_b / "image10.png").resolve(),
        explicit_duplicate.resolve(),
    ]
    assert all(record.from_folder for record in result.items[:4])
    assert all(not record.resolve_raw_profile for record in result.items[:4])
    assert all(not record.select_on_complete for record in result.items[:4])
    assert not result.items[-1].from_folder
    assert result.items[-1].resolve_raw_profile
    assert result.items[-1].select_on_complete


def test_registration_discovery_observes_cooperative_checkpoint(tmp_path: Path) -> None:
    (tmp_path / "image1.png").write_bytes(b"x")

    class Cancelled(RuntimeError):
        pass

    def cancel() -> None:
        raise Cancelled

    with pytest.raises(Cancelled):
        discover_registration_inputs((tmp_path,), checkpoint=cancel)