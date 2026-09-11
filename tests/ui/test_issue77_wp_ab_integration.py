from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.roi import RoiBounds

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _window(qtbot: object) -> MainWindow:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    return window


def _add_folder(
    window: MainWindow,
    folder: Path,
    *,
    shape: tuple[int, int],
    count: int = 3,
) -> list[ImageDocument]:
    documents = [
        ImageDocument.from_array(
            np.full(shape, index, dtype=np.uint8),
            f"frame-{index}.png",
            source_path=folder / f"frame-{index}.png",
        )
        for index in range(count)
    ]
    for document in documents:
        window.add_document(document, select=False)
    return documents


def _selected_ids(window: MainWindow) -> list[str]:
    return [document.document_id for document in window.selected_documents]


def test_same_position_bootstrap_preserves_roi_when_target_contains_it(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window = _window(qtbot)
    first = _add_folder(window, tmp_path / "first", shape=(6, 8))
    second = _add_folder(window, tmp_path / "second", shape=(6, 8))
    window._select_document_ids([first[1].document_id])

    roi = RoiBounds(2, 1, 4, 3)
    assert window._shared_roi_changed(roi)

    window.add_next_folder_at_same_position()

    assert _selected_ids(window) == [first[1].document_id, second[1].document_id]
    assert window._shared_roi == roi
    assert all(
        viewer.current_roi_bounds() == roi for viewer in window.multi_compare_view.occupied_viewers
    )
    window.close()


def test_same_position_bootstrap_clears_roi_when_target_cannot_contain_it(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window = _window(qtbot)
    first = _add_folder(window, tmp_path / "first", shape=(6, 8))
    second = _add_folder(window, tmp_path / "second", shape=(4, 5))
    window._select_document_ids([first[1].document_id])

    roi = RoiBounds(4, 2, 4, 4)
    assert window._shared_roi_changed(roi)

    window.add_next_folder_at_same_position()

    assert _selected_ids(window) == [first[1].document_id, second[1].document_id]
    assert window._shared_roi is None
    assert window.comparison_analysis_panel.region_scope.currentText() == "Full image"
    assert all(
        viewer.current_roi_bounds() is None
        for viewer in window.multi_compare_view.occupied_viewers
    )
    window.close()
