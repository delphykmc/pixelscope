from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QSettings, Qt

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument


def _window(
    qtbot: object,
    tmp_path: Path,
) -> tuple[MainWindow, list[ImageDocument]]:
    QSettings().clear()
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    documents = [
        ImageDocument.from_array(
            np.full((4, 4), index * 10, dtype=np.uint8),
            f"image{index + 1:02d}.png",
            source_path=tmp_path / f"image{index + 1:02d}.png",
        )
        for index in range(4)
    ]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    return window, documents


def _pick(qtbot: object, window: MainWindow, document: ImageDocument) -> None:
    viewer = next(
        viewer
        for viewer in window.multi_compare_view.occupied_viewers
        if viewer.presented_document is document
    )
    qtbot.mouseClick(  # type: ignore[attr-defined]
        viewer.header.pick,
        Qt.MouseButton.LeftButton,
    )


def test_keep_requires_explicit_calculate_to_establish_next_active_difference(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, documents = _window(qtbot, tmp_path)
    controller = window.review_selection_controller

    assert not window.diff_action.isEnabled()
    window.difference_panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_document is not None,
        timeout=5000,
    )
    assert window.diff_action.isEnabled()
    assert window.diff_action.isChecked()

    _pick(qtbot, window, documents[0])
    _pick(qtbot, window, documents[1])
    assert controller.keep_picked()

    assert window._difference_document is None
    assert window._difference_source_ids is None
    assert not window.diff_action.isChecked()
    assert not window.diff_action.isEnabled()

    window.difference_panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_document is not None,
        timeout=5000,
    )
    assert window._difference_source_ids == (
        documents[0].document_id,
        documents[1].document_id,
    )
    assert window.diff_action.isEnabled()
    assert window.diff_action.isChecked()
    window.close()
