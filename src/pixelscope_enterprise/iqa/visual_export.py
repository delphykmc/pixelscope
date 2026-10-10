"""Source-coordinate PNG export of client-verified IQA presentation data.

Not a portable result package, a source RAW copy, or an official regional score.
PNG pixels are independent from screen zoom, window dimensions and pane order.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from PySide6.QtGui import QImage

from pixelscope_enterprise.iqa.analysis_model import (
    AnalysisResult,
    AttributeDisplay,
    Roi,
    clipped_cells,
    colorize_spatial_rgba,
    map_polarity_legend,
    roi_statistics,
    spatial_display_half_range,
)

ExportScope = Literal["full", "roi", "both"]
MAX_EXPORT_PIXELS = 16_777_216  # Prevent accidental unbounded RGBA allocations.


def export_folder(parent: Path, result_id: str) -> Path:
    """Use a fixed safe prefix: untrusted result IDs never become arbitrary paths."""

    slug = re.sub(r"[^A-Za-z0-9_-]", "_", result_id)[:48].strip("_") or "result"
    return parent / f"iqa-images-{slug}"


def _rectangles(
    result: AnalysisResult, scope: ExportScope, roi: Roi | None
) -> tuple[tuple[str, tuple[int, int, int, int]], ...]:
    if scope not in ("full", "roi", "both"):
        raise ValueError("unknown visual export scope")
    full = ("full", (0, 0, result.image_width, result.image_height))
    if scope == "full":
        return (full,)
    if roi is None:
        raise ValueError("ROI export requested without an active ROI")
    x, y, width, height = roi
    if not np.isfinite([x, y, width, height]).all() or width <= 0 or height <= 0:
        raise ValueError("ROI geometry is invalid")
    x0 = max(0, min(result.image_width, int(np.floor(x))))
    y0 = max(0, min(result.image_height, int(np.floor(y))))
    x1 = max(0, min(result.image_width, int(np.ceil(x + width))))
    y1 = max(0, min(result.image_height, int(np.ceil(y + height))))
    if x1 <= x0 or y1 <= y0:
        raise ValueError("ROI has no in-image pixel area")
    selected = ("roi", (x0, y0, x1 - x0, y1 - y0))
    return (selected,) if scope == "roi" else (full, selected)


def map_rgba(
    attribute: AttributeDisplay,
    rect: tuple[int, int, int, int],
    effective_half_range: float,
) -> NDArray[np.uint8]:
    """Nearest-cell, pixel-center sampling at ORIGINAL source coordinates.

    Invalid/uncovered cells have alpha 0, not imputed numeric zero. Deliberately
    does not interpolate a low-resolution grid into fictitious image detail.
    """

    grid = attribute.spatial
    if grid is None:
        raise ValueError("selected attribute has no spatial grid")
    x, y, width, height = rect
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        raise ValueError("invalid export rectangle")
    if x + width > grid.image_width or y + height > grid.image_height:
        raise ValueError("export rectangle exceeds source geometry")
    if width * height > MAX_EXPORT_PIXELS:
        raise ValueError("visual export would exceed the bounded pixel budget")

    colors = colorize_spatial_rgba(attribute, effective_half_range)
    assert colors is not None
    xs = x + np.arange(width, dtype=np.float64) + 0.5
    ys = y + np.arange(height, dtype=np.float64) + 0.5
    columns = np.floor((xs - grid.origin_x) / grid.block_width).astype(np.int64)
    rows = np.floor((ys - grid.origin_y) / grid.block_height).astype(np.int64)
    inside_x = (columns >= 0) & (columns < grid.columns)
    inside_y = (rows >= 0) & (rows < grid.rows)
    columns = np.clip(columns, 0, grid.columns - 1)
    rows = np.clip(rows, 0, grid.rows - 1)
    # Indexed array is the only full-sized map intermediate; no QGraphicsScene
    # screenshot or Python loop over 4K pixels.
    rgba = np.ascontiguousarray(colors[rows[:, None], columns[None, :]])
    rgba[..., 3] = np.where(
        inside_y[:, None] & inside_x[None, :], rgba[..., 3], 0
    )
    return rgba


def _save_png(image: QImage, path: Path) -> None:
    if image.isNull() or not image.save(str(path), "PNG"):
        raise OSError(f"PNG writer failed for {path.name}")


def _map_image(
    attribute: AttributeDisplay,
    rect: tuple[int, int, int, int],
    effective_half_range: float,
) -> QImage:
    rgba = map_rgba(attribute, rect, effective_half_range)
    height, width, _channels = rgba.shape
    # The QImage must own its buffer before numpy releases the array.
    return QImage(
        rgba.tobytes(), width, height, width * 4, QImage.Format.Format_RGBA8888
    ).copy()


def write_visual_pngs(
    result: AnalysisResult,
    attribute: AttributeDisplay,
    source_images: tuple[QImage | None, QImage | None],
    destination: Path,
    *,
    scope: ExportScope,
    roi: Roi | None,
    display_range: float,
    display_gain: float,
) -> Path:
    """Publish only a complete, non-overwriting directory of PNGs and audit JSON.

    The caller chooses a parent directory; destination is a fresh sibling path.
    Current GUI thread/QImage ownership is maintained by the UI caller.
    """

    if attribute not in result.attributes:
        raise ValueError("selected Attribute does not belong to the result")
    rectangles = _rectangles(result, scope, roi)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("visual export directory already exists")
    if not destination.parent.is_dir():
        raise FileNotFoundError("visual export parent directory does not exist")
    for _label, (_x, _y, width, height) in rectangles:
        if width * height > MAX_EXPORT_PIXELS:
            raise ValueError("visual export would exceed the bounded pixel budget")

    sources: list[QImage | None] = []
    for image in source_images:
        sources.append(
            image
            if image is not None
            and not image.isNull()
            and image.width() == result.image_width
            and image.height() == result.image_height
            else None
        )
    if not any(image is not None for image in sources) and attribute.spatial is None:
        raise ValueError("no source or selected spatial map is available to export")
    half_range = spatial_display_half_range(display_range, display_gain)
    full_clip: tuple[int, int] | None = (
        clipped_cells(attribute.spatial, half_range)
        if attribute.spatial is not None
        else None
    )
    map_info: dict[str, object] = {
        "attribute_id": attribute.attribute_id,
        "attribute_label": attribute.label,
        "unit": attribute.unit,
        "quality_oriented": attribute.quality_oriented,
        "polarity": map_polarity_legend(attribute),
        "display_range": display_range,
        "display_gain": display_gain,
        "effective_half_range": half_range,
        "clamp_count_scope": "whole_spatial_grid_valid_cells",
        "clipped_valid_cells": full_clip[0] if full_clip is not None else None,
        "total_valid_cells": full_clip[1] if full_clip is not None else None,
        "grid_shape": (
            [attribute.spatial.rows, attribute.spatial.columns]
            if attribute.spatial is not None
            else None
        ),
    }
    if attribute.spatial is not None:
        grid = attribute.spatial
        map_info["grid_geometry"] = {
            "origin_x": grid.origin_x,
            "origin_y": grid.origin_y,
            "block_width": grid.block_width,
            "block_height": grid.block_height,
        }
        map_info["invalid_cells"] = grid.values.size - int(np.count_nonzero(grid.valid_mask))

    staged = Path(tempfile.mkdtemp(prefix=".iqa-png-", dir=destination.parent))
    published = False
    try:
        exported: list[str] = []
        omitted: dict[str, str] = {}
        region_details: dict[str, object] = {}
        for scope_name, rect in rectangles:
            x, y, width, height = rect
            details: dict[str, object] = {"xywh_px": [x, y, width, height]}
            if attribute.spatial is not None:
                stats = roi_statistics(attribute.spatial, (x, y, width, height))
                details["grid_valid_coverage"] = stats.valid_coverage
                details["grid_valid_area_px2"] = stats.valid_area
                details["area_px2"] = stats.roi_area
                details["grid_derived_mean"] = stats.mean
                details["grid_derived_mean_is_official"] = False
            region_details[scope_name] = details
            for index, semantic in enumerate(("A", "B")):
                name = f"source_{semantic}_{scope_name}.png"
                image = sources[index]
                if image is None:
                    omitted[name] = "original RGB unavailable or geometry mismatch"
                    continue
                _save_png(image.copy(x, y, width, height), staged / name)
                exported.append(name)
            map_name = f"selected_map_{scope_name}.png"
            if attribute.spatial is None:
                omitted[map_name] = "selected Attribute has no spatial grid"
            else:
                _save_png(_map_image(attribute, rect, half_range), staged / map_name)
                exported.append(map_name)

        # Not a result serializer: no source absolute paths, pixel arrays, jobs,
        # private server fields or reload contract are included.
        manifest = {
            "schema_version": 1,
            "kind": "nonportable_visual_png_export",
            "result_id": result.result_id,
            "source_a_label": result.source_a_label,
            "source_b_label": result.source_b_label,
            "source_geometry_px": [result.image_width, result.image_height],
            "requested_scope": scope,
            "regions": region_details,
            "selected_map": map_info,
            "exported_files": exported,
            "omitted_files": omitted,
            "notes": [
                "A/B PNGs are decoded displayed originals, not bit-exact RAW copies.",
                "Map uses nearest grid-cell display colors; invalid/uncovered pixels are transparent.",
                "GRID-derived ROI values are descriptive, not full-pair comparisons.",
            ],
        }
        with (staged / "export_info.json").open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(manifest, handle, indent=2, ensure_ascii=False, allow_nan=False)
            handle.write("\n")
        if destination.exists() or destination.is_symlink():
            raise FileExistsError("visual export directory already exists")
        os.rename(staged, destination)
        published = True
        return destination
    finally:
        if not published:
            shutil.rmtree(staged, ignore_errors=True)
