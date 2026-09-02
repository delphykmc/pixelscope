from __future__ import annotations

import hashlib
import json
import struct
import zlib
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

WIDTH = 16
HEIGHT = 12
FIXTURE_VERSION = 1
LAYOUTS = {"YUV444": (1, 1), "YUV422": (2, 1), "YUV420": (2, 2)}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_planes(layout: str, *, variant: bool = False):
    sx, sy = LAYOUTS[layout]
    yy, xx = np.indices((HEIGHT, WIDTH))
    y = (32 + 8 * xx + 4 * yy).astype(np.uint8)
    cy, cx = np.indices((HEIGHT // sy, WIDTH // sx))
    u = (32 + ((17 * cx + 11 * cy) % 192)).astype(np.uint8)
    v = (224 - ((13 * cx + 7 * cy) % 192)).astype(np.uint8)
    if variant:
        y = (y.astype(np.uint16) + 10).astype(np.uint8)
        u = (u.astype(np.uint16) + 8).astype(np.uint8)
        v = (v.astype(np.int16) - 8).astype(np.uint8)
    return y, u, v


def write_yuv(path: Path, y, u, v) -> None:
    uv = np.empty((u.shape[0], u.shape[1] * 2), dtype=np.uint8)
    uv[:, 0::2] = u
    uv[:, 1::2] = v
    path.write_bytes(y.tobytes() + uv.tobytes())


def bt601_preview(layout: str, y, u, v):
    sx, sy = LAYOUTS[layout]
    uf = np.repeat(np.repeat(u, sy, 0), sx, 1).astype(np.float32) - 128.0
    vf = np.repeat(np.repeat(v, sy, 0), sx, 1).astype(np.float32) - 128.0
    yf = y.astype(np.float32)
    rgb = np.empty((HEIGHT, WIDTH, 3), dtype=np.uint8)
    rgb[..., 0] = np.clip(np.rint(yf + 1.402 * vf), 0, 255).astype(np.uint8)
    rgb[..., 1] = np.clip(np.rint(yf - 0.344136 * uf - 0.714136 * vf), 0, 255).astype(np.uint8)
    rgb[..., 2] = np.clip(np.rint(yf + 1.772 * uf), 0, 255).astype(np.uint8)
    return rgb


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(kind)
    crc = zlib.crc32(payload, crc)
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc & 0xFFFFFFFF)


def write_png(path: Path, image: NDArray[np.uint8]) -> None:
    if image.ndim == 2:
        color_type = 0
    elif image.ndim == 3 and image.shape[2] == 3:
        color_type = 2
    else:
        raise ValueError(image.shape)
    h, w = image.shape[:2]
    data = np.ascontiguousarray(image)
    scan = b"".join(b"\0" + data[r].tobytes() for r in range(h))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, color_type, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", ihdr)
        + png_chunk(b"IDAT", zlib.compress(scan, 9))
        + png_chunk(b"IEND", b"")
    )


