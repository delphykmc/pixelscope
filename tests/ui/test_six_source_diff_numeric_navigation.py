from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QSettings

from pixelscope.app import main_window as main_window_module
from pixelscope.app.main_window import MainWindow
from pixelscope.app.settings import QSettingsAdapter, SettingsRepository
from pixelscope.core.image_document import ImageDocument


def _repository(path: Path) -> SettingsRepository:
    settings = QSettings(str(path), QSettings.Format.IniFormat)
    settings.clear()
    return SettingsRepository(QSettingsAdapter(settings))


def _ready_documents(tmp_path: Path) -> list[ImageDocument]:
    return [
        ImageDocument.from_array(
            np.full((4, 4), index + 1, dtype=np.uint8),
            f"image{index + 1}.png",
            source_path=tmp_path / f"image{index + 1}.png",
        )
        for index in range(6)
    ]


def test_six_source_diff_number_keys_show_matching_source_and_keep_diff_available(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ui_settings = QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat)
    ui_settings.clear()
    monkeypatch.setattr(main_window_module, "QSettings", lambda: ui_settings)

    window = MainWindow(settings_repository=_repository(tmp_path / "app.ini"))
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = _ready_documents(tmp_path)
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])

    numerical = np.zeros((4, 4), dtype=np.uint8)
    preview = np.zeros((4, 4, 3), dtype=np.uint8)
    cached_display = ("Difference", numerical, preview)
    monkeypatch.setattr(
        window.difference_panel,
        "selected_documents",
        lambda: (documents[0], documents[1]),
    )
    monkeypatch.setattr(
        window.difference_panel,
        "cached_display_for_current",
        lambda: cached_display,
    )

    window._store_difference_document(*cached_display, switch_to_result=True)
    window.diff_action.blockSignals(True)
    window.diff_action.setChecked(True)
    window.diff_action.blockSignals(False)
    window._set_single_navigation("difference")

    difference = window._difference_document
    assert difference is not None
    assert window.viewer.document is difference
    assert window._view_capacity == 1
    assert window.diff_action.isChecked()

    logical_ids = tuple(document.document_id for document in window.selected_documents)
    assert logical_ids == tuple(document.document_id for document in documents)

    for local_index, document in enumerate(documents):
        window.show_selected_image(local_index)

        assert window.viewer.document is document
        assert window.viewer._slot == local_index + 1
        assert window._current_index == local_index
        assert window._active_document_id == document.document_id
        assert window.diff_action.isChecked()
        assert tuple(item.document_id for item in window.selected_documents) == logical_ids
        for candidate in documents:
            item = window.document_list.document_item(candidate.document_id)
            assert item is not None
            assert bool(item.data(0, window.document_list.ACTIVE_ROLE)) is (
                candidate is document
            )

    window._navigate_single_view("difference")
    assert window.viewer.document is difference
    assert window._active_document_id == difference.document_id
    assert window.diff_action.isChecked()
    assert tuple(document.document_id for document in window.selected_documents) == logical_ids
    window.close()
