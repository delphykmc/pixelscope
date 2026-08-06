from __future__ import annotations

import argparse
import struct
from collections.abc import Mapping
from pathlib import Path

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "src" / "pixelscope" / "assets" / "icons"
SVG_PATH = ICON_DIR / "pixelscope.svg"
PNG_PATH = ICON_DIR / "pixelscope.png"
ICO_PATH = ICON_DIR / "pixelscope.ico"
ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def _render_png(svg_bytes: bytes, size: int) -> bytes:
    renderer = QSvgRenderer(QByteArray(svg_bytes))
    if not renderer.isValid():
        raise RuntimeError(f"invalid SVG source: {SVG_PATH}")

    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        renderer.render(painter, QRectF(0.0, 0.0, float(size), float(size)))
    finally:
        painter.end()

    buffer = QBuffer()
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
        raise RuntimeError("failed to open PNG output buffer")
    if not image.save(buffer, "PNG"):
        raise RuntimeError(f"failed to encode {size} px PNG frame")
    return bytes(buffer.data())


def _encode_ico(frames: Mapping[int, bytes]) -> bytes:
    ordered = [(size, frames[size]) for size in ICO_SIZES]
    header_size = 6 + 16 * len(ordered)
    offset = header_size
    entries: list[bytes] = []
    payloads: list[bytes] = []

    for size, payload in ordered:
        dimension = 0 if size == 256 else size
        entries.append(
            struct.pack(
                "<BBBBHHII",
                dimension,
                dimension,
                0,
                0,
                1,
                32,
                len(payload),
                offset,
            )
        )
        payloads.append(payload)
        offset += len(payload)

    return (
        struct.pack("<HHH", 0, 1, len(ordered))
        + b"".join(entries)
        + b"".join(payloads)
    )


def _write_or_check(path: Path, expected: bytes, *, check: bool) -> None:
    if check:
        actual = path.read_bytes() if path.exists() else None
        if actual != expected:
            raise RuntimeError(
                f"{path.relative_to(ROOT)} is not the canonical generated output"
            )
        return
    path.write_bytes(expected)


def generate(*, check: bool) -> None:
    svg_bytes = SVG_PATH.read_bytes()
    frames = {size: _render_png(svg_bytes, size) for size in ICO_SIZES}
    _write_or_check(PNG_PATH, frames[256], check=check)
    _write_or_check(ICO_PATH, _encode_ico(frames), check=check)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate PixelScope PNG/ICO assets from the canonical SVG."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify checked-in PNG/ICO bytes instead of rewriting them",
    )
    args = parser.parse_args()

    generate(check=args.check)
    action = "Verified" if args.check else "Generated"
    print(f"{action} {PNG_PATH.relative_to(ROOT)}")
    print(f"{action} {ICO_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
