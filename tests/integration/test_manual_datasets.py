from __future__ import annotations

from pathlib import Path

from pixelscope.io.image_reader import read_image
from pixelscope.io.path_discovery import discover_image_inputs

FHD = Path(__file__).parents[2] / "test_data" / "manual" / "fhd_chart_set"


def test_fhd_chart_folders_are_complete_and_naturally_aligned() -> None:
    folders = [FHD / "base", FHD / "variation_noise", FHD / "variation_tone"]
    discovered = [discover_image_inputs((folder,)) for folder in folders]

    assert [len(items) for items in discovered] == [10, 10, 10]
    assert all(
        item.path.suffix.casefold() == ".jpg"
        for items in discovered
        for item in items
    )
    baseline_names = [item.path.name for item in discovered[0]]
    assert [item.path.name for item in discovered[1]] == baseline_names
    assert [item.path.name for item in discovered[2]] == baseline_names

    document = read_image(discovered[0][0].path)
    assert document.shape == (1080, 1920, 3)
    assert document.channel_layout == "RGB"
