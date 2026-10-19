from __future__ import annotations

import numpy as np
import pytest

from pixelscope.app.bootstrap import compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.display_transform import render_ordinary_display_preview
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.roi import RoiBounds
from pixelscope.ui.display_gain import display_gain_state

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


@pytest.mark.parametrize("layout", ["Single View", "Multi View"])
def test_cycle_preserves_gain_roi_and_difference_pair(qtbot, layout: str) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    compose_main_window_presentation(window)
    documents = [
        ImageDocument.from_array(np.full((240, 320), value, dtype=np.uint8), name)
        for value, name in [(10, "a.png"), (100, "b.png")]
    ]
    for document in documents:
        window.add_document(document, select=False)
    ids = [document.document_id for document in documents]
    window.quick_compare_controller._apply_registered_drop(ids)
    qtbot.waitUntil(
        lambda: window.difference_panel.has_cached_map() and window.diff_action.isEnabled()
    )
    window.diff_action.setChecked(True)
    window.set_layout_mode(layout)
    window.show()
    bounds = RoiBounds(20, 30, 80, 90)
    window._shared_roi_changed(bounds)
    pair = window._difference_source_ids
    gain = display_gain_state()
    gain.set_gain(2.0)
    try:
        for expected in [documents[1], documents[0], documents[1]]:
            window.cycle_primary_source()
            assert window._focus_document_id == expected.document_id
            assert window._difference_source_ids == pair == tuple(ids)
            assert window.diff_action.isChecked()
            assert window._shared_roi == bounds
            assert [document.document_id for document in window.selected_documents] == ids
            viewers = (
                [window.viewer]
                if layout == "Single View"
                else [
                    viewer
                    for viewer in window.multi_compare_view.occupied_viewers
                    if viewer.document.channel_layout != "DIFFERENCE"
                ]
            )
            qtbot.waitUntil(
                lambda viewers=viewers: all(
                    viewer._displayed_gain == 2.0 and viewer._display_preview_worker is None
                    for viewer in viewers
                )
            )
            if layout == "Single View":
                assert window.viewer.document is expected
            for viewer in viewers:
                document = viewer.document
                expected_preview = render_ordinary_display_preview(
                    document.source,
                    channel_layout=document.channel_layout,
                    transform=document.display_transform,
                    canonical_preview=document.preview,
                    gain=2.0,
                )
                assert np.array_equal(viewer.image_item.image, expected_preview)
    finally:
        gain.reset()
        window.close()
