from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import QApplication

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.ui.quick_compare import QuickCompareController

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _window(qtbot: object) -> tuple[MainWindow, QuickCompareController]:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    controller = window.quick_compare_controller
    assert isinstance(controller, QuickCompareController)
    return window, controller


def _mime_for(path: Path) -> QMimeData:
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path))])
    return mime


def test_empty_workspace_children_are_native_drop_surfaces(qtbot: object) -> None:
    window, _controller = _window(qtbot)
    empty = window.empty_workspace

    assert window.central_stack.currentWidget() is empty
    assert empty.acceptDrops()
    for child in (
        empty.title,
        empty.open_images_button,
        empty.open_folders_button,
        empty.formats_hint,
        empty.shortcuts_hint,
        empty.gestures_hint,
    ):
        assert child.acceptDrops()
    window.close()


def test_empty_workspace_delivers_full_drag_lifecycle_through_application_filter(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, controller = _window(qtbot)
    path = tmp_path / "sample.png"
    path.write_bytes(b"placeholder")
    mime = _mime_for(path)
    target = window.empty_workspace.title
    received: list[list[Path]] = []

    def handle(paths: list[Path]) -> bool:
        received.append(paths)
        return True

    monkeypatch.setattr(controller, "handle_image_drop", handle)

    enter = QDragEnterEvent(
        QPoint(1, 1),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(target, enter)
    assert enter.isAccepted()

    move = QDragMoveEvent(
        QPoint(2, 2),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(target, move)
    assert move.isAccepted()

    drop = QDropEvent(
        QPointF(3.0, 3.0),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(target, drop)
    assert drop.isAccepted()
    assert received == [[path]]
    window.close()
