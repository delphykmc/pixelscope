import numpy as np
import pytest
from PySide6.QtCore import QSettings

from pixelscope.app.bootstrap import compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.display_transform import render_absolute_difference
from pixelscope.core.image_document import ImageDocument
from pixelscope.ui import difference_panel as panel_module


def reference(diff, gain=1.0):
    if gain <= 0:
        raise ValueError("display gain must be greater than zero")
    maximum = max(float(np.max(diff)), 1.0)
    scaled = np.clip(diff.astype(np.float32) * gain / maximum, 0.0, 1.0)
    return np.ascontiguousarray(np.rint(scaled * 255.0).astype(np.uint8))


def signature(viewer):
    ranges = viewer.view_box.viewRange()
    return np.array([*(sum(bounds) / 2 for bounds in ranges), *viewer.view_box.viewPixelSize()])


@pytest.mark.parametrize("channels", [1, 3])
def test_c1_matches_reference_pixels_and_geometry_through_five_cycles(
    qtbot, monkeypatch, channels, isolated_qsettings
):
    shape = (64, 96) if channels == 1 else (64, 96, 3)
    a = np.random.default_rng(192).integers(0, 128, shape, dtype=np.uint8)
    b = np.flip(a, axis=0).copy()
    absolute = np.abs(a.astype(np.int16) - b.astype(np.int16)).astype(np.uint8)
    expected = reference(absolute)

    def run(renderer):
        monkeypatch.setattr(panel_module, "render_absolute_difference", renderer)
        QSettings().clear()
        window = MainWindow()
        qtbot.addWidget(window)
        compose_main_window_presentation(window)
        window.resize(1200, 800)
        window.show()
        documents = [
            ImageDocument.from_array(array.copy(), name) for array, name in ((a, "A"), (b, "B"))
        ]
        states = []
        try:
            for document in documents:
                window.add_document(document, select=False)
            window._select_document_ids([d.document_id for d in documents])
            window.set_layout_mode("Multi View")
            panel = window.difference_panel
            panel.calculate_difference(publish_result=False)
            qtbot.waitUntil(lambda: panel.has_cached_map() and panel._worker is None)
            assert not window.diff_action.isChecked() and window._difference_document is None

            def viewers():
                return [
                    next(
                        v
                        for v in window.multi_compare_view.occupied_viewers
                        if v.document is document
                    )
                    for document in documents
                ]

            def snapshot():
                qtbot.waitUntil(lambda: not window.multi_compare_view._layout_refit_active)
                qtbot.wait(10)
                states.append(np.stack([signature(v) for v in viewers()]))

            snapshot()
            window.diff_action.trigger()
            qtbot.waitUntil(lambda: window._difference_document is not None)
            assert np.array_equal(window._difference_document.source, absolute)
            assert np.array_equal(window._difference_document.preview, expected)
            snapshot()
            window.diff_action.trigger()
            snapshot()
            viewers()[0].view_box.setRange(xRange=(-20, 40), yRange=(-10, 30), padding=0)
            snapshot()
            for _ in range(5):
                window.diff_action.trigger()
                assert window.selected_documents == documents
                assert np.array_equal(window._difference_document.preview, expected)
                snapshot()
                window.diff_action.trigger()
                snapshot()
            assert np.array_equal(documents[0].source, a)
            assert np.array_equal(documents[1].source, b)
            anchor = viewers()[0]
            original = signature(anchor)
            anchor.view_box.translateBy(x=3, y=5)
            assert not np.allclose(signature(anchor)[:2], original[:2], rtol=1e-8, atol=1e-8)
            shifted = signature(anchor)
            anchor.view_box.scaleBy((1.25, 1.25))
            assert not np.allclose(signature(anchor)[2:], shifted[2:], rtol=1e-8, atol=1e-8)
            return np.stack(states)
        finally:
            window.close()

    baseline = run(reference)
    candidate = run(render_absolute_difference)
    # Assert parity against the actual baseline transition, not universal numeric
    # range invariance. Both implementations can have an existing fit transition.
    np.testing.assert_allclose(candidate, baseline, rtol=1e-8, atol=1e-8)
