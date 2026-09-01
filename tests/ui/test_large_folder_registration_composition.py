from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import cv2
import numpy as np
import pytest
from PySide6.QtWidgets import QFileDialog

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.app.registration_controller import RegistrationController
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.recent_entries import RecentEntryKind

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _history_count(entries: Sequence[Path], target: Path) -> int:
    identity = str(target.resolve()).casefold()
    return sum(str(entry.resolve()).casefold() == identity for entry in entries)


def test_production_composition_preserves_recent_tags_and_folder_only_selection(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    open_folder = tmp_path / "open-folder"
    drop_folder = tmp_path / "drop-folder"
    open_folder.mkdir()
    drop_folder.mkdir()
    for index in range(2):
        (open_folder / f"open{index}.png").write_bytes(b"registered-only")
        (drop_folder / f"drop{index}.png").write_bytes(b"registered-only")
    direct = tmp_path / "direct.png"
    assert cv2.imwrite(str(direct), np.full((8, 8), 17, dtype=np.uint8))

    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    controller = window.large_folder_registration_controller
    assert isinstance(controller, RegistrationController)
    controller.chunk_size = 1

    seed = ImageDocument.from_array(np.zeros((6, 6), dtype=np.uint8), "seed")
    window.add_document(seed, select=True)
    selected_before = [document.document_id for document in window.selected_documents]
    page_before = [document.document_id for document in window.current_comparison_documents()]
    presented_before = window.central_stack.currentWidget()
    layout_before = window._layout_mode
    active_before = window._active_document_id

    monkeypatch.setattr(
        QFileDialog,
        "getExistingDirectory",
        lambda *_args, **_kwargs: str(open_folder),
    )
    window.action_map["Open Folder..."].trigger()
    qtbot.waitUntil(lambda: controller.is_idle, timeout=5000)  # type: ignore[attr-defined]

    assert [document.document_id for document in window.selected_documents] == selected_before
    assert [document.document_id for document in window.current_comparison_documents()] == (
        page_before
    )
    assert window.central_stack.currentWidget() is presented_before
    assert window._layout_mode == layout_before
    assert window._active_document_id == active_before

    recent = window.recent_entries_controller.repository
    folder_history = recent.load(RecentEntryKind.FOLDER)
    assert _history_count(folder_history, open_folder) == 1

    tag_controller = window.folder_display_tag_controller
    tag_controller.set_tag(drop_folder, "Candidate")
    window.document_list.paths_dropped.emit([drop_folder, direct])
    qtbot.waitUntil(lambda: controller.is_idle, timeout=5000)  # type: ignore[attr-defined]

    folder_history = recent.load(RecentEntryKind.FOLDER)
    image_history = recent.load(RecentEntryKind.IMAGE)
    assert _history_count(folder_history, open_folder) == 1
    assert _history_count(folder_history, drop_folder) == 1
    assert _history_count(image_history, direct) == 1
    assert [document.source_path for document in window.selected_documents] == [direct.resolve()]

    tagged_documents = [
        document
        for document in window.documents.values()
        if document.source_path is not None
        and document.source_path.parent == drop_folder.resolve()
    ]
    assert [document.display_name for document in tagged_documents] == [
        "[Candidate] drop0.png",
        "[Candidate] drop1.png",
    ]

    tagged_group = next(
        window.document_list.topLevelItem(index)
        for index in range(window.document_list.topLevelItemCount())
        if str(window.document_list.topLevelItem(index).data(0, window.document_list.PATH_ROLE))
        == str(drop_folder.resolve())
    )
    assert tagged_group.text(0) == "drop-folder [Candidate]"

    qtbot.waitUntil(lambda: not window._workers, timeout=3000)  # type: ignore[attr-defined]
    window.close()
