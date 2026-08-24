from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLineEdit

from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument

pytestmark = pytest.mark.usefixtures("isolated_synced_qsettings")


def _ready_documents(tmp_path: Path, count: int) -> list[ImageDocument]:
    return [
        ImageDocument.from_array(
            np.full((8, 10, 3), index, dtype=np.uint8),
            f"review-{index + 1:02d}.png",
            source_path=tmp_path / f"folder-{index:02d}" / f"review-{index + 1:02d}.png",
        )
        for index in range(count)
    ]


def _select_documents(window: MainWindow, documents: list[ImageDocument]) -> None:
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])


def test_comparison_page_shortcuts_follow_availability_and_preserve_native_ctrl_arrow(
    qtbot: object,
    tmp_path: Path,
) -> None:
    documents = _ready_documents(tmp_path, 15)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _select_documents(window, documents)

    editor = QLineEdit(window)
    editor.setText("alpha beta")
    editor.show()
    window.show()

    previous_shortcut, next_shortcut = window._comparison_page_shortcuts
    assert not previous_shortcut.isEnabled()
    assert next_shortcut.isEnabled()

    next_shortcut.activated.emit()
    assert window._page_start == 6
    assert previous_shortcut.isEnabled()
    assert next_shortcut.isEnabled()

    next_shortcut.activated.emit()
    assert window._page_start == 12
    assert previous_shortcut.isEnabled()
    assert not next_shortcut.isEnabled()

    editor.setText("alpha beta")
    editor.setCursorPosition(0)
    editor.setFocus()
    qtbot.waitUntil(editor.hasFocus)  # type: ignore[attr-defined]
    QTest.keyClick(
        editor,
        Qt.Key.Key_Right,
        Qt.KeyboardModifier.ControlModifier,
    )
    assert window._page_start == 12
    assert editor.cursorPosition() > 0
    window.close()


def test_six_source_cached_difference_reentry_matches_async_diff_only_presentation(
    qtbot: object,
    tmp_path: Path,
) -> None:
    documents = _ready_documents(tmp_path, 12)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _select_documents(window, documents)

    window.difference_panel.calculate_difference()
    first_pair = {documents[0].document_id, documents[1].document_id}
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_source_ids is not None
        and set(window._difference_source_ids) == first_pair
        and window._difference_document is not None
        and window.viewer.document is window._difference_document,
        timeout=3000,
    )
    assert window.central_stack.currentWidget() is window.viewer
    assert window._layout_mode == "Single View"
    assert window._six_image_diff_restore_state is not None

    window.next_comparison_page()
    second_pair = {documents[6].document_id, documents[7].document_id}
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_source_ids is not None
        and set(window._difference_source_ids) == second_pair
        and window._difference_document is not None
        and window.viewer.document is window._difference_document,
        timeout=3000,
    )

    window.previous_comparison_page()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_source_ids is not None
        and set(window._difference_source_ids) == first_pair
        and window._difference_document is not None
        and window.viewer.document is window._difference_document,
        timeout=3000,
    )
    assert window.central_stack.currentWidget() is window.viewer
    assert window._layout_mode == "Single View"
    assert window._view_capacity == 1
    assert window._six_image_diff_restore_state is not None

    window.diff_action.setChecked(False)
    assert window._six_image_diff_restore_state is None
    assert window.current_comparison_documents() == documents[:6]
    assert window.central_stack.currentWidget() is window.multi_compare_view
    window.close()


def test_comparison_page_navigation_does_not_create_folder_position_preload_plan(
    qtbot: object,
    tmp_path: Path,
) -> None:
    documents = _ready_documents(tmp_path, 12)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _select_documents(window, documents)

    assert window.preload_controller.current_plan is None
    assert not window._preload_workers

    window.next_comparison_page()

    assert window.current_comparison_documents() == documents[6:12]
    assert window.preload_controller.current_plan is None
    assert not window._preload_workers
    window.close()
