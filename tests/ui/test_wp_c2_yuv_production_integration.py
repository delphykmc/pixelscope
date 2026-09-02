from __future__ import annotations

import numpy as np
import pytest

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.yuv import NativeYuvFrame
from pixelscope.ui.difference_panel import DifferencePanel

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
    _compose_main_window_presentation(window)
    return window


def _select_pair(
    window: MainWindow,
    first: ImageDocument,
    second: ImageDocument,
) -> DifferencePanel:
    """Bind a YUV pair through the real Registered -> Selected -> Current Page path."""

    window.add_document(first, select=False)
    window.add_document(second, select=False)
    window._select_document_ids([first.document_id, second.document_id])
    panel = window.difference_panel
    pair = panel.selected_documents()
    assert pair is not None
    assert {pair[0].document_id, pair[1].document_id} == {
        first.document_id,
        second.document_id,
    }
    return panel


def _wait_for_presented_difference(window: MainWindow, qtbot: object) -> ImageDocument:
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_document is not None
        and window.__dict__.get("_difference_result_key")
        == window.difference_panel._cache_key(),
        timeout=3000,
    )
    result = window._difference_document
    assert result is not None
    return result


def _mark_difference_visible(window: MainWindow) -> None:
    # Exercise the reviewer's toolbar-visible transition while the pair is owned by
    # the real Current Comparison Page. The lifecycle owns subsequent teardown/restore.
    window.diff_action.blockSignals(True)
    window.diff_action.setChecked(True)
    window.diff_action.blockSignals(False)


def test_wp_c2_retires_only_wp_c1_difference_block(qtbot: object) -> None:
    window = _window(qtbot)
    controller = window.native_yuv_semantics_controller
    lifecycle = window.native_yuv_difference_presentation_lifecycle

    assert window.native_yuv_difference_installed is True
    assert lifecycle._original_set_documents == controller._difference_set_documents_original
    assert window.difference_panel.set_documents == lifecycle.set_documents
    assert window.difference_panel.calculate_difference == controller._difference_calculate_original
    assert window.difference_panel.set_documents != controller.set_difference_documents

    first = _document("a.yuv")
    second = _document("b.yuv", y_delta=3, u_delta=7)
    panel = _select_pair(window, first, second)

    assert panel.a_selector.count() == 2
    assert panel.b_selector.count() == 2
    assert [panel.channel.itemText(index) for index in range(panel.channel.count())] == [
        "Y",
        "U",
        "V",
    ]
    assert panel.channel.currentText() == "Y"
    assert panel.calculate.isEnabled()
    assert "WP-C2" not in panel.status.text()

    window.close()


def test_production_yuv_channel_calculation_keeps_native_u_resolution(qtbot: object) -> None:
    window = _window(qtbot)
    first = _document("a.yuv")
    second = _document("b.yuv", u_delta=7)
    panel = _select_pair(window, first, second)
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


def test_uncached_yuv_channel_switch_clears_stale_presented_plane(qtbot: object) -> None:
    window = _window(qtbot)
    first = _document("a.yuv")
    second = _document("b.yuv", y_delta=3, u_delta=7)
    panel = _select_pair(window, first, second)

    panel.calculate_difference()
    presented_y = _wait_for_presented_difference(window, qtbot)
    assert presented_y.source is not None
    assert presented_y.source.shape == (4, 4)
    np.testing.assert_array_equal(presented_y.source, np.full((4, 4), 3, dtype=np.uint8))
    y_key = panel._cache_key()
    assert y_key is not None
    assert window.__dict__["_difference_result_key"] == y_key

    _mark_difference_visible(window)
    panel.channel.setCurrentText("U")

    assert panel.cached_result_for_current() is None
    assert window._difference_document is None
    assert window.__dict__["_difference_result_key"] is None
    assert not window.diff_action.isChecked()

    window.close()


def test_cached_yuv_channel_switch_rebinds_visible_result_to_exact_plane(qtbot: object) -> None:
    window = _window(qtbot)
    first = _document("a.yuv")
    second = _document("b.yuv", y_delta=3, u_delta=7)
    panel = _select_pair(window, first, second)

    panel.calculate_difference()
    _wait_for_presented_difference(window, qtbot)
    y_key = panel._cache_key()
    assert y_key is not None

    panel.channel.setCurrentText("U")
    panel.calculate_difference()
    presented_u = _wait_for_presented_difference(window, qtbot)
    u_key = panel._cache_key()
    assert u_key is not None and u_key != y_key
    assert presented_u.source is not None
    np.testing.assert_array_equal(presented_u.source, np.full((2, 2), 7, dtype=np.uint8))

    _mark_difference_visible(window)
    panel.channel.setCurrentText("Y")
    assert window._difference_document is None
    presented_y = _wait_for_presented_difference(window, qtbot)
    assert window.diff_action.isChecked()
    assert window.__dict__["_difference_result_key"] == y_key
    assert presented_y.source is not None
    np.testing.assert_array_equal(presented_y.source, np.full((4, 4), 3, dtype=np.uint8))

    panel.channel.setCurrentText("U")
    assert window._difference_document is None
    presented_u_again = _wait_for_presented_difference(window, qtbot)
    assert window.diff_action.isChecked()
    assert window.__dict__["_difference_result_key"] == u_key
    assert presented_u_again.source is not None
    np.testing.assert_array_equal(
        presented_u_again.source,
        np.full((2, 2), 7, dtype=np.uint8),
    )

    window.close()
