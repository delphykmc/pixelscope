from __future__ import annotations

import json
from pathlib import Path

import pytest

from pixelscope.io.raw_profile import RawProfile
from pixelscope.io.raw_reader import read_raw

DATASET = Path(__file__).parents[2] / "test_data" / "manual" / "raw_chart_set"


def test_raw_chart_set_manifest_profiles_and_pixels_are_consistent() -> None:
    manifest = json.loads((DATASET / "manifest.json").read_text(encoding="utf-8"))
    entries = manifest["files"]
    assert len(entries) == 10
    missing = [entry["raw"] for entry in entries if not (DATASET / entry["raw"]).is_file()]
    if missing:
        pytest.skip("RAW chart binaries are not installed: " + ", ".join(missing))
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
        profile = RawProfile.load_json(profile_path)
        image = read_raw(raw_path, profile)
        assert image.shape == (1080, 1920)
        assert int(image.min()) == entry["minimum"]
        assert int(image.max()) == entry["maximum"]
        assert profile.minimum_row_bytes == entry["stride_bytes"]
