from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray

FHD_SIZE = (1920, 1080)
DEFAULT_ROOT = Path("manual_data/fhd")
DEFAULT_OUTPUT = DEFAULT_ROOT / "16bit_variations"


def _find_base_image(explicit: Path | None, root: Path) -> Path:
    if explicit is not None:
        candidate = explicit.resolve()
        if not candidate.is_file():
            raise FileNotFoundError(candidate)
        return candidate

    preferred = (
        root / "base.jpg",
        root / "base.jpeg",
        root / "Base.jpg",
        root / "Base.jpeg",
    )
    for candidate in preferred:
        if candidate.is_file():
            return candidate.resolve()

    discovered = sorted(
        [*root.glob("*.jpg"), *root.glob("*.jpeg")],
        key=lambda path: path.name.casefold(),
    )
    if not discovered:
        raise FileNotFoundError(
            f"No base JPEG found in {root}. Pass an explicit path with --base."
        )
    return discovered[0].resolve()


def _load_fhd_bgr(path: Path) -> NDArray[np.uint8]:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"OpenCV could not decode {path}")
    if (image.shape[1], image.shape[0]) != FHD_SIZE:
        image = cv2.resize(image, FHD_SIZE, interpolation=cv2.INTER_AREA)
    return np.ascontiguousarray(image, dtype=np.uint8)


def _to_uint16(image: NDArray[np.uint8]) -> NDArray[np.uint16]:
    return image.astype(np.uint16) * np.uint16(257)


def _clip_uint16(values: NDArray[np.floating]) -> NDArray[np.uint16]:
    return np.clip(np.rint(values), 0, 65535).astype(np.uint16)


def _write_png(path: Path, image: NDArray[np.uint16]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), image):
        raise RuntimeError(f"OpenCV could not write {path}")
    check = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if check is None or check.dtype != np.uint16 or check.shape != image.shape:
        raise RuntimeError(f"16-bit round-trip validation failed for {path}")


def generate_variations(
    base_path: Path,
    output_dir: Path,
    seed: int = 20260804,
) -> list[Path]:
    base_u8 = _load_fhd_bgr(base_path)
    base = _to_uint16(base_u8)
    base_float = base.astype(np.float64)
    midpoint = 32767.5

    x_ramp = np.linspace(-2048.0, 2048.0, base.shape[1], dtype=np.float64)
    ramp = x_ramp[np.newaxis, :, np.newaxis]
    rng = np.random.default_rng(seed)
    noise = rng.normal(0.0, 384.0, size=base.shape)

    variations: dict[str, NDArray[np.uint16]] = {
        "base_16bit.png": base,
        "brightness_minus_4096_16bit.png": _clip_uint16(base_float - 4096.0),
        "brightness_plus_4096_16bit.png": _clip_uint16(base_float + 4096.0),
        "contrast_low_16bit.png": _clip_uint16(
            midpoint + (base_float - midpoint) * 0.80
        ),
        "contrast_high_16bit.png": _clip_uint16(
            midpoint + (base_float - midpoint) * 1.20
        ),
        "noise_sigma_384_16bit.png": _clip_uint16(base_float + noise),
        "ramp_plus_minus_2048_16bit.png": _clip_uint16(base_float + ramp),
        "gaussian_blur_5x5_16bit.png": cv2.GaussianBlur(base, (5, 5), 0),
    }

    written: list[Path] = []
    for filename, image in variations.items():
        target = output_dir / filename
        _write_png(target, np.ascontiguousarray(image, dtype=np.uint16))
        written.append(target)

    manifest = {
        "source": str(base_path),
        "source_note": (
            "The JPEG is decoded as 8-bit and expanded to uint16. Variations add "
            "intermediate 16-bit code values for histogram UI testing."
        ),
        "width": FHD_SIZE[0],
        "height": FHD_SIZE[1],
        "dtype": "uint16",
        "seed": seed,
        "files": [path.name for path in written],
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    written.append(manifest_path)
    return written


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate deterministic FHD uint16 PNG variations from a base JPEG."
    )
    parser.add_argument(
        "--base",
        type=Path,
        default=None,
        help="Base JPEG. By default, search manual_data/fhd.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help="Directory searched for a base JPEG when --base is omitted.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output directory for the generated 16-bit PNG files.",
    )
    parser.add_argument("--seed", type=int, default=20260804)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    base_path = _find_base_image(args.base, args.root)
    output_dir = args.output.resolve()
    written = generate_variations(base_path, output_dir, seed=args.seed)
    print(f"Base: {base_path}")
    print(f"Output: {output_dir}")
    for path in written:
        print(f"  {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
