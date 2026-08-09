from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QFileDialog

from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineSelection
from pixelscope.core.roi import RoiBounds


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path: Path) -> None:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str(tmp_path),
    )
    settings = QSettings()
    settings.clear()
    settings.sync()


@pytest.mark.parametrize("image_count", [6, 8])
def test_open_images_keeps_all_selected_files_and_pages_presentation(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    image_count: int,
) -> None:
    paths = [tmp_path / f"direct-{index:02d}.png" for index in range(image_count)]
    for path in paths:
        path.write_bytes(b"fixture")
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileNames",
        lambda *_args, **_kwargs: ([str(path) for path in paths], ""),
    )

    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    monkeypatch.setattr(window, "_ensure_loaded", lambda _document: None)
    monkeypatch.setattr(window, "_refresh_preload_plan", lambda: None)

    window.open_images()

    assert len(window.documents) == image_count
    assert [document.source_path for document in window.selected_documents] == [
        path.resolve() for path in paths
    ]
    assert window._view_capacity == 6
    assert [
        viewer.document.source_path
        for viewer in window.multi_compare_view.occupied_viewers
        if viewer.document is not None
    ] == [path.resolve() for path in paths[:6]]

    if image_count > 6:
        window.next_image()
        assert window._page_start == 6
        assert [
            viewer.document.source_path
            for viewer in window.multi_compare_view.occupied_viewers
            if viewer.document is not None
        ] == [path.resolve() for path in paths[6:]]

    window.close()


def test_open_folders_cancel_is_a_complete_noop(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current = ImageDocument.from_array(
        np.arange(16, dtype=np.uint8).reshape(4, 4),
        "current.png",
        source_path=tmp_path / "current.png",
    )
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.add_document(current)
    window._shared_roi = RoiBounds(0, 0, 2, 2)
    window._shared_line = LineSelection(0, 0, 3, 3)

    selected_before = tuple(document.document_id for document in window.selected_documents)
    central_before = window.central_stack.currentWidget()
    layout_before = window._layout_mode
    active_before = window._active_document_id
    roi_before = window._shared_roi
    line_before = window._shared_line
    monkeypatch.setattr(
        "pixelscope.app.main_window.choose_directories",
        lambda *_args, **_kwargs: (),
    )

    window.open_folders()

    assert len(window.documents) == 1
    assert tuple(document.document_id for document in window.selected_documents) == selected_before
    assert window.central_stack.currentWidget() is central_before
    assert window._layout_mode == layout_before
    assert window._active_document_id == active_before
    assert window._shared_roi == roi_before
    assert window._shared_line == line_before
    window.close()
