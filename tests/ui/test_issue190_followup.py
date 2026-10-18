from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication
from scripts.issue190_followup import fourk_lane

from pixelscope.app.bootstrap import compose_main_window_presentation
from pixelscope.app.main_window import MainWindow

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


@pytest.mark.parametrize("state", ["OFF", "ON"])
def test_resident_uhd_diagnostic_keeps_source_and_diff_headers_honest(qtbot, state):
    window = MainWindow()
    qtbot.addWidget(window)
    compose_main_window_presentation(window)
    window.resize(1200, 800)
    window.show()
    app = QApplication.instance()

    def wait(predicate):
        qtbot.waitUntil(predicate, timeout=15000)

    try:
        checks = fourk_lane(
            window, app, wait, f"E3K_L1_{state}", {}, {}, lambda: None, lambda: None
        )
        assert "diff_cache_pixels_and_visibility" in checks
        for viewer in window.multi_compare_view.occupied_viewers:
            document = viewer.document
            assert document is not None
            assert viewer.header._display_name == document.display_name
            if document is window._difference_document:
                assert "A-UHD" in viewer.header.difference_a_name.text()
                assert "B-UHD" in viewer.header.difference_b_name.text()
            else:
                assert viewer.header.name.toolTip() == document.display_name
    finally:
        window.close()
