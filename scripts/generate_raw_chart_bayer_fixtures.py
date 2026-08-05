from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

WIDTH = 1920
HEIGHT = 1080
BAYER_PATTERN = "RGGB"


def _normalized_bayer_chart() -> NDArray[np.float64]:
    """Create a deterministic FHD RGGB chart with gradients and code coverage."""

    x = np.linspace(0.0, 1.0, WIDTH, dtype=np.float64)
    y = np.linspace(0.0, 1.0, HEIGHT, dtype=np.float64)[:, None]
    red = np.broadcast_to(x, (HEIGHT, WIDTH))
    green = np.broadcast_to(y, (HEIGHT, WIDTH))
    blue = 0.5 + 0.5 * np.sin(12.0 * np.pi * x)[None, :]
    blue = np.broadcast_to(blue, (HEIGHT, WIDTH))

    checker = ((np.indices((HEIGHT, WIDTH)).sum(axis=0) // 32) % 2).astype(np.float64)
    red = np.clip(0.82 * red + 0.18 * checker, 0.0, 1.0)
    green = np.clip(0.82 * green + 0.18 * (1.0 - checker), 0.0, 1.0)
    blue = np.clip(0.82 * blue + 0.18 * checker, 0.0, 1.0)

    mosaic = np.empty((HEIGHT, WIDTH), dtype=np.float64)
    mosaic[0::2, 0::2] = red[0::2, 0::2]
    mosaic[0::2, 1::2] = green[0::2, 1::2]
    mosaic[1::2, 0::2] = green[1::2, 0::2]
    mosaic[1::2, 1::2] = blue[1::2, 1::2]
    return mosaic


def _quantized_chart(bit_depth: int) -> NDArray[np.uint16]:
    maximum = (1 << bit_depth) - 1
    values = np.rint(_normalized_bayer_chart() * maximum).astype(np.uint16)

    # A 256 x 256 patch covers every code at least once for 10/12/14-bit.
    coverage = np.arange(256 * 256, dtype=np.uint32) % (maximum + 1)
    values[-256:, -256:] = coverage.reshape(256, 256).astype(np.uint16)
    return values


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
            "synthetic_fhd_10bit_rggb_u16le_lsb",
            10,
            "unpacked",
            WIDTH * 2,
            "uint16",
            "little",
            "lsb",
        ),
        (
            "synthetic_fhd_12bit_rggb_u16le_msb",
            12,
            "unpacked",
            WIDTH * 2,
            "uint16",
            "little",
            "msb",
        ),
        (
            "synthetic_fhd_10bit_rggb_mipi_raw10",
            10,
            "mipi_raw10",
            WIDTH * 5 // 4,
            None,
            None,
            None,
        ),
        (
            "synthetic_fhd_12bit_rggb_mipi_raw12",
            12,
            "mipi_raw12",
            WIDTH * 3 // 2,
            None,
            None,
            None,
        ),
        (
            "synthetic_fhd_14bit_rggb_mipi_raw14",
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
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    return entries


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    output = root / "test_data" / "manual" / "raw_chart_set"
    entries = generate(output)
    print(json.dumps(entries, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
