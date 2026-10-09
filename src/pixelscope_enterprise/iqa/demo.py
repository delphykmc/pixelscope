"""Synthetic public-safe manual preview of the independent IQA Analysis Window.

Run with an environment containing the project's PySide6 dependency:
    python -m pixelscope_enterprise.iqa.demo

No MAIN window, job, real image, data-service, transport or proprietary artifacts.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from PySide6.QtGui import QColor, QImage
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
        grid = SpatialMap(values, valid, width, height, float(block), float(block))
        # Deliberately exercise independent availability, unlike a polished
        # screenshot where every metric would misleadingly have both outputs.
        official = (
            None
            if index in (1, 11)
            else 0.0
            if index == 2
            else 0.01
            if index == 3
            else 7.0
            if index == 4
            else -7.0
            if index == 5
            else offset
        )
        attributes.append(
            AttributeDisplay(
                attribute_id=f"synthetic_{index:02d}",
                label=f"Synthetic attribute {index + 1}",
                unit=unit,
                group="Relative power" if index < 10 else "Signed delta",
                official_value=official,
                official_availability="missing" if official is None else "available",
                quality_oriented=index < 10,
                fixed_range=6.0 if index < 10 else 3.0,
                spatial=None if index in (0, 11) else grid,
                # An explicitly public *illustrative* axis, not inferred from
                # the map color range or a private server schema.
                chart_axis_range=4.0 if index < 10 else 2.0,
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
    """Run demo with optional `--rgb` local 4K synthetic original images."""

    argv = list(arguments) if arguments is not None else sys.argv[1:]
    use_rgb = "--rgb" in argv
    app = QApplication([arg for arg in argv if arg != "--rgb"])
    manager = AnalysisWindowManager()
    if not use_rgb:
        manager.show(make_synthetic_result())
        return app.exec()

    # Created only in the local temporary directory, never committed/uploaded.
    # Synthetic RGB imagery demonstrates that the A/B panes really render and
    # continue to be reused while the selected Map changes.
    with TemporaryDirectory(prefix="pixelscope-ux1-rgb-") as directory:
        paths: list[Path] = []
        for label, color in (
            ("a", QColor(115, 140, 159)),
            ("b", QColor(134, 127, 114)),
        ):
            filename = Path(directory) / f"synthetic-{label}-4k.png"
            image = QImage(3840, 2160, QImage.Format.Format_RGB32)
            image.fill(color)
            if not image.save(str(filename)):
                raise RuntimeError("could not save public-safe synthetic RGB preview")
            paths.append(filename)
        manager.show(
            replace(make_synthetic_result(), source_a=paths[0], source_b=paths[1])
        )
        return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
