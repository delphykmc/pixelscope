"""Synthetic public-safe manual preview of the independent IQA Analysis Window.

Run with an environment containing the project's PySide6 dependency:
    python -m pixelscope_enterprise.iqa.demo

No MAIN window, job, real image, data-service, transport or proprietary artifacts.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from PySide6.QtWidgets import QApplication

from pixelscope_enterprise.iqa.analysis_model import (
    AnalysisResult,
    AttributeDisplay,
    SpatialMap,
)
from pixelscope_enterprise.iqa.analysis_window import AnalysisWindowManager


def make_synthetic_result(result_id: str = "public-synthetic-pair") -> AnalysisResult:
    """Deterministic company-neutral 4K/64-pixel-block visual evidence."""

    width, height, block = 3840, 2160, 64
    cols, rows = (width + block - 1) // block, (height + block - 1) // block
    yy, xx = np.mgrid[0:rows, 0:cols]
    valid = np.ones((rows, cols), dtype=bool)
    valid[2:5, 7:11] = False  # Synthetic missing area, never zero-imputed.
    attributes: list[AttributeDisplay] = []
    for index in range(12):
        unit = "dB" if index < 10 else "delta"
        offset = (index - 5) / 4.0
        values = 3.0 * np.sin(xx / 7 + index / 3) * np.cos(yy / 6) + offset
        grid = SpatialMap(
            values, valid, width, height, float(block), float(block)
        )
        attributes.append(
            AttributeDisplay(
                attribute_id=f"synthetic_{index:02d}",
                label=f"Synthetic attribute {index + 1}",
                unit=unit,
                group="Relative power" if index < 10 else "Signed delta",
                official_value=None if index == 11 else offset,
                official_availability="missing" if index == 11 else "available",
                quality_oriented=index < 10,
                fixed_range=6.0 if index < 10 else 3.0,
                spatial=None if index == 11 else grid,
            )
        )
    return AnalysisResult(
        result_id=result_id,
        image_width=width,
        image_height=height,
        source_a_label="Synthetic source A (not distributed)",
        source_b_label="Synthetic source B (not distributed)",
        attributes=tuple(attributes),
    )


def main(arguments: Sequence[str] | None = None) -> int:
    app = QApplication(list(arguments) if arguments is not None else [])
    manager = AnalysisWindowManager()
    manager.show(make_synthetic_result())
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