def pixel(layout: str, planes, x: int, y: int):
    yy, u, v = planes
    sx, sy = LAYOUTS[layout]
    return [int(yy[y, x]), int(u[y // sy, x // sx]), int(v[y // sy, x // sx])]


def native_entry(out: Path, stem: str, layout: str, *, variant: bool = False):
    planes = native_planes(layout, variant=variant)
    y, u, v = planes
    source = out / f"{stem}.yuv"
    write_yuv(source, y, u, v)
    ref = out / "references" / f"{stem}_bt601_full.png"
    write_png(ref, bt601_preview(layout, y, u, v))
    sx, sy = LAYOUTS[layout]
    coords = ((0, 0), (1, 0), (2, 0), (0, 1), (0, 2), (3, 3))
    return {
        "file": source.name,
        "role": "native_yuv",
        "layout": layout,
        "width": WIDTH,
        "height": HEIGHT,
        "bit_depth": 8,
        "plane_order": "Y+UV",
        "chroma_order": "UV",
        "color_matrix": "BT.601",
        "color_range": "Full",
        "file_size": source.stat().st_size,
        "sha256": sha256(source),
        "plane_shapes": {
            "Y": [HEIGHT, WIDTH],
            "U": [HEIGHT // sy, WIDTH // sx],
            "V": [HEIGHT // sy, WIDTH // sx],
        },
        "sample_counts": {"Y": int(y.size), "U": int(u.size), "V": int(v.size)},
        "selected_pixels": {
            f"{x},{yy}": pixel(layout, planes, x, yy) for x, yy in coords
        },
        "horizontal_line_x_0_to_15": {
            "Y_positions": list(range(WIDTH)),
            "U_positions": list(range(0, WIDTH, sx)),
            "V_positions": list(range(0, WIDTH, sx)),
        },
        "vertical_line_y_0_to_11": {
            "Y_positions": list(range(HEIGHT)),
            "U_positions": list(range(0, HEIGHT, sy)),
            "V_positions": list(range(0, HEIGHT, sy)),
        },
        "preview_reference": str(ref.relative_to(out)).replace("\\", "/"),
        "preview_sha256": sha256(ref),
        "variant": variant,
    }


def legacy_bayer12():
    yy, xx = np.indices((HEIGHT, WIDTH))
    ramp = (20 * xx + 10 * yy).astype(np.uint16)
    a = np.empty((HEIGHT, WIDTH), dtype=np.uint16)
    a[0::2, 0::2] = 3000 + ramp[0::2, 0::2]
    a[0::2, 1::2] = 2100 + ramp[0::2, 1::2]
    a[1::2, 0::2] = 1800 + ramp[1::2, 0::2]
    a[1::2, 1::2] = 900 + ramp[1::2, 1::2]
    return a


def generate(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "references").mkdir(exist_ok=True)
    (output_dir / "negative").mkdir(exist_ok=True)

    entries = [
        native_entry(output_dir, "01_yuv444_16x12", "YUV444"),
        native_entry(output_dir, "02_yuv422_16x12", "YUV422"),
        native_entry(output_dir, "03_yuv420_16x12", "YUV420"),
        native_entry(output_dir, "04_yuv420_variant_16x12", "YUV420", variant=True),
    ]

    legacy = output_dir / "05_legacy_bayer12_imgprops_16x12.yuv"
    legacy_bayer12().astype("<u2").tofile(legacy)
    sidecar = output_dir / "05_legacy_bayer12_imgprops_16x12.imgprops"
    sidecar.write_text(
        json.dumps(
            {
                "width": WIDTH,
                "height": HEIGHT,
                "imageType": "BAYER12",
                "pattern": "RGGB",
                "sensorBitWidth": 12,
                "pedestal": 256,
                "note": "unknown fields are intentionally ignored",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    entries.append(
        {
            "file": legacy.name,
            "role": "generic_raw_imgprops_fallback",
            "file_size": legacy.stat().st_size,
            "sha256": sha256(legacy),
            "sidecar": sidecar.name,
            "sidecar_sha256": sha256(sidecar),
            "expected_profile": {
                "width": WIDTH,
                "height": HEIGHT,
                "storage_format": "unpacked",
                "container_dtype": "uint16",
                "endianness": "little",
                "bit_depth": 12,
                "bit_alignment": "lsb",
                "channel_layout": "BAYER",
                "bayer_pattern": "RGGB",
                "black_level": 256,
                "stride_bytes": WIDTH * 2,
            },
        }
    )

    y, u, v = native_planes("YUV420")
    temp = output_dir / "negative" / "_good.tmp"
    write_yuv(temp, y, u, v)
    good = temp.read_bytes()
    temp.unlink()
    short = output_dir / "negative" / "yuv420_short_16x12.yuv"
    long = output_dir / "negative" / "yuv420_long_16x12.yuv"
    short.write_bytes(good[:-1])
    long.write_bytes(good + b"\0")
    entries += [
        {
            "file": "negative/yuv420_short_16x12.yuv",
            "role": "negative_size",
            "intended_layout": "YUV420",
            "expected_size": len(good),
            "actual_size": short.stat().st_size,
            "sha256": sha256(short),
        },
        {
            "file": "negative/yuv420_long_16x12.yuv",
            "role": "negative_size",
            "intended_layout": "YUV420",
            "expected_size": len(good),
            "actual_size": long.stat().st_size,
            "sha256": sha256(long),
        },
    ]

    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixture_version": FIXTURE_VERSION,
                "generated_by": "scripts/generate_yuv_manual_fixtures.py",
                "width": WIDTH,
                "height": HEIGHT,
                "entries": entries,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return sorted(p for p in output_dir.rglob("*") if p.is_file())


def main() -> int:
    for p in generate(Path("test_data/manual/yuv_chart_set")):
        print(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
