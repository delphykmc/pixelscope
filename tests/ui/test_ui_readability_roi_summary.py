"""UI-01: keep bounded ROI context readable without forcing sidebar width."""
from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from pixelscope.app.bootstrap import compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def test_memo_narrow_roi_summary_reflows_without_changing_analysis(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    compose_main_window_presentation(window)
    window.setFixedSize(1024, 720)
    documents = [
        ImageDocument.from_array(np.full((360, 640, 3), i, np.uint8), f"image{i}.png")
        for i in range(2)
    ]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([d.document_id for d in documents])
    window.set_layout_mode("Multi View")
    window.show()
    panel = window.comparison_analysis_panel
    qtbot.waitUntil(lambda: panel.get_current_analysis_token() is not None, timeout=10000)
    window.named_review_coordinator.show()
    followup = window.issue77_ui_design_followup
    qtbot.waitUntil(lambda: window.main_splitter.widget(0).width() < 230)
    qtbot.waitUntil(lambda: panel.roi_label._paint_text() == panel.roi_label.text())
    before = (
        tuple((d.document_id, d.generation, id(d.source)) for d in documents),
        window._shared_roi,
        panel._request_signature,
    )
    for width in (320, 167, 390, 180):
        window.setFixedSize(1400 if width >= 320 else 1024, 720)
        QApplication.processEvents()
        total = sum(window.main_splitter.sizes())
        window.main_splitter.setSizes([width, max(1, total - width)])
        qtbot.waitUntil(lambda: panel.roi_label._paint_text() == panel.roi_label.text())
        expected = (1, 1, 1, 1) if width >= 320 else (2, 0, 1, 3)
        qtbot.waitUntil(
            lambda expected=expected: panel.region_layout.getItemPosition(
                panel.region_layout.indexOf(panel.roi_label)
            )
            == expected
        )
        for control in (panel.roi_label, panel.region_scope, followup.roi_edit_button):
            assert control.geometry().left() >= 0
            assert control.geometry().right() < panel.region_group.width()
        assert before == (
            tuple((d.document_id, d.generation, id(d.source)) for d in documents),
            window._shared_roi,
            panel._request_signature,
        )
    assert "Width 640" in panel.roi_label.toolTip()
    original_font = panel.region_group.font()
    larger_font = panel.region_group.font()
    larger_font.setPointSizeF(original_font.pointSizeF() + 1)
    panel.region_group.setFont(larger_font)
    qtbot.waitUntil(lambda: panel.roi_label._paint_text() == panel.roi_label.text())
    panel.region_group.setFont(original_font)
    qtbot.waitUntil(lambda: panel.roi_label._paint_text() == panel.roi_label.text())
    assert followup.roi_edit_button.isEnabled()
    window.close()
