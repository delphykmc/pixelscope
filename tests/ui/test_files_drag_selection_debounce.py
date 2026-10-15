from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QWidget

from pixelscope.app.bootstrap import compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def test_files_drag_intermediate_selection_does_not_rebuild_viewers(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    compose_main_window_presentation(window)
    docs = [
        ImageDocument.from_array(
            np.full((8, 8), index, dtype=np.uint8),
            f"drag-{index}.png",
            source_path=tmp_path / f"drag-{index}.png",
        )
        for index in range(3)
    ]
    for document in docs:
        window.add_document(document, select=False)

    first = window.document_list.document_item(docs[0].document_id)
    second = window.document_list.document_item(docs[1].document_id)
    third = window.document_list.document_item(docs[2].document_id)
    assert first is not None and second is not None and third is not None

    rendered: list[str] = []
    original = window._render_selection

    def traced_render(*args: object, **kwargs: object) -> None:
        rendered.append("render")
        original(*args, **kwargs)

    monkeypatch.setattr(window, "_render_selection", traced_render)

    # Ordinary click/programmatic selection remains synchronous.
    first.setSelected(True)
    assert rendered == ["render"]
    assert [document.document_id for document in window.selected_documents] == [docs[0].document_id]
    rendered.clear()

    # QTreeWidget emits once for every intermediate mouse-drag selection.
    # Only the final selection is permitted to rebuild 4K presentation/analysis.
    window.document_list._selection_mouse_dragging = True
    second.setSelected(True)
    third.setSelected(True)
    second.setSelected(False)
    assert rendered == []
    assert window._files_drag_selection_dirty

    window.document_list._selection_mouse_dragging = False
    window.document_list.selection_drag_finished.emit()
    assert rendered == ["render"]
    assert not window._files_drag_selection_dirty
    assert [document.document_id for document in window.selected_documents] == [
        docs[0].document_id,
        docs[2].document_id,
    ]

    # Selection change after release is again immediate.
    first.setSelected(False)
    assert len(rendered) == 2
    assert [document.document_id for document in window.selected_documents] == [docs[2].document_id]
    window.close()


def _mouse_event(
    viewport: QWidget,
    event_type: QEvent.Type,
    x: float,
    y: float,
    button: Qt.MouseButton,
    buttons: Qt.MouseButton,
) -> None:
    local = QPointF(x, y)
    global_point = QPointF(viewport.mapToGlobal(local.toPoint()))
    event = QMouseEvent(
        event_type,
        local,
        global_point,
        button,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(viewport, event)


def test_real_mouse_drag_pause_does_not_commit_and_review_syncs_only_on_release(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    compose_main_window_presentation(window)
    docs = [
        ImageDocument.from_array(
            np.full((8, 8), index, dtype=np.uint8),
            f"mouse-{index}.png",
            source_path=tmp_path / f"mouse-{index}.png",
        )
        for index in range(4)
    ]
    for document in docs:
        window.add_document(document, select=False)
    window.show()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.document_list.viewport().isVisible(), timeout=5000
    )
    tree = window.document_list
    viewport = tree.viewport()
    items = [tree.document_item(document.document_id) for document in docs]
    assert all(item is not None for item in items)
    first, second, third, fourth = items
    assert first is not None and second is not None and third is not None
    assert fourth is not None
    tree.scrollToItem(first)
    first_rect = tree.visualItemRect(first)
    third_rect = tree.visualItemRect(third)
    assert first_rect.isValid() and third_rect.isValid()
    first_pos = first_rect.center()
    third_pos = third_rect.center()

    # Establish a real initial click, which must still commit immediately.
    _mouse_event(
        viewport, QEvent.Type.MouseButtonPress,
        first_pos.x(), first_pos.y(),
        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
    )
    _mouse_event(
        viewport, QEvent.Type.MouseButtonRelease,
        first_pos.x(), first_pos.y(),
        Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton,
    )

    controller = window.review_selection_controller
    commits: list[int] = []
    review_syncs: list[int] = []
    orig_render = window._render_selection
    orig_sync = controller._sync_all

    def counted_render(*args: object, **kwargs: object) -> None:
        commits.append(1)
        orig_render(*args, **kwargs)

    def counted_review_sync() -> None:
        review_syncs.append(1)
        orig_sync()

    monkeypatch.setattr(window, "_render_selection", counted_render)
    monkeypatch.setattr(controller, "_sync_all", counted_review_sync)

    # A real held-button QMouseEvent, rather than directly setting the private
    # state flag, starts the drag. Intermediate edits produce Qt selection signals.
    _mouse_event(
        viewport, QEvent.Type.MouseButtonPress,
        first_pos.x(), first_pos.y(),
        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
    )
    _mouse_event(
        viewport, QEvent.Type.MouseMove,
        third_pos.x(), third_pos.y(),
        Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton,
    )
    assert tree.selection_mouse_dragging
    second.setSelected(True)
    assert window._files_drag_selection_dirty
    assert commits == []
    assert review_syncs == []

    # The 200ms idle fallback must not render while a held drag is paused.
    qtbot.wait(260)  # type: ignore[attr-defined]
    assert tree.selection_mouse_dragging
    assert commits == []
    assert review_syncs == []
    _mouse_event(
        viewport, QEvent.Type.MouseMove,
        first_pos.x(), first_pos.y(),
        Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton,
    )
    fourth.setSelected(True)
    third.setSelected(False)
    assert commits == []
    assert review_syncs == []

    _mouse_event(
        viewport, QEvent.Type.MouseButtonRelease,
        first_pos.x(), first_pos.y(),
        Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton,
    )
    assert not tree.selection_mouse_dragging
    assert not window._files_drag_selection_dirty
    assert commits == [1]
    assert review_syncs == [1]
    selected_from_tree = {
        str(item.data(0, Qt.ItemDataRole.UserRole))
        for item in tree.selected_document_items()
    }
    assert {item.document_id for item in window.selected_documents} == selected_from_tree

    # Post-release single selection edits still take the immediate path.
    fourth.setSelected(not fourth.isSelected())
    assert commits == [1, 1]
    assert review_syncs == [1, 1]
    window.close()
