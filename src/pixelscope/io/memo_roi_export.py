"""Export the current comparison-page ROI as one PNG per source preview.

This is a simple evidence export, independent of Review persistence or RAW/YUV
source attestation. Crops use exact half-open reference pixel bounds and 8-bit
canonical display previews, with no tile overlays or downscaled screenshots.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray

from pixelscope.core.roi import RoiBounds, roi_fits_shape

PreviewEntry = tuple[str, NDArray[np.uint8]]


def _filename(index: int, name: str, roi: RoiBounds) -> str:
    basename = Path(name).stem
    safe = re.sub(r"[^\w.-]+", "_", basename, flags=re.UNICODE).strip("._")[:68]
    if not safe:
        safe = "image"
    return (
        f"{index:02d}_{safe}_ROI_x{roi.x}_y{roi.y}_"
        f"w{roi.width}_h{roi.height}.png"
    )


def _encode_png(preview: NDArray[np.uint8], roi: RoiBounds) -> bytes:
    region = np.ascontiguousarray(preview[roi.y : roi.bottom, roi.x : roi.right])
    if region.ndim == 3 and region.shape[2] == 3:
        source = cv2.cvtColor(region, cv2.COLOR_RGB2BGR)
    elif region.ndim == 3 and region.shape[2] == 4:
        source = cv2.cvtColor(region, cv2.COLOR_RGBA2BGRA)
    elif region.ndim == 2:
        source = region
    else:
        raise ValueError("ROI PNG supports Gray, RGB and RGBA previews")
    ok, encoded = cv2.imencode(".png", source)
    if not ok:
        raise OSError("ROI PNG encoding failed")
    return encoded.tobytes()


def export_roi_pngs(
    directory: Path,
    images: Sequence[PreviewEntry],
    roi: RoiBounds,
    *,
    cancel: Callable[[], bool] | None = None,
) -> tuple[Path, ...]:
    """Validate all selected previews, then export without overwriting user files.

    Partial files created by this invocation are removed if any write fails;
    unrelated existing files remain untouched. Repeated exports gain a numbered
    suffix rather than overwriting previous evidence.
    """
    if not isinstance(directory, Path) or not directory.is_dir():
        raise ValueError("Select an existing output directory")
    if not isinstance(roi, RoiBounds):
        raise ValueError("Draw an ROI before exporting")
    if not 1 <= len(images) <= 6:
        raise ValueError("ROI export requires 1–6 current page images")

    payloads: list[tuple[str, bytes]] = []
    for index, (name, preview) in enumerate(images, 1):
        if cancel is not None and cancel():
            raise RuntimeError("ROI PNG export cancelled")
        if not isinstance(preview, np.ndarray) or preview.dtype != np.uint8:
            raise ValueError("ROI PNG requires a ready 8-bit display preview")
        if not roi_fits_shape(preview.shape, roi):
            raise ValueError(f"ROI is outside {name}; no crops were exported")
        payloads.append((_filename(index, name, roi), _encode_png(preview, roi)))

    created: list[Path] = []
    try:
        for filename, payload in payloads:
            if cancel is not None and cancel():
                raise RuntimeError("ROI PNG export cancelled")
            stem = Path(filename).stem
            candidate = directory / filename
            number = 2
            while candidate.exists():
                candidate = directory / f"{stem}_{number}.png"
                number += 1
            # Exclusive create also prevents overwrites if another process
            # introduces the same filename between existence check and open.
            with candidate.open("xb") as handle:
                created.append(candidate)
                handle.write(payload)
        return tuple(created)
    except BaseException:
        for candidate in created:
            candidate.unlink(missing_ok=True)
        raise
