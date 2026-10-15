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


def test_histogram_retains_previous_plot_during_background_request(
    qtbot: object,
) -> None:
    panel = ComparisonAnalysisPanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    qtbot.addWidget(panel.histogram_panel)  # type: ignore[attr-defined]
    panel.histogram_panel.resize(820, 560)
    panel.histogram_panel.show()
    source = np.full((12, 18, 3), 35, dtype=np.uint8)
    document = ImageDocument.from_array(source, "original.png")
    panel._documents = [document]
    spec = automatic_histogram_spec(document)
    first = analyze_roi(source, RoiBounds(0, 0, 18, 12), *spec)
    panel.last_results = (first,)
    panel._render((first,), [spec])

    plot = panel.plots[0]
    previous_items = tuple(plot.listDataItems())
    previous_geometry = plot.geometry()
    context_height = panel.histogram_context.height()
    assert previous_items and not plot.isHidden()
    assert context_height > 0

    # A new request should not blank the previous image or remove its
    # histogram rows/axes while the next worker is still calculating.
    panel._invalidate_histogram_presentation()
    panel._set_activity("Calculating...", busy=True)
    qtbot.wait(30)  # type: ignore[attr-defined]
    assert panel.last_results == ()
    assert tuple(plot.listDataItems()) == previous_items
    assert not plot.isHidden()
    assert panel.histogram_context.isVisible()
    assert panel.histogram_context.height() == context_height
    assert plot.geometry() == previous_geometry
    assert not panel.busy.isHidden()

    updated = np.full((12, 18, 3), 91, dtype=np.uint8)
    new_result = analyze_roi(updated, RoiBounds(0, 0, 18, 12), *spec)
    panel._render((new_result,), [spec])
    assert not plot.isHidden()
    assert panel._arranged_histogram_count == 1
    assert len(plot.listDataItems()) == 3
    assert panel.busy.isHidden()
    assert int(new_result.channel_statistics[0].mean) == 91
    panel.shutdown()


def test_analysis_progress_rail_never_resizes_statistics_or_scroll_area(
    qtbot: object,
) -> None:
    panel = ComparisonAnalysisPanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    panel.resize(670, 630)
    panel.show()
    qtbot.wait(30)  # type: ignore[attr-defined]
    assert not panel.activity.isHidden()
    height = panel.activity.height()
    table_geometry = panel.table.geometry()
    group_geometry = panel.statistics_group.geometry()
    activity_geometry = panel.activity.geometry()

    for message, busy in (
        ("Preparing analysis...", True),
        ("Calculating...", True),
        ("", False),
        ("Preparing histogram...", True),
        ("", False),
    ):
        panel._set_activity(message, busy=busy)
        qtbot.wait(5)  # type: ignore[attr-defined]
        assert panel.activity.height() == height
        assert panel.activity.geometry() == activity_geometry
        assert panel.statistics_group.geometry() == group_geometry
        assert panel.table.geometry() == table_geometry
        assert panel.busy.isHidden() is not busy
    panel.shutdown()
