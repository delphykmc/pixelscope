from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from pixelscope.core.bayer import render_bayer_preview
from pixelscope.core.display_transform import DisplayTransform
from pixelscope.core.image_document import ImageDocument


class ImageReadError(ValueError):
    """User-facing error for unsupported or corrupt ordinary image files."""


def read_image(path: str | Path) -> ImageDocument:
    """Decode a Unicode-safe PNG/BMP/JPEG and normalize OpenCV channels to RGB(A)."""

    source_path = Path(path)
    if source_path.suffix.lower() not in (".png", ".bmp", ".jpg", ".jpeg"):
        raise ImageReadError("Supported image formats are PNG, BMP, and JPEG")
    try:
        encoded = np.fromfile(source_path, dtype=np.uint8)
    except OSError as exc:
        raise ImageReadError(f"Cannot read image file: {exc}") from exc
    decoded = cv2.imdecode(encoded, cv2.IMREAD_UNCHANGED)
    if decoded is None:
        raise ImageReadError("The file is not a valid or supported PNG/BMP/JPEG image")
    if decoded.ndim == 2:
        image = decoded
        layout = "GRAY"
    elif decoded.ndim == 3 and decoded.shape[2] == 3:
        image = cv2.cvtColor(decoded, cv2.COLOR_BGR2RGB)
        layout = "RGB"
    elif decoded.ndim == 3 and decoded.shape[2] == 4:
        image = cv2.cvtColor(decoded, cv2.COLOR_BGRA2RGBA)
        layout = "RGBA"
    else:
        raise ImageReadError(f"Unsupported decoded image shape: {decoded.shape}")
    return ImageDocument.from_array(
        image,
        display_name=source_path.name,
        source_path=source_path,
        channel_layout=layout,
    )


def read_raw_document(path: str | Path, profile_path: str | Path) -> ImageDocument:
    from pixelscope.io.raw_profile import RawProfile
    from pixelscope.io.raw_reader import read_raw

    source_path = Path(path)
    profile = RawProfile.load_json(profile_path)
    source = read_raw(source_path, profile)
    transform = DisplayTransform(
        black_level=profile.display_black_level,
        white_level=profile.white_level,
    )
    return ImageDocument.from_array(
        source,
        display_name=source_path.name,
        source_path=source_path,
        channel_layout=profile.channel_layout,
        bit_depth=profile.bit_depth,
        raw_profile=profile,
        display_transform=transform,
        prepared_preview=(
            render_bayer_preview(source, transform) if profile.channel_layout == "BAYER" else None
        ),
    )
