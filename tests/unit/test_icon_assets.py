from __future__ import annotations

import struct
from importlib.resources import files
from xml.etree import ElementTree

EXPECTED_ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def _icon_resource(name: str) -> bytes:
    resource = files("pixelscope")
    for part in ("assets", "icons", name):
        resource = resource.joinpath(part)
    return resource.read_bytes()


def test_canonical_svg_is_editable_vector_source() -> None:
    svg_bytes = _icon_resource("pixelscope.svg")
    root = ElementTree.fromstring(svg_bytes)

    assert root.tag.endswith("svg")
    assert root.attrib["viewBox"] == "0 0 512 512"
    assert b"data:image" not in svg_bytes


def test_runtime_png_is_indexed_alpha_256_square() -> None:
    png_bytes = _icon_resource("pixelscope.png")

    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack_from(">II", png_bytes, 16)
    assert (width, height) == (256, 256)
    assert png_bytes[24] == 8
    assert png_bytes[25] == 3  # PNG color type 3: indexed color with transparency.
    assert b"tRNS" in png_bytes


def test_windows_ico_contains_all_supported_sizes() -> None:
    ico_bytes = _icon_resource("pixelscope.ico")
    reserved, image_type, count = struct.unpack_from("<HHH", ico_bytes, 0)

    assert (reserved, image_type) == (0, 1)
    assert count == len(EXPECTED_ICO_SIZES)

    sizes: list[int] = []
    for index in range(count):
        width, height = struct.unpack_from("<BB", ico_bytes, 6 + index * 16)
        decoded_width = 256 if width == 0 else width
        decoded_height = 256 if height == 0 else height
        assert decoded_width == decoded_height
        sizes.append(decoded_width)

    assert tuple(sizes) == EXPECTED_ICO_SIZES
