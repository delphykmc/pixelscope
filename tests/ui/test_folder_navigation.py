from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QItemSelectionModel, QSettings, Qt

from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path: Path) -> None:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    QSettings().clear()


def _add_folder_documents(
    window: MainWindow,
    folder: Path,
    count: int = 3,
) -> list[ImageDocument]:
    documents = [
        ImageDocument.from_array(
            np.full((2, 2), index, dtype=np.uint8),
            f"image{index + 1}.png",
            source_path=folder / f"image{index + 1}.png",
        )
        for index in range(count)
    ]
    for document in documents:
        window.add_document(document, select=False)
    return documents


def test_single_folder_navigation_and_prediction_share_one_plan(
    qtbot: object, tmp_path: Path
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = _add_folder_documents(window, tmp_path / "single")
    window._select_document_ids([documents[1].document_id])

    next_plan = window._plan_folder_navigation(1)
    assert next_plan is not None
    assert next_plan.document_ids == (documents[2].document_id,)
    window.next_folder_position()
    assert tuple(document.document_id for document in window.selected_documents) == (
        documents[2].document_id,
    )

    window.previous_folder_position()
    assert [document.document_id for document in window.selected_documents] == [
        documents[1].document_id
    ]


@pytest.mark.parametrize("folder_count", (2, 3, 4, 5, 6))
def test_two_to_six_folders_move_atomically_to_the_predicted_ids(
    qtbot: object,
    tmp_path: Path,
    folder_count: int,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    by_folder = [
        _add_folder_documents(window, tmp_path / f"folder-{index}", count=2)
        for index in range(folder_count)
    ]
    window._select_document_ids([documents[0].document_id for documents in by_folder])

    plan = window._plan_folder_navigation(1)
    assert plan is not None
    window.next_folder_position()

    actual_ids = tuple(document.document_id for document in window.selected_documents)
    assert actual_ids == plan.document_ids
    assert actual_ids == tuple(documents[1].document_id for documents in by_folder)


def test_one_folder_endpoint_keeps_the_whole_group_unchanged(qtbot: object, tmp_path: Path) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    first = _add_folder_documents(window, tmp_path / "first", count=2)
    second = _add_folder_documents(window, tmp_path / "second", count=3)
    selected_ids = [first[1].document_id, second[1].document_id]
    window._select_document_ids(selected_ids)

    assert window._plan_folder_navigation(1) is None
    window.next_folder_position()

    assert [document.document_id for document in window.selected_documents] == selected_ids
    assert "selection was not changed" in window.statusBar().currentMessage()


def test_duplicate_folder_programmatic_and_over_six_groups_are_invalid(
    qtbot: object, tmp_path: Path
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    same_folder = _add_folder_documents(window, tmp_path / "same", count=2)
    window._select_document_ids([document.document_id for document in same_folder])
    assert window._plan_folder_navigation(1) is None

    generated = ImageDocument.from_array(np.zeros((2, 2), dtype=np.uint8), "generated")
    window.add_document(generated, select=False)
    window._select_document_ids([generated.document_id])
    assert window._plan_folder_navigation(1) is None

    seven = [
        _add_folder_documents(window, tmp_path / f"many-{index}", count=2)[0] for index in range(7)
    ]
    window._select_document_ids([document.document_id for document in seven])
    assert window._plan_folder_navigation(1) is None


def test_files_up_down_keep_native_tree_row_navigation(qtbot: object, tmp_path: Path) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = _add_folder_documents(window, tmp_path / "rows", count=3)
    first_item = window.document_list.document_item(documents[0].document_id)
    second_item = window.document_list.document_item(documents[1].document_id)
    assert first_item is not None
    assert second_item is not None
    window.document_list.setCurrentItem(
        first_item,
        0,
        QItemSelectionModel.SelectionFlag.ClearAndSelect,
    )
    window.show()
    window.document_list.setFocus()

    qtbot.keyClick(window.document_list, Qt.Key.Key_Down)  # type: ignore[attr-defined]
    assert window.document_list.currentItem() is second_item
    qtbot.keyClick(window.document_list, Qt.Key.Key_Up)  # type: ignore[attr-defined]
    assert window.document_list.currentItem() is first_item
