from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

import resvg_py
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "src" / "pixelscope" / "assets" / "icons"
SVG_PATH = ICON_DIR / "pixelscope.svg"
PNG_PATH = ICON_DIR / "pixelscope.png"
ICO_PATH = ICON_DIR / "pixelscope.ico"
ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", maxsplit=1)[-1].lower()


def verify_svg(svg_path: Path) -> None:
    """Reject canonical SVG sources that embed raster images."""
    root = ET.parse(svg_path).getroot()
    if any(_local_name(element.tag) == "image" for element in root.iter()):
        raise RuntimeError("canonical SVG must not contain embedded raster <image> elements")


def _render_rgba(svg_string: str, size: int) -> Image.Image:
    png_bytes = resvg_py.svg_to_bytes(svg_string, width=size, height=size)
    with Image.open(BytesIO(png_bytes)) as decoded:
        return decoded.convert("RGBA")


def build_canonical_assets(svg_path: Path, output_dir: Path) -> tuple[Path, Path]:
    """Render the canonical PNG/ICO derivatives using resvg and Pillow."""
    verify_svg(svg_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    svg_string = svg_path.read_text(encoding="utf-8")
    png_path = output_dir / "pixelscope.png"
    ico_path = output_dir / "pixelscope.ico"

    image_256 = _render_rgba(svg_string, 256)
    try:
        indexed = image_256.quantize(colors=256, dither=Image.Dither.NONE)
        try:
            indexed.save(png_path, format="PNG", optimize=True)
        finally:
            indexed.close()
    finally:
        image_256.close()

    frames = [_render_rgba(svg_string, size) for size in ICO_SIZES]
    try:
        frames[-1].save(
            ico_path,
            format="ICO",
            sizes=[(size, size) for size in ICO_SIZES],
            append_images=frames[:-1],
        )
    finally:
        for frame in frames:
            frame.close()

    return png_path, ico_path


def assert_reproducible_assets(generated_dir: Path, reference_dir: Path) -> None:
    """Fail when regenerated PNG/ICO bytes differ from checked-in canonical assets."""
    for name in ("pixelscope.png", "pixelscope.ico"):
        generated = (generated_dir / name).read_bytes()
        reference = (reference_dir / name).read_bytes()
        if generated != reference:
            raise RuntimeError(f"{name} does not reproduce the checked-in canonical asset")


def check_reproducibility() -> None:
    """Regenerate into an isolated temporary directory and compare exact bytes."""
    verify_svg(SVG_PATH)
    with TemporaryDirectory(prefix="pixelscope-icon-check-") as temp_dir:
        generated_dir = Path(temp_dir)
        build_canonical_assets(SVG_PATH, generated_dir)
        assert_reproducible_assets(generated_dir, ICON_DIR)


def generate(*, check: bool) -> None:
    if check:
        check_reproducibility()
        return
    build_canonical_assets(SVG_PATH, ICON_DIR)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate PixelScope PNG/ICO assets from the canonical SVG."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "regenerate into a temporary directory and fail unless the generated "
            "PNG/ICO exactly match the checked-in assets"
        ),
    )
    args = parser.parse_args()

    generate(check=args.check)
    action = "Reproduced" if args.check else "Generated"
    print(f"{action} {PNG_PATH.relative_to(ROOT)}")
    print(f"{action} {ICO_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
