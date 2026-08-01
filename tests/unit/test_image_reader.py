from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from pixelscope.io.image_reader import ImageReadError, read_image


def write_encoded(path: Path, image: np.ndarray) -> None:
    ok, encoded = cv2.imencode(path.suffix, image)
    assert ok
    encoded.tofile(path)


def test_unicode_path_and_bgr_to_rgb(tmp_path: Path) -> None:
    path = tmp_path / "한글 영상.png"
    bgr = np.array([[[30, 20, 10]]], dtype=np.uint8)
    write_encoded(path, bgr)
    document = read_image(path)
    assert document.channel_layout == "RGB"
    assert document.pixel_at(0, 0) == (10, 20, 30)


def test_uint16_gray_png(tmp_path: Path) -> None:
    path = tmp_path / "gray16.png"
    source = np.array([[0, 65535]], dtype=np.uint16)
    write_encoded(path, source)
    document = read_image(path)
    assert document.original_dtype == np.dtype(np.uint16)
    assert document.pixel_at(1, 0) == 65535


def test_bmp_and_invalid_file(tmp_path: Path) -> None:
    bmp = tmp_path / "test.bmp"
    write_encoded(bmp, np.zeros((2, 2), dtype=np.uint8))
    assert read_image(bmp).shape == (2, 2)
    bad = tmp_path / "bad.png"
    bad.write_text("not an image", encoding="utf-8")
    with pytest.raises(ImageReadError, match="not a valid"):
        read_image(bad)


def test_jpeg_is_decoded_and_converted_to_rgb(tmp_path: Path) -> None:
    path = tmp_path / "chart.jpg"
    bgr = np.full((4, 5, 3), (30, 20, 10), dtype=np.uint8)
    write_encoded(path, bgr)
    document = read_image(path)
    assert document.shape == (4, 5, 3)
    assert document.channel_layout == "RGB"
    red, green, blue = document.pixel_at(0, 0)
    assert blue > red
    assert green >= red
