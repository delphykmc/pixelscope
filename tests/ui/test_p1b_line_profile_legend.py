from __future__ import annotations

import numpy as np
import pyqtgraph as pg

from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineSelection
from pixelscope.ui.line_profile_panel import LineProfilePanel


def _document(name: str, value: int) -> ImageDocument:
    return ImageDocument.from_array(
        np.full((3, 5, 3), value, dtype=np.uint8),
        name,
    )


def _legend_texts(panel: LineProfilePanel, plot_index: int) -> list[str]:
    return [str(label.text) for _sample, label in panel.legends[plot_index].items]


def test_line_profile_legends_use_only_image_id_and_channel_and_larger_markers(
    qtbot: object,
) -> None:
    panel = LineProfilePanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    first = _document("first-long-filename.png", 10)
    second = _document("second-long-filename.png", 20)

    panel.set_documents(
        [first, second],
        LineSelection(0, 1, 4),
    )
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(panel.last_results) == 2,
        timeout=3000,
    )

    assert _legend_texts(panel, 0) == [
        "1 · R",
        "1 · G",
        "1 · B",
        "2 · R",
        "2 · G",
        "2 · B",
    ]
    assert all("filename" not in label for label in _legend_texts(panel, 0))
    overlay_markers = [
        item
        for item in panel.plot.listDataItems()
        if isinstance(item, pg.ScatterPlotItem)
    ]
    assert len(overlay_markers) == 6
    assert all(marker.opts["size"] == 7.0 for marker in overlay_markers)

    panel.view_mode.setCurrentText("Separate by image")
    assert _legend_texts(panel, 0) == ["1 · R", "1 · G", "1 · B"]
    assert _legend_texts(panel, 1) == ["2 · R", "2 · G", "2 · B"]

    panel.view_mode.setCurrentText("Separate by channel")
    assert _legend_texts(panel, 0) == ["1 · R", "2 · R"]
    assert _legend_texts(panel, 1) == ["1 · G", "2 · G"]
    assert _legend_texts(panel, 2) == ["1 · B", "2 · B"]
