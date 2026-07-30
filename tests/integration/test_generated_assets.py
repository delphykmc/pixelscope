from __future__ import annotations

from pathlib import Path

from scripts.generate_test_images import generate

from pixelscope.io.image_reader import read_image, read_raw_document


def test_generated_assets_can_be_loaded(tmp_path: Path) -> None:
    generated = generate(tmp_path)
    names = {path.name for path in generated}
    assert "한글_경로_영상.png" in names
    assert read_image(tmp_path / "gray_u8.bmp").shape == (128, 256)
    assert read_image(tmp_path / "gray_u16.png").bit_depth == 16
    raw = read_raw_document(tmp_path / "unpacked_u16.raw", tmp_path / "unpacked_u16.json")
    assert raw.shape == (240, 320)
    assert raw.pixel_at(319, 0) == 65535
