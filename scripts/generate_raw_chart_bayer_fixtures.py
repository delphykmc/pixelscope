from __future__ import annotations

import hashlib
import json
import struct
import zlib
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

WIDTH = 1920
HEIGHT = 1080
BAYER_PATTERN = "RGGB"
COVERAGE_PATCH_SIZE = 256
COVERAGE_BLOCK_SIZE = 2
REFERENCE_DIR = "references"
REFERENCE_RGB = "bayer_reference_rgb.png"
REFERENCE_MOSAIC = "bayer_reference_mosaic.png"
REFERENCE_PIXELSCOPE = "bayer_reference_pixelscope.png"
BAYER_CHART_VERSION = 3
LEGACY_BAYER_STEMS = (
    "synthetic_fhd_10bit_rggb_u16le_lsb",
    "synthetic_fhd_10bit_rggb_mipi_raw10",
    "synthetic_fhd_12bit_rggb_u16le_msb",
    "synthetic_fhd_12bit_rggb_mipi_raw12",
    "synthetic_fhd_14bit_rggb_mipi_raw14",
)
LEGACY_REFERENCE_FILES = (
    "synthetic_fhd_rggb_reference_rgb.png",
    "synthetic_fhd_rggb_reference_mosaic.png",
    "synthetic_fhd_rggb_reference_pixelscope.png",
)


def _remove_legacy_outputs(output_dir: Path) -> None:
    for stem in LEGACY_BAYER_STEMS:
        for suffix in (".raw", ".json"):
            (output_dir / f"{stem}{suffix}").unlink(missing_ok=True)
    for filename in LEGACY_REFERENCE_FILES:
        (output_dir / filename).unlink(missing_ok=True)


