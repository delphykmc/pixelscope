from __future__ import annotations

import argparse
import struct
from collections.abc import Mapping
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "src" / "pixelscope" / "assets" / "icons"
SVG_PATH = ICON_DIR / "pixelscope.svg"
PNG_PATH = ICON_DIR / "pixelscope.png"
ICO_PATH = ICON_DIR / "pixelscope.ico"
ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def _renderer(svg_bytes: bytes) -> QSvgRenderer:
    renderer = QSvgRenderer(QByteArray(svg_bytes))
    if not renderer.isValid():
        raise RuntimeError(f"invalid SVG source: {SVG_PATH}")
    return renderer


def _render_png(renderer: QSvgRenderer, size: int) -> bytes:
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


def _decoded_image(payload: bytes, size: int) -> QImage:
    image = QImage.fromData(payload)
    if image.isNull():
        raise RuntimeError(f"failed to decode {size} px icon payload")
    if (image.width(), image.height()) != (size, size):
        raise RuntimeError(f"icon payload does not match declared {size} px size")
    if not image.hasAlphaChannel() or image.pixelColor(0, 0).alpha() == 255:
        raise RuntimeError(f"{size} px icon payload does not retain transparency")
    return image


def _check_existing() -> None:
    _renderer(SVG_PATH.read_bytes())
    _decoded_image(PNG_PATH.read_bytes(), 256)

    ico_bytes = ICO_PATH.read_bytes()
    reserved, image_type, count = struct.unpack_from("<HHH", ico_bytes, 0)
    if (reserved, image_type, count) != (0, 1, len(ICO_SIZES)):
        raise RuntimeError("ICO header does not match the canonical frame contract")

    directory_end = 6 + count * 16
    ranges: list[tuple[int, int]] = []
    sizes: list[int] = []
    for index in range(count):
        entry_offset = 6 + index * 16
        width, height, _, entry_reserved, planes, bit_count, length, offset = (
            struct.unpack_from("<BBBBHHII", ico_bytes, entry_offset)
        )
        size = 256 if width == 0 else width
        decoded_height = 256 if height == 0 else height
        end = offset + length
        if size != decoded_height or entry_reserved != 0 or planes != 1:
            raise RuntimeError(f"invalid ICO directory entry at index {index}")
        invalid_bounds = (
            bit_count != 32
            or length <= 0
            or offset < directory_end
            or end > len(ico_bytes)
        )
        if invalid_bounds:
            raise RuntimeError(f"invalid ICO payload bounds at index {index}")
        _decoded_image(ico_bytes[offset:end], size)
        sizes.append(size)
        ranges.append((offset, end))

    if tuple(sizes) != ICO_SIZES:
        raise RuntimeError(f"unexpected ICO frame order: {tuple(sizes)}")
    ordered_ranges = sorted(ranges)
    for index in range(1, len(ordered_ranges)):
        if ordered_ranges[index - 1][1] > ordered_ranges[index][0]:
            raise RuntimeError("ICO frame payloads overlap")


def generate(*, check: bool) -> None:
    if check:
        _check_existing()
        return

    renderer = _renderer(SVG_PATH.read_bytes())
    frames = {size: _render_png(renderer, size) for size in ICO_SIZES}
    PNG_PATH.write_bytes(frames[256])
    ICO_PATH.write_bytes(_encode_ico(frames))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate PixelScope PNG/ICO assets from the canonical SVG."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate checked-in SVG/PNG/ICO assets without rewriting them",
    )
    args = parser.parse_args()

    generate(check=args.check)
    action = "Validated" if args.check else "Generated"
    print(f"{action} {PNG_PATH.relative_to(ROOT)}")
    print(f"{action} {ICO_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
