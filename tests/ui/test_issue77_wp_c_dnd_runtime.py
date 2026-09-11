from __future__ import annotations

from pathlib import Path
from threading import Event, get_ident

import numpy as np
import pytest
from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import QApplication, QWidget

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.display_transform import render_ordinary_display_preview
from pixelscope.core.image_document import ImageDocument
from pixelscope.ui.display_gain import display_gain_state
from pixelscope.ui.presentation_drop import PresentationDropHost
from pixelscope.ui.quick_compare import QuickCompareController

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _window(qtbot: object) -> tuple[MainWindow, QuickCompareController]:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    controller = window.quick_compare_controller
    assert isinstance(controller, QuickCompareController)
    return window, controller


def _document(name: str, value: int, tmp_path: Path) -> ImageDocument:
    return ImageDocument.from_array(
        np.full((6, 8), value, dtype=np.uint8),
        name,
        source_path=tmp_path / name,
    )


def _add(window: MainWindow, documents: list[ImageDocument]) -> None:
    for document in documents:
        window.add_document(document, select=False)


def _mime_for(path: Path) -> QMimeData:
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path))])
    return mime


def _send_drag_lifecycle(target: QWidget, mime: QMimeData) -> tuple[bool, bool, bool]:
    enter = QDragEnterEvent(
        QPoint(1, 1),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(target, enter)

    move = QDragMoveEvent(
        QPoint(2, 2),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(target, move)

    drop = QDropEvent(
        QPointF(3.0, 3.0),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(target, drop)
    return enter.isAccepted(), move.isAccepted(), drop.isAccepted()


def test_presentation_host_is_single_drop_owner_for_empty_single_and_multi_states(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, _controller = _window(qtbot)
    host = window.presentation_drop_host
    assert isinstance(host, PresentationDropHost)
    assert host.content is window.central_stack
    assert host.acceptDrops()
    assert not window.central_stack.acceptDrops()

    path = tmp_path / "sample.png"
    path.write_bytes(b"placeholder")
    mime = _mime_for(path)
    received: list[list[Path]] = []
    host.paths_dropped.connect(received.append)

    for presentation in (
        window.empty_workspace,
        window.viewer,
        window.multi_compare_view,
    ):
        window.central_stack.setCurrentWidget(presentation)
        assert _send_drag_lifecycle(host, mime) == (True, True, True)

    assert received == [[path], [path], [path]]
    window.close()


def test_nested_presentation_widgets_are_not_competing_native_drop_targets(qtbot: object) -> None:
    window, _controller = _window(qtbot)
    host = window.presentation_drop_host
    assert isinstance(host, PresentationDropHost)

    assert not window.central_stack.acceptDrops()
    assert all(not child.acceptDrops() for child in window.central_stack.findChildren(QWidget))
    assert not host.isAncestorOf(window.document_list)
    assert window.document_list.acceptDrops()
    window.close()


def test_presentation_host_ignores_non_local_mime(qtbot: object) -> None:
    window, _controller = _window(qtbot)
    host = window.presentation_drop_host
    assert isinstance(host, PresentationDropHost)
    mime = QMimeData()
    mime.setText("not a local file")

    enter = QDragEnterEvent(
        QPoint(1, 1),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(host, enter)
    assert not enter.isAccepted()
    window.close()


def test_single_view_blink_gain_render_is_async_and_cached(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, controller = _window(qtbot)
    first = _document("a.png", 10, tmp_path)
    second = _document("b.png", 100, tmp_path)
    _add(window, [first, second])
    window._select_document_ids([first.document_id, second.document_id])
    window.set_layout_mode("Single View")
    window.show_selected_image(1)
    window.show()
    qtbot.wait(20)  # type: ignore[attr-defined]

    state = display_gain_state()
    state.set_gain(2.0)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.viewer._displayed_gain == 2.0
        and window.viewer._display_preview_worker is None,
        timeout=5000,
    )

    assert first.source is not None
    assert first.preview is not None
    expected_alternate = render_ordinary_display_preview(
        first.source,
        channel_layout=first.channel_layout,
        transform=first.display_transform,
        canonical_preview=first.preview,
        gain=2.0,
    )
    reference_image = np.array(window.viewer.image_item.image, copy=True)
    worker_started = Event()
    worker_release = Event()
    worker_threads: list[int] = []
    call_count = 0
    main_thread = get_ident()

    def delayed_render(*args: object, **kwargs: object) -> np.ndarray:
        nonlocal call_count
        call_count += 1
        worker_threads.append(get_ident())
        worker_started.set()
        assert worker_release.wait(timeout=5.0)
        return render_ordinary_display_preview(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        "pixelscope.ui.quick_compare.render_ordinary_display_preview",
        delayed_render,
    )
    controller._clear_blink_cache()

    assert controller._begin_blink()
    qtbot.waitUntil(worker_started.is_set, timeout=3000)  # type: ignore[attr-defined]
    assert len(worker_threads) == 1
    assert worker_threads[0] != main_thread
    assert np.array_equal(window.viewer.image_item.image, reference_image)

    worker_release.set()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: controller._blink_cache_preview is not None
        and np.array_equal(window.viewer.image_item.image, expected_alternate),
        timeout=5000,
    )
    assert call_count == 1

    controller._end_blink()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.viewer._displayed_gain == 2.0
        and window.viewer._display_preview_worker is None,
        timeout=5000,
    )

    assert controller._begin_blink()
    assert np.array_equal(window.viewer.image_item.image, expected_alternate)
    assert call_count == 1
    controller._end_blink()

    state.reset()
    window.close()
