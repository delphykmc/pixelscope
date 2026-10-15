from __future__ import annotations

import numpy as np
import pyqtgraph as pg
import pytest

from pixelscope.core.image_document import ImageDocument
from pixelscope.core.roi import RoiBounds, analyze_roi
from pixelscope.ui.comparison_analysis_panel import (
    ComparisonAnalysisPanel,
    automatic_histogram_spec,
)


@pytest.mark.parametrize(
    ("mode", "expected_visible", "expected_channels"),
    [("Separate", 2, 3), ("Overlay", 1, 6)],
)
def test_first_histogram_plot_show_waits_for_data_and_axis_layout(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    expected_visible: int,
    expected_channels: int,
) -> None:
    panel = ComparisonAnalysisPanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    qtbot.addWidget(panel.histogram_panel)  # type: ignore[attr-defined]
    documents = [
        ImageDocument.from_array(
            np.full((12, 18, 3), 40 + index * 50, dtype=np.uint8),
            f"histogram-{index}.png",
        )
        for index in range(2)
    ]
    panel._documents = documents
    panel.histogram_mode.setCurrentText(mode)
    specs = [automatic_histogram_spec(document) for document in documents]
    results = tuple(
        analyze_roi(
            document.source,
            RoiBounds(0, 0, 18, 12),
            *spec,
        )
        for document, spec in zip(documents, specs, strict=True)
    )

    first_shows: list[int] = []
    original_show = pg.PlotWidget.show

    def inspect_before_first_show(plot: pg.PlotWidget) -> None:
        if plot in panel.plots:
            first_shows.append(panel.plots.index(plot))
            # The first visible histogram frame must already have curves,
            # labels and axes. Showing the empty PlotWidget is a regression.
            assert len(plot.listDataItems()) == expected_channels
            assert not plot.getPlotItem().getAxis("left").isHidden()
            assert not plot.getPlotItem().getAxis("bottom").isHidden()
            assert plot.getPlotItem().getAxis("left").labelText == "Count"
            assert plot.getPlotItem().getAxis("bottom").labelText == "Pixel value"
            x_range = plot.getViewBox().viewRange()[0]
            assert x_range[0] < 40.0 < x_range[1]
        original_show(plot)

    monkeypatch.setattr(pg.PlotWidget, "show", inspect_before_first_show)
    panel._render(results, specs)

    assert first_shows == list(range(expected_visible))
    assert all(not plot.isHidden() for plot in panel.plots[:expected_visible])
    assert all(plot.isHidden() for plot in panel.plots[expected_visible:])
    panel.shutdown()
