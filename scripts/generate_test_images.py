from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray


def _write_image(path: Path, image: NDArray[np.generic]) -> None:
    suffix = path.suffix.lower()
    encoded_image = image
    if image.ndim == 3 and image.shape[2] == 3:
        encoded_image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    success, encoded = cv2.imencode(suffix, encoded_image)
    if not success:
        raise RuntimeError(f"OpenCV could not encode {path.name}")
    encoded.tofile(path)


def generate(output: Path) -> list[Path]:
    """Create deterministic, non-business test assets and return their paths."""

    output.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    gray = np.tile(np.arange(256, dtype=np.uint8), (128, 1))
    rgb = np.stack((gray, np.flip(gray, axis=1), np.full_like(gray, 96)), axis=-1)
    gray16 = np.tile(np.linspace(0, 65535, 320, dtype=np.uint16), (240, 1))
    a = np.tile(np.arange(64, dtype=np.uint8), (64, 1))
    b = np.clip(a.astype(np.int16) + 7, 0, 255).astype(np.uint8)
    extreme = np.array([[0, 65535], [65535, 0]], dtype=np.uint16)
    mismatch = np.zeros((33, 65), dtype=np.uint8)

    for name, image in (
        ("gray_u8_gradient.png", gray),
        ("rgb_pattern.png", rgb),
        ("gray_u16.png", gray16),
        ("compare_a.png", a),
        ("compare_b_offset_7.png", b),
        ("uint16_extremes.png", extreme),
        ("shape_mismatch.png", mismatch),
        ("한글_경로_영상.png", rgb),
        ("gray_u8.bmp", gray),
    ):
        path = output / name
        _write_image(path, image)
        created.append(path)

    raw_path = output / "unpacked_u16.raw"
    gray16.astype("<u2").tofile(raw_path)
    created.append(raw_path)
    profile_path = output / "unpacked_u16.json"
    profile_path.write_text(
        json.dumps(
            {
                "name": "generated_unpacked_u16",
                "width": 320,
                "height": 240,
                "stride_bytes": 640,
                "offset_bytes": 0,
                "dtype": "uint16",
                "endianness": "little",
                "bit_depth": 16,
                "packing": "unpacked_u16",
                "channel_layout": "GRAY",
                "bayer_pattern": None,
                "black_level": 0,
                "white_level": 65535,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    created.append(profile_path)
    return created


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", nargs="?", type=Path, default=Path("test_data/generated"))
    arguments = parser.parse_args()
    for path in generate(arguments.output):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
