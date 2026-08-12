from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QSettings, Qt

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument


def _production_window(qtbot: object) -> MainWindow:
    QSettings().clear()
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    return window


def _ready_document(path: Path, value: int) -> ImageDocument:
    return ImageDocument.from_array(
        np.full((16, 16), value, dtype=np.uint8),
        path.name,
        source_path=path,
    )


def test_deselecting_difference_member_invalidates_diff_without_recalculation(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = _production_window(qtbot)
    documents = [
        _ready_document(tmp_path / f"image-{index}.png", 20 + index)
        for index in range(4)
    ]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])

    a, b = documents[:2]
    window.difference_panel.set_documents(documents, (a.document_id, b.document_id))
    difference = ImageDocument.from_array(
        np.zeros((16, 16), dtype=np.uint8),
        "Difference",
        channel_layout="DIFFERENCE",
    )
    window._difference_document = difference
    window._difference_source_ids = (a.document_id, b.document_id)
    window.diff_action.blockSignals(True)
    window.diff_action.setChecked(True)
    window.diff_action.blockSignals(False)
    window._render_selection(preserve_view=True)

    calculations: list[object] = []
    monkeypatch.setattr(
        window.difference_panel,
        "calculate_difference",
        lambda: calculations.append(object()),
    )

    item = next(
        item
        for item in window.document_list.document_items()
        if str(item.data(0, Qt.ItemDataRole.UserRole)) == a.document_id
    )
    item.setSelected(False)

    assert len(window.selected_documents) == 3
    assert window._difference_document is None
    assert window._difference_source_ids is None
    assert not window.diff_action.isChecked()
    assert calculations == []
    assert len(window.multi_compare_view.occupied_viewers) == 3
    window.close()


def test_restore_feedback_timer_tolerates_parent_window_destruction(
    qtbot: object,
) -> None:
    window = _production_window(qtbot)
    controller = window.session_controller

    controller._begin_restore_feedback()
    dialog = controller._restore_dialog
    assert dialog is not None
    assert dialog.windowModality() == Qt.WindowModality.ApplicationModal

    controller._finish_restore_feedback(delay_ms=250)
    window.close()
    dialog.deleteLater()
    qtbot.wait(350)  # type: ignore[attr-defined]

    assert controller._restore_dialog is None
