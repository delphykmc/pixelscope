from __future__ import annotations

import os
import struct
import subprocess
import sys
from importlib.resources import files
from pathlib import Path
from xml.etree import ElementTree

from PySide6.QtGui import QImage

EXPECTED_ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "scripts" / "generate_icon_assets.py"


def _icon_resource(name: str) -> bytes:
    resource = files("pixelscope")
    for part in ("assets", "icons", name):
        resource = resource.joinpath(part)
    return resource.read_bytes()


def _local_name(tag: str) -> str:
    return tag.rsplit("}", maxsplit=1)[-1].lower()


def test_canonical_svg_is_editable_vector_source() -> None:
    svg_bytes = _icon_resource("pixelscope.svg")
    root = ElementTree.fromstring(svg_bytes)

    assert _local_name(root.tag) == "svg"
    assert root.attrib["viewBox"] == "0 0 512 512"
    assert b"data:image" not in svg_bytes
    assert all(_local_name(element.tag) != "image" for element in root.iter())


def test_runtime_png_is_transparent_256_square() -> None:
    png_bytes = _icon_resource("pixelscope.png")
    image = QImage.fromData(png_bytes, "PNG")

    assert png_bytes.startswith(PNG_SIGNATURE)
    assert not image.isNull()
    assert (image.width(), image.height()) == (256, 256)
    assert image.hasAlphaChannel()
    assert image.pixelColor(0, 0).alpha() < 255


def test_windows_ico_contains_valid_transparent_frames() -> None:
    ico_bytes = _icon_resource("pixelscope.ico")
    reserved, image_type, count = struct.unpack_from("<HHH", ico_bytes, 0)

    assert (reserved, image_type) == (0, 1)
    assert count == len(EXPECTED_ICO_SIZES)

    directory_end = 6 + count * 16
    sizes: list[int] = []
    payload_ranges: list[tuple[int, int]] = []

    for index in range(count):
        entry_offset = 6 + index * 16
        (
            width,
            height,
            _color_count,
            entry_reserved,
            planes,
            bit_count,
            payload_length,
            payload_offset,
        ) = struct.unpack_from("<BBBBHHII", ico_bytes, entry_offset)

        decoded_width = 256 if width == 0 else width
        decoded_height = 256 if height == 0 else height
        assert decoded_width == decoded_height
        assert entry_reserved == 0
        # ICO exporters commonly write wPlanes as either 0 (unspecified) or 1.
        # Validate the actual decoded 32-bit alpha payload below instead of
        # rejecting an otherwise valid Windows icon on this advisory field.
        assert planes in (0, 1)
        assert bit_count == 32
        assert payload_length > 0
        assert payload_offset >= directory_end

        payload_end = payload_offset + payload_length
        assert payload_end <= len(ico_bytes)
        payload_ranges.append((payload_offset, payload_end))
        sizes.append(decoded_width)

        payload = ico_bytes[payload_offset:payload_end]
        image = QImage.fromData(payload)
        assert not image.isNull()
        assert (image.width(), image.height()) == (decoded_width, decoded_height)
        assert image.hasAlphaChannel()
        assert image.pixelColor(0, 0).alpha() < 255

    assert tuple(sizes) == EXPECTED_ICO_SIZES
    ordered_ranges = sorted(payload_ranges)
    for index in range(1, len(ordered_ranges)):
        assert ordered_ranges[index - 1][1] <= ordered_ranges[index][0]


def test_generator_reproduces_checked_in_assets_and_cleans_temp(tmp_path: Path) -> None:
    temp_root = tmp_path / "icon-reproduction"
    temp_root.mkdir()
    env = os.environ.copy()
    env.update(
        {
            "TMP": str(temp_root),
            "TEMP": str(temp_root),
            "TMPDIR": str(temp_root),
        }
    )

    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--check"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert list(temp_root.iterdir()) == []