def _reference_rgb_chart() -> NDArray[np.float64]:
    """Create the true RGB source chart sampled by every Bayer fixture."""

    image = np.full((HEIGHT, WIDTH, 3), 0.08, dtype=np.float64)

    # Color bars make Bayer channel identity obvious after channel splitting.
    color_bars = np.array(
        [
            (1.0, 1.0, 1.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 1.0),
            (0.0, 1.0, 0.0),
            (1.0, 0.0, 1.0),
            (1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
            (0.0, 0.0, 0.0),
        ],
        dtype=np.float64,
    )
    bar_height = 150
    bar_width = WIDTH // len(color_bars)
    for index, color in enumerate(color_bars):
        left = index * bar_width
        right = WIDTH if index == len(color_bars) - 1 else (index + 1) * bar_width
        image[:bar_height, left:right] = color

    # Smooth neutral ramp and discrete gray steps.
    ramp_top, ramp_bottom = 180, 310
    ramp = np.linspace(0.0, 1.0, 1200, dtype=np.float64)
    image[ramp_top:ramp_bottom, 40:1240] = ramp[None, :, None]
    step_left, step_right = 1280, WIDTH - 40
    step_count = 12
    step_width = (step_right - step_left) // step_count
    for index in range(step_count):
        level = index / (step_count - 1)
        left = step_left + index * step_width
        right = step_right if index == step_count - 1 else left + step_width
        image[ramp_top:ramp_bottom, left:right] = level

    # Large neutral checkerboard: easy to recognize in raw mosaic and channel planes.
    checker_top, checker_bottom = 350, 700
    checker_left, checker_right = 40, 620
    yy, xx = np.indices((checker_bottom - checker_top, checker_right - checker_left))
    checker = ((xx // 32 + yy // 32) % 2).astype(np.float64)
    checker = 0.12 + checker * 0.76
    image[checker_top:checker_bottom, checker_left:checker_right] = checker[..., None]

    # RGB two-axis gradient: each channel has a simple, explainable behavior.
    gradient_top, gradient_bottom = 350, 700
    gradient_left, gradient_right = 660, 1260
    gx = np.linspace(0.0, 1.0, gradient_right - gradient_left, dtype=np.float64)
    gy = np.linspace(0.0, 1.0, gradient_bottom - gradient_top, dtype=np.float64)[:, None]
    gradient = np.empty(
        (gradient_bottom - gradient_top, gradient_right - gradient_left, 3),
        dtype=np.float64,
    )
    gradient[..., 0] = gx[None, :]
    gradient[..., 1] = gy
    gradient[..., 2] = 1.0 - 0.5 * gx[None, :] - 0.5 * gy
    image[gradient_top:gradient_bottom, gradient_left:gradient_right] = np.clip(
        gradient,
        0.0,
        1.0,
    )

    # Concentric neutral rings and a slanted edge expose geometry and aliasing.
    geometry_top, geometry_bottom = 350, 700
    geometry_left, geometry_right = 1300, WIDTH - 40
    region_height = geometry_bottom - geometry_top
    region_width = geometry_right - geometry_left
    yy, xx = np.indices((region_height, region_width), dtype=np.float64)
    center_x = (region_width - 1) / 2.0
    center_y = (region_height - 1) / 2.0
    radius = np.hypot(xx - center_x, yy - center_y)
    rings = 0.20 + 0.70 * ((radius // 20) % 2)
    slanted = (xx + 0.55 * yy) > (0.62 * region_width)
    geometry = np.where(slanted, rings, 1.0 - rings)
    image[geometry_top:geometry_bottom, geometry_left:geometry_right] = geometry[..., None]

    # Bottom frequency bands are neutral, so Bayer parity does not dominate the pattern.
    frequency_top = 740
    frequency_bottom = HEIGHT - 40
    frequency_right = WIDTH - COVERAGE_PATCH_SIZE - 80
    band_width = max(1, frequency_right - 40)
    x = np.linspace(0.0, 1.0, band_width, dtype=np.float64)
    y = np.arange(frequency_bottom - frequency_top, dtype=np.float64)[:, None]
    local_frequency = 2.0 + 70.0 * x
    phase = 2.0 * np.pi * (local_frequency[None, :] * y / 160.0)
    bands = 0.5 + 0.42 * np.sin(phase)
    image[frequency_top:frequency_bottom, 40:frequency_right] = bands[..., None]

    # The source chart marks the isolated decoder-coverage area as a neutral ramp.
    coverage_codes = np.arange(128 * 128, dtype=np.float64).reshape(128, 128)
    coverage = np.repeat(np.repeat(coverage_codes / 16383.0, 2, axis=0), 2, axis=1)
    image[-COVERAGE_PATCH_SIZE:, -COVERAGE_PATCH_SIZE:] = coverage[..., None]

    return np.clip(image, 0.0, 1.0)


def _sample_rggb(rgb: NDArray[np.float64]) -> NDArray[np.float64]:
    """Sample an RGB reference into one full-resolution RGGB Bayer mosaic."""

    mosaic = np.empty(rgb.shape[:2], dtype=np.float64)
    mosaic[0::2, 0::2] = rgb[0::2, 0::2, 0]
    mosaic[0::2, 1::2] = rgb[0::2, 1::2, 1]
    mosaic[1::2, 0::2] = rgb[1::2, 0::2, 1]
    mosaic[1::2, 1::2] = rgb[1::2, 1::2, 2]
    return mosaic


def _coverage_patch(bit_depth: int) -> NDArray[np.uint16]:
    """Cover every native code while keeping each RGGB 2x2 block neutral."""

    maximum = (1 << bit_depth) - 1
    block_codes = np.arange(128 * 128, dtype=np.uint32) % (maximum + 1)
    blocks = block_codes.reshape(128, 128)
    expanded = np.repeat(
        np.repeat(blocks, COVERAGE_BLOCK_SIZE, axis=0),
        COVERAGE_BLOCK_SIZE,
        axis=1,
    )
    return expanded.astype(np.uint16)


def _quantized_chart(bit_depth: int) -> NDArray[np.uint16]:
    maximum = (1 << bit_depth) - 1
    values = np.rint(_sample_rggb(_reference_rgb_chart()) * maximum).astype(np.uint16)
    values[-COVERAGE_PATCH_SIZE:, -COVERAGE_PATCH_SIZE:] = _coverage_patch(bit_depth)
    return values


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    checksum = zlib.crc32(kind)
    checksum = zlib.crc32(payload, checksum)
    return (
        struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum & 0xFFFFFFFF)
    )


def _write_png(path: Path, image: NDArray[np.uint8]) -> None:
    """Write a deterministic 8-bit grayscale or RGB PNG using only stdlib zlib."""

    if image.ndim == 2:
        color_type = 0
    elif image.ndim == 3 and image.shape[2] == 3:
        color_type = 2
    else:
        raise ValueError(f"unsupported PNG shape: {image.shape}")
    if image.shape[:2] != (HEIGHT, WIDTH):
        raise ValueError(f"unexpected PNG shape: {image.shape}")

    contiguous = np.ascontiguousarray(image)
    scanlines = b"".join(b"\x00" + contiguous[row].tobytes() for row in range(contiguous.shape[0]))
    ihdr = struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, color_type, 0, 0, 0)
    encoded = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(scanlines, level=9))
        + _png_chunk(b"IEND", b"")
    )
    path.write_bytes(encoded)


def _write_reference_images(output_dir: Path) -> dict[str, str]:
    reference_dir = output_dir / REFERENCE_DIR
    reference_dir.mkdir(parents=True, exist_ok=True)
    rgb = _reference_rgb_chart()
    mosaic14 = _quantized_chart(14)
    mosaic_u8 = np.rint(mosaic14.astype(np.float64) * (255.0 / 16383.0)).astype(np.uint8)
    red_blue = np.rint(mosaic_u8.astype(np.float32) * 0.38).astype(np.uint8)
    pixelscope = np.ascontiguousarray(np.stack((red_blue, mosaic_u8, red_blue), axis=-1))

    _write_png(reference_dir / REFERENCE_RGB, np.rint(rgb * 255.0).astype(np.uint8))
    _write_png(reference_dir / REFERENCE_MOSAIC, mosaic_u8)
    _write_png(reference_dir / REFERENCE_PIXELSCOPE, pixelscope)
    return {
        "source_rgb": f"{REFERENCE_DIR}/{REFERENCE_RGB}",
        "mosaic_gray": f"{REFERENCE_DIR}/{REFERENCE_MOSAIC}",
        "pixelscope_preview": f"{REFERENCE_DIR}/{REFERENCE_PIXELSCOPE}",
    }


def _pack_raw10(values: NDArray[np.uint16]) -> bytes:
    groups = values.reshape(HEIGHT, -1, 4).astype(np.uint16)
    packed = np.empty((HEIGHT, groups.shape[1], 5), dtype=np.uint8)
    packed[:, :, 0:4] = (groups >> 2).astype(np.uint8)
    packed[:, :, 4] = (
        (groups[:, :, 0] & 0x03)
        | ((groups[:, :, 1] & 0x03) << 2)
        | ((groups[:, :, 2] & 0x03) << 4)
        | ((groups[:, :, 3] & 0x03) << 6)
    ).astype(np.uint8)
    return packed.tobytes()


def _pack_raw12(values: NDArray[np.uint16]) -> bytes:
    groups = values.reshape(HEIGHT, -1, 2).astype(np.uint16)
    packed = np.empty((HEIGHT, groups.shape[1], 3), dtype=np.uint8)
    packed[:, :, 0:2] = (groups >> 4).astype(np.uint8)
    packed[:, :, 2] = ((groups[:, :, 0] & 0x0F) | ((groups[:, :, 1] & 0x0F) << 4)).astype(np.uint8)
    return packed.tobytes()


def _pack_raw14(values: NDArray[np.uint16]) -> bytes:
    groups = values.reshape(HEIGHT, -1, 4).astype(np.uint16)
    low0 = groups[:, :, 0] & 0x3F
    low1 = groups[:, :, 1] & 0x3F
    low2 = groups[:, :, 2] & 0x3F
    low3 = groups[:, :, 3] & 0x3F
    packed = np.empty((HEIGHT, groups.shape[1], 7), dtype=np.uint8)
    packed[:, :, 0:4] = (groups >> 6).astype(np.uint8)
    packed[:, :, 4] = (low0 | ((low1 & 0x03) << 6)).astype(np.uint8)
    packed[:, :, 5] = ((low1 >> 2) | ((low2 & 0x0F) << 4)).astype(np.uint8)
    packed[:, :, 6] = ((low2 >> 4) | (low3 << 2)).astype(np.uint8)
    return packed.tobytes()


def _profile(
    *,
    name: str,
    bit_depth: int,
    storage_format: str,
    stride_bytes: int,
    container_dtype: str | None = None,
    endianness: str | None = None,
    bit_alignment: str | None = None,
) -> dict[str, object]:
    return {
        "name": name,
        "width": WIDTH,
        "height": HEIGHT,
        "stride_bytes": stride_bytes,
        "offset_bytes": 0,
        "storage_format": storage_format,
        "container_dtype": container_dtype,
        "endianness": endianness,
        "bit_depth": bit_depth,
        "bit_alignment": bit_alignment,
        "channel_layout": "BAYER",
        "bayer_pattern": BAYER_PATTERN,
        "black_level": [0, 0, 0, 0],
        "white_level": (1 << bit_depth) - 1,
    }


def generate(output_dir: Path) -> list[dict[str, object]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, object]] = []
    definitions = [
        (
            "02_bayer_10bit_01_rggb_u16le_lsb",
            10,
            "unpacked",
            WIDTH * 2,
            "uint16",
            "little",
            "lsb",
        ),
        (
            "02_bayer_10bit_02_rggb_mipi_raw10",
            10,
            "mipi_raw10",
            WIDTH * 5 // 4,
            None,
            None,
            None,
        ),
        (
            "02_bayer_12bit_01_rggb_u16le_msb",
            12,
            "unpacked",
            WIDTH * 2,
            "uint16",
            "little",
            "msb",
        ),
        (
            "02_bayer_12bit_02_rggb_mipi_raw12",
            12,
            "mipi_raw12",
            WIDTH * 3 // 2,
            None,
            None,
            None,
        ),
        (
            "02_bayer_14bit_01_rggb_mipi_raw14",
            14,
            "mipi_raw14",
            WIDTH * 7 // 4,
            None,
            None,
            None,
        ),
    ]

    for (
        stem,
        bit_depth,
        storage_format,
        stride,
        container_dtype,
        endianness,
        alignment,
    ) in definitions:
        values = _quantized_chart(bit_depth)
        if storage_format == "unpacked":
            stored = values
            if alignment == "msb":
                stored = values << (16 - bit_depth)
            payload = stored.astype("<u2").tobytes()
        elif storage_format == "mipi_raw10":
            payload = _pack_raw10(values)
        elif storage_format == "mipi_raw12":
            payload = _pack_raw12(values)
        else:
            payload = _pack_raw14(values)

        raw_name = f"{stem}.raw"
        profile_name = f"{stem}.json"
        (output_dir / raw_name).write_bytes(payload)
        profile = _profile(
            name=stem,
            bit_depth=bit_depth,
            storage_format=storage_format,
            stride_bytes=stride,
            container_dtype=container_dtype,
            endianness=endianness,
            bit_alignment=alignment,
        )
        (output_dir / profile_name).write_text(
            json.dumps(profile, indent=2) + "\n",
            encoding="utf-8",
        )
        entries.append(
            {
                "raw": raw_name,
                "profile": profile_name,
                "storage_format": storage_format,
                "container_dtype": container_dtype,
                "bit_depth": bit_depth,
                "bit_alignment": alignment,
                "stride_bytes": stride,
                "channel_layout": "BAYER",
                "bayer_pattern": BAYER_PATTERN,
                "minimum": 0,
                "maximum": (1 << bit_depth) - 1,
                "expected_auto_bins": min(1 << bit_depth, 4096),
                "comparison_group": "shared_rggb_chart_v3",
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    return entries


def _update_manifest(
    output_dir: Path,
    entries: list[dict[str, object]],
    references: dict[str, str],
) -> None:
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(
            "manifest.json is required so existing GRAY fixture metadata can be preserved"
        )
    current = json.loads(manifest_path.read_text(encoding="utf-8"))
    gray_entries = [
        entry for entry in current.get("files", []) if entry.get("channel_layout") == "GRAY"
    ]
    gray_names = {
        8: "01_gray_08bit_u8",
        10: "01_gray_10bit_u16le_lsb",
        12: "01_gray_12bit_u16le_lsb",
        14: "01_gray_14bit_u16le_lsb",
        16: "01_gray_16bit_u16le",
    }
    for entry in gray_entries:
        stem = gray_names[int(entry["bit_depth"])]
        entry["raw"] = f"{stem}.raw"
        entry["profile"] = f"{stem}.json"
    updated = {
        "dataset": "PixelScope synthetic FHD RAW chart set",
        "width": WIDTH,
        "height": HEIGHT,
        "seed": current.get("seed", 20260804),
        "bayer_chart_version": BAYER_CHART_VERSION,
        "generator": "scripts/generate_raw_chart_bayer_fixtures.py",
        "description": (
            "Naturally sorted GRAY fixtures followed by one true-RGB-derived RGGB chart "
            "serialized as unpacked uint16 and MIPI RAW10/12/14. The Bayer variants "
            "share the same sampled scene and use a CFA-neutral 256x256 native-code "
            "coverage patch in the bottom-right corner."
        ),
        "references": {
            **references,
            "coverage_patch": {
                "size": COVERAGE_PATCH_SIZE,
                "block_size": COVERAGE_BLOCK_SIZE,
                "location": "bottom-right",
                "description": (
                    "Every 2x2 RGGB block carries one neutral code. The patch covers every "
                    "native code at least once for 10, 12, and 14-bit fixtures."
                ),
            },
        },
        "files": gray_entries + entries,
    }
    manifest_path.write_text(json.dumps(updated, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    output = root / "test_data" / "manual" / "raw_chart_set"
    _remove_legacy_outputs(output)
    entries = generate(output)
    references = _write_reference_images(output)
    _update_manifest(output, entries, references)
    print(
        json.dumps(
            {
                "bayer_entries": entries,
                "references": references,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
