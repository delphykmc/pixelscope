from __future__ import annotations

import numpy as np

from pixelscope.core.image_document import ImageDocument
from pixelscope.ui.comparison_analysis_panel import (
    ComparisonAnalysisPanel,
    automatic_histogram_spec,
    histogram_display_values,
)


def _document(dtype: np.dtype[np.generic], bit_depth: int) -> ImageDocument:
    return ImageDocument.from_array(
        np.zeros((4, 5, 3), dtype=dtype),
        f"{bit_depth}-bit.png",
        bit_depth=bit_depth,
    )


def test_auto_histogram_bins_are_capped_without_losing_native_range() -> None:
    eight_bit = _document(np.dtype(np.uint8), 8)
    twelve_bit = _document(np.dtype(np.uint16), 12)
    sixteen_bit = _document(np.dtype(np.uint16), 16)

    assert automatic_histogram_spec(eight_bit) == (256, (0.0, 256.0))
    assert automatic_histogram_spec(twelve_bit) == (4096, (0.0, 4096.0))
    assert automatic_histogram_spec(sixteen_bit) == (4096, (0.0, 65536.0))


def test_explicit_histogram_bins_preserve_native_code_range() -> None:
    document = _document(np.dtype(np.uint16), 12)

    assert automatic_histogram_spec(document, 256) == (256, (0.0, 4096.0))
    assert automatic_histogram_spec(document, 1024) == (1024, (0.0, 4096.0))
    assert automatic_histogram_spec(document, 4096) == (4096, (0.0, 4096.0))


def test_histogram_display_values_support_count_normalized_and_log() -> None:
    counts = np.asarray([0, 9, 99], dtype=np.int64)

    np.testing.assert_array_equal(
        histogram_display_values(counts, "Count"),
        np.asarray([0.0, 9.0, 99.0]),
    )
    np.testing.assert_allclose(
        histogram_display_values(counts, "Normalized"),
        np.asarray([0.0, 9.0 / 108.0, 99.0 / 108.0]),
    )
    np.testing.assert_allclose(
        histogram_display_values(counts, "Log count"),
        np.asarray([0.0, 1.0, 2.0]),
    )


def test_histogram_controls_expose_bounded_bins_and_log_count(qtbot: object) -> None:
    panel = ComparisonAnalysisPanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]

    assert [
        panel.histogram_bins.itemText(index)
        for index in range(panel.histogram_bins.count())
    ] == ["Auto", "256", "1024", "4096"]
    assert [
        panel.histogram_units.itemText(index)
        for index in range(panel.histogram_units.count())
    ] == ["Count", "Normalized", "Log count"]

    assert panel._selected_histogram_bins() is None
    panel.histogram_bins.setCurrentText("1024")
    assert panel._selected_histogram_bins() == 1024
