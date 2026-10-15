from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

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
    assert [document.document_id for document in window.selected_documents] == [
        docs[0].document_id
    ]
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
    assert [document.document_id for document in window.selected_documents] == [
        docs[2].document_id
    ]
    window.close()
