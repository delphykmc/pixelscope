"""Client-only measurement CSV export; not a saved IQA Result package.

Full-pair comparison values and GRID-DERIVED ROI estimates are different
measurement scopes. Neither display gain nor any rendered map enters export.
"""

from __future__ import annotations

import csv
import io
import os
import tempfile
from pathlib import Path

import numpy as np

from pixelscope_enterprise.iqa.analysis_model import AnalysisResult, Roi, roi_statistics

COLUMNS = (
    "result_id",
    "source_a_label",
    "source_b_label",
    "image_width_px",
    "image_height_px",
    "measurement_scope",
    "attribute_id",
    "attribute_label",
    "unit",
    "quality_oriented",
    "value",
    "availability",
    "roi_x_px",
    "roi_y_px",
    "roi_width_px",
    "roi_height_px",
    "roi_valid_area_px2",
    "roi_total_area_px2",
    "roi_valid_coverage",
)


def _safe_text(value: str) -> str:
    """Prevent CSV spreadsheet formula execution from untrusted labels and IDs."""

    if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
        return "'" + value
    return value


def _number(value: float | int | None) -> str:
    """An unavailable measurement is blank, never a fabricated numeric zero."""

    if value is None:
        return ""
    return str(value)


def build_measurements_csv(result: AnalysisResult, roi: Roi | None = None) -> str:
    """Return deterministic RFC-4180-style CSV from immutable scientific data.

    A numeric 0.0 remains an actual zero. A missing/failed/invalid GRID value
    stays empty. ROI rows are included only if a valid source-coordinate ROI
    and an Attribute's grid are available. Never infer a full-pair score for an ROI.
    """

    if roi is not None:
        x, y, width, height = roi
        if (
            not np.isfinite(roi).all()
            or x < 0
            or y < 0
            or width <= 0
            or height <= 0
            or x + width > result.image_width
            or y + height > result.image_height
        ):
            raise ValueError("ROI must lie within the source image")

    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(COLUMNS)
    shared = (
        _safe_text(result.result_id),
        _safe_text(result.source_a_label),
        _safe_text(result.source_b_label),
        result.image_width,
        result.image_height,
    )

    for attribute in result.attributes:
        meta = (
            _safe_text(attribute.attribute_id),
            _safe_text(attribute.label),
            _safe_text(attribute.unit),
            "yes" if attribute.quality_oriented else "no",
        )
        writer.writerow(
            (
                *shared,
                "FULL_PAIR_COMPARISON",
                *meta,
                _number(attribute.official_value),
                attribute.official_availability,
                *("",) * 7,
            )
        )
        if roi is None or attribute.spatial is None:
            continue
        stats = roi_statistics(attribute.spatial, roi)
        writer.writerow(
            (
                *shared,
                "GRID_DERIVED_ROI",
                *meta,
                _number(stats.mean),
                "available" if stats.mean is not None else "missing",
                *(_number(v) for v in roi),
                _number(stats.valid_area),
                _number(stats.roi_area),
                _number(stats.valid_coverage),
            )
        )
    return buffer.getvalue()


def write_measurements_csv(result: AnalysisResult, roi: Roi | None, destination: Path) -> None:
    """Atomically write UTF-8-with-BOM CSV for Windows Excel interoperability."""

    payload = build_measurements_csv(result, roi)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8-sig",
            newline="",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as file:
            temporary = Path(file.name)
            file.write(payload)
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
