from __future__ import annotations

import numpy as np
import pytest

from pixelscope.app.main_window import MainWindow
from pixelscope.app.raw_input_compatibility import install_raw_input_compatibility
from pixelscope.app.yuv_difference_semantics import install_native_yuv_difference
from pixelscope.app.yuv_input_semantics import install_native_yuv_semantics
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.yuv import NativeYuvFrame

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _document(name: str, *, y_delta: int = 0, u_delta: int = 0) -> ImageDocument:
    y = np.arange(16, dtype=np.uint8).reshape(4, 4)
    u = np.array([[40, 50], [60, 70]], dtype=np.uint8)
    v = np.array([[180, 190], [200, 210]], dtype=np.uint8)
    if y_delta:
        y = (y.astype(np.uint16) + y_delta).astype(np.uint8)
    if u_delta:
        u = (u.astype(np.uint16) + u_delta).astype(np.uint8)
    return ImageDocument.from_yuv(
        NativeYuvFrame(y=y, u=u, v=v, layout="YUV420"),
        name,
    )


def _window(qtbot: object) -> MainWindow:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    install_raw_input_compatibility(window)
    install_native_yuv_semantics(window)
    install_native_yuv_difference(window)
    return window


def test_wp_c2_retires_only_wp_c1_difference_block(qtbot: object) -> None:
    window = _window(qtbot)
    controller = window.native_yuv_semantics_controller

    assert window.native_yuv_difference_installed is True
    assert window.difference_panel.set_documents == controller._difference_set_documents_original
    assert window.difference_panel.calculate_difference == controller._difference_calculate_original
    assert window.difference_panel.set_documents != controller.set_difference_documents

    first = _document("a.yuv")
    second = _document("b.yuv", y_delta=3, u_delta=7)
    window.difference_panel.set_documents(
        [first, second],
        (first.document_id, second.document_id),
    )

    assert window.difference_panel.a_selector.count() == 2
    assert window.difference_panel.b_selector.count() == 2
    assert [
        window.difference_panel.channel.itemText(index)
        for index in range(window.difference_panel.channel.count())
    ] == ["Y", "U", "V"]
    assert window.difference_panel.channel.currentText() == "Y"
    assert window.difference_panel.calculate.isEnabled()
    assert "WP-C2" not in window.difference_panel.status.text()

    window.close()


def test_production_yuv_channel_calculation_keeps_native_u_resolution(qtbot: object) -> None:
    window = _window(qtbot)
    first = _document("a.yuv")
    second = _document("b.yuv", u_delta=7)
    panel = window.difference_panel
    panel.set_documents([first, second], (first.document_id, second.document_id))
    panel.channel.setCurrentText("U")

    panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: panel.last_result is not None and panel.cached_result_for_current() is not None,
        timeout=3000,
    )

    cached = panel.cached_result_for_current()
    assert cached is not None
    assert cached.channel_layout == "YUV420"
    assert cached.absolute.shape == (2, 2)
    np.testing.assert_array_equal(cached.absolute, np.full((2, 2), 7, dtype=np.uint8))
    assert panel.last_result is not None
    assert panel.last_result.mae == 7.0

    window.close()
