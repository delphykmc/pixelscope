from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QLineEdit

from pixelscope.app.bootstrap import compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.ui.image_viewer import ImageViewer

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _window(qtbot: object, count: int) -> tuple[MainWindow, list[ImageDocument]]:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    compose_main_window_presentation(window)
    documents = [
        ImageDocument.from_array(
            np.full((240, 320), index + 1, dtype=np.uint8), f"cycle-{index}.png"
        )
        for index in range(count)
    ]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    window.show()
    qtbot.wait(20)  # type: ignore[attr-defined]
    return window, documents


def _visible_source_ids(window: MainWindow) -> list[str]:
    return [
        viewer.document.document_id
        for viewer in window.multi_compare_view.occupied_viewers
        if viewer.document is not None and viewer.document.channel_layout != "DIFFERENCE"
    ]


@pytest.mark.parametrize("count", (2, 3, 4, 5, 6))
def test_t_rotates_last_source_to_primary_without_image_upload(
    qtbot: object, monkeypatch: pytest.MonkeyPatch, count: int
) -> None:
    window, documents = _window(qtbot, count)
    selected_ids = [document.document_id for document in documents]
    window.set_layout_mode("Multi View")
    before_order = _visible_source_ids(window)
    before_range = window.multi_compare_view.capture_view_state()
    uploads: list[str] = []
    original_upload = ImageViewer._upload_preview

    def recording_upload(self: ImageViewer, preview: object, document: ImageDocument) -> None:
        uploads.append(document.document_id)
        original_upload(self, preview, document)

    monkeypatch.setattr(ImageViewer, "_upload_preview", recording_upload)
    for _ in range(count):
        expected = [before_order[-1], *before_order[:-1]]
        window.cycle_primary_source()
        assert _visible_source_ids(window) == expected
        assert window._focus_document_id == expected[0]
        assert [document.document_id for document in window.selected_documents] == selected_ids
        assert np.allclose(
            window.multi_compare_view.capture_view_state().ranges,
            before_range.ranges,
            rtol=0.05,
        )
        before_order = expected
    assert uploads == []
    assert before_order == selected_ids
    window.close()


def test_t_rotates_in_single_view_without_displaying_diff(
    qtbot: object,
) -> None:
    window, documents = _window(qtbot, 3)
    window.set_layout_mode("Single View")
    expected = [documents[2], documents[1], documents[0], documents[2]]
    for source in expected:
        window.cycle_primary_source()
        assert window.viewer.document is source
        assert window._focus_document_id == source.document_id
    window.close()


def test_t_uses_only_current_page_and_skips_derived_order_entries(qtbot: object) -> None:
    window, documents = _window(qtbot, 7)
    window.set_layout_mode("Multi View")
    # A leftover derived/display-only ID must never become a source target.
    window._multi_display_order.append("generated-difference")
    window.cycle_primary_source()
    assert window._focus_document_id == documents[5].document_id
    assert window._page_start == 0
    assert documents[6].document_id not in _visible_source_ids(window)
    window.close()


@pytest.mark.parametrize("scope", ["viewer", "document_list"])
def test_t_shortcut_is_scoped_to_viewer_and_files(qtbot: object, scope: str) -> None:
    window, documents = _window(qtbot, 2)
    window.activateWindow()
    window.set_layout_mode("Single View")
    target = getattr(window, scope)
    target.setFocus()
    qtbot.keyClick(target, Qt.Key.Key_T)  # type: ignore[attr-defined]
    assert window.viewer.document is documents[1]
    window.close()


def test_t_leaves_editor_and_modified_key_input_alone(qtbot: object) -> None:
    window, documents = _window(qtbot, 2)
    window.set_layout_mode("Single View")
    editor = QLineEdit(window)
    editor.show()
    window.activateWindow()
    editor.setFocus()
    qtbot.keyClicks(editor, "t")  # type: ignore[attr-defined]
    assert editor.text() == "t"
    assert window.viewer.document is documents[0]
    window.viewer.setFocus()
    qtbot.keyClick(  # type: ignore[attr-defined]
        window.viewer, Qt.Key.Key_T, Qt.KeyboardModifier.ControlModifier
    )
    assert window.viewer.document is documents[0]
    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_T, Qt.KeyboardModifier.NoModifier, "t", True)
    QApplication.sendEvent(window.viewer, event)
    assert window.viewer.document is documents[0]
    window.close()


def test_cycle_does_nothing_for_one_source_or_split_channels(qtbot: object) -> None:
    window, documents = _window(qtbot, 1)
    window.cycle_primary_source()
    assert window.viewer.document is documents[0]
    window.close()

    window, documents = _window(qtbot, 2)
    window._channel_split_active = True
    before = list(window._multi_display_order)
    window.cycle_primary_source()
    assert window._multi_display_order == before
    window.close()


def test_b_no_longer_overlays_source_images(qtbot: object) -> None:
    window, _documents = _window(qtbot, 2)
    viewer = window.multi_compare_view.occupied_viewers[0]
    before_document = viewer.document
    before_image = np.array(viewer.image_item.image, copy=True)
    window.activateWindow()
    viewer.setFocus()
    qtbot.keyClick(viewer, Qt.Key.Key_B)  # type: ignore[attr-defined]
    assert viewer.document is before_document
    assert np.array_equal(viewer.image_item.image, before_image)
    assert not hasattr(window.quick_compare_controller, "_blink_snapshot")
    window.close()
