from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image
from scripts.run_ui_capture_poc import changed_fraction, validate_capture


def _pattern(path: Path) -> None:
    image = Image.new("RGB", (500, 400))
    pixels = image.load()
    assert pixels is not None
    for y in range(400):
        for x in range(500):
            pixels[x, y] = (x % 256, y % 256, (x + y) % 256)
    image.save(path)


def _metadata(path: Path, image: Path, source_sha: str) -> None:
    path.write_text(
        json.dumps(
            {
                "status": "captured",
                "scenario": "single_image",
                "source_sha": source_sha,
                "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
                "geometry": {"pixel_png": [500, 400], "logical_widget": [500, 400]},
            }
        ),
        encoding="utf-8",
    )


def test_poc_validator_requires_decodable_nonblank_png_and_exact_identity(tmp_path: Path) -> None:
    png, metadata = tmp_path / "capture.png", tmp_path / "capture.json"
    sha = "1" * 40
    _pattern(png)
    _metadata(metadata, png, sha)
    assert validate_capture(png, metadata, "single_image", sha)["status"] == "captured"

    pinned = json.loads(metadata.read_text(encoding="utf-8"))
    pinned["capture_profile"] = "windows-e1-poc-v1"
    metadata.write_text(json.dumps(pinned), encoding="utf-8")
    with pytest.raises(ValueError, match="pinned capture profile"):
        validate_capture(png, metadata, "single_image", sha)
    pinned.pop("capture_profile")
    metadata.write_text(json.dumps(pinned), encoding="utf-8")

    with pytest.raises(ValueError, match="source SHA mismatch"):
        validate_capture(png, metadata, "single_image", "2" * 40)

    Image.new("RGB", (500, 400), (20, 20, 20)).save(png)
    _metadata(metadata, png, sha)
    with pytest.raises(ValueError, match="insufficient pixel variation"):
        validate_capture(png, metadata, "single_image", sha)

    png.write_bytes(b"not a PNG")
    _metadata(metadata, png, sha)
    with pytest.raises(OSError):
        validate_capture(png, metadata, "single_image", sha)


def test_poc_repeatability_is_exact_pixel_not_png_metadata(tmp_path: Path) -> None:
    first, second = tmp_path / "first.png", tmp_path / "second.png"
    _pattern(first)
    _pattern(second)
    assert changed_fraction(first, second) == 0
    with Image.open(second) as opened:
        changed = opened.copy()
    changed.putpixel((20, 20), (1, 2, 3))
    changed.save(second)
    assert 0 < changed_fraction(first, second) < 0.01
    Image.new("RGB", (450, 400)).save(second)
    assert changed_fraction(first, second) == 1.0
