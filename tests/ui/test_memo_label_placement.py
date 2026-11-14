import numpy as np
import pytest

from pixelscope.core.image_document import ImageDocument
from pixelscope.core.roi import RoiBounds
from pixelscope.ui import image_viewer as viewer_module
from pixelscope.ui.image_viewer import ImageViewer


@pytest.mark.parametrize("width,height", [(340, 300), (640, 420)])
def test_memo_labels_avoid_collisions_and_edges_after_zoom_resize(qtbot, width, height):
    viewer = ImageViewer()
    qtbot.addWidget(viewer)
    viewer.resize(width, height)
    document = ImageDocument.from_array(np.zeros((360, 640), np.uint8), "source")
    viewer.set_document(document)
    viewer.show()
    qtbot.waitUntil(lambda: not viewer._geometry_timer.isActive())
    regions = (
        ("ROI 1", RoiBounds(100, 100, 150, 100), False),
        ("ROI 2", RoiBounds(105, 105, 140, 90), True),
        ("ROI 3", RoiBounds(620, 340, 20, 20), False),
    )
    original_source = document.source
    viewer.set_memo_regions(regions)
    rectangles = [item[0].rect() for item in viewer._memo_items]

    def verify():
        visible = viewer.view_box.sceneBoundingRect()
        labels = [item[1].sceneBoundingRect() for item in viewer._memo_items if item[1].isVisible()]
        assert all(visible.contains(rect) for rect in labels)
        assert all(not a.intersects(b) for i, a in enumerate(labels) for b in labels[i + 1 :])
        assert [item[0].rect() for item in viewer._memo_items] == rectangles
        assert viewer._memo_regions == regions and document.source is original_source

    verify()
    viewer.zoom_by(1.5)
    verify()
    viewer.resize(width + 80, height + 40)
    qtbot.waitUntil(lambda: not viewer._geometry_timer.isActive())
    verify()
    viewer.view_box.setRange(xRange=(1000, 1100), yRange=(1000, 1100), padding=0)
    assert all(not label.isVisible() for _, label in viewer._memo_items)
    viewer.fit_image()
    qtbot.waitUntil(lambda: not viewer._geometry_timer.isActive())
    assert all(label.isVisible() for _, label in viewer._memo_items)
    verify()
    viewer.set_memo_regions(())
    assert not viewer._memo_items


def test_dense_memo_label_search_has_a_total_work_budget(qtbot, monkeypatch):
    from PySide6.QtCore import QRectF

    monkeypatch.setattr(viewer_module, "_MEMO_LABEL_INTERSECTION_BUDGET", 32)
    viewer = ImageViewer()
    qtbot.addWidget(viewer)
    viewer.resize(300, 240)
    viewer.set_document(ImageDocument.from_array(np.zeros((80, 80), np.uint8), "dense"))
    viewer.show()
    qtbot.waitUntil(lambda: not viewer._geometry_timer.isActive())
    calls = []
    original = QRectF.intersected

    def counted(rect, other):
        calls.append(1)
        return original(rect, other)

    monkeypatch.setattr(QRectF, "intersected", counted)
    viewer.set_memo_regions(
        tuple((f"ROI {i + 1}", RoiBounds(10, 10, 20, 20), False) for i in range(80))
    )
    assert 0 < len(calls) <= 32
    assert len(viewer._memo_items) == 80
