from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QSettings

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.comparison_set import ComparisonSet, ComparisonSetSource
from pixelscope.core.image_document import ImageDocument


def _production_window(qtbot: object) -> MainWindow:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    return window


def _ready_document(path: Path, value: int) -> ImageDocument:
    path.write_bytes(b"registered-test-source")
    return ImageDocument.from_array(
        np.full((4, 4), value, dtype=np.uint8),
        path.name,
        source_path=path,
    )


def _register(window: MainWindow, documents: list[ImageDocument]) -> None:
    for document in documents:
        window.add_document(document, select=False)


def test_save_uses_logical_selected_not_temporary_pick_set(qtbot: object, tmp_path: Path) -> None:
    QSettings().clear()
    documents = [_ready_document(tmp_path / f"image{i}.png", i) for i in range(3)]
    window = _production_window(qtbot)
    _register(window, documents)
    window._select_document_ids([document.document_id for document in documents])
    review = window.review_selection_controller
    review.state.enter([document.document_id for document in documents])
    review.state.set_picked(documents[1].document_id, True)

    saved = window.comparison_set_controller.save_to_path(tmp_path / "set.pixelscope")

    assert [Path(source.path).name for source in saved.sources] == [
        "image0.png",
        "image1.png",
        "image2.png",
    ]
    assert review.active
    assert review.picked_ids == {documents[1].document_id}
    window.close()


def test_keep_selection_result_is_the_saved_comparison_set(qtbot: object, tmp_path: Path) -> None:
    QSettings().clear()
    documents = [_ready_document(tmp_path / f"image{i}.png", i) for i in range(4)]
    window = _production_window(qtbot)
    _register(window, documents)
    window._select_document_ids([document.document_id for document in documents])
    review = window.review_selection_controller
    review.state.enter([document.document_id for document in documents])
    review.state.set_picked(documents[1].document_id, True)
    review.state.set_picked(documents[3].document_id, True)
    assert review.keep_picked()

    saved = window.comparison_set_controller.save_to_path(tmp_path / "curated.pixelscope")

    assert [Path(source.path).name for source in saved.sources] == ["image1.png", "image3.png"]
    window.close()


def test_open_restores_order_active_primary_layout_and_keeps_other_registered(
    qtbot: object,
    tmp_path: Path,
) -> None:
    QSettings().clear()
    documents = [_ready_document(tmp_path / f"image{i}.png", i) for i in range(4)]
    extra = _ready_document(tmp_path / "extra.png", 9)
    window = _production_window(qtbot)
    _register(window, [*documents, extra])
    window._select_document_ids([documents[2].document_id, documents[0].document_id, documents[1].document_id])
    window.set_layout_mode("Multi View")
    window._set_focus_document(documents[0].document_id)
    window._set_active_document(documents[1])
    target = tmp_path / "set.pixelscope"
    window.comparison_set_controller.save_to_path(target)

    window._select_document_ids([extra.document_id])
    window.set_layout_mode("Single View")
    loaded, missing = window.comparison_set_controller.open_from_path(target)

    assert loaded == 3
    assert missing == ()
    assert [document.document_id for document in window.selected_documents] == [
        documents[2].document_id,
        documents[0].document_id,
        documents[1].document_id,
    ]
    assert extra.document_id in window.documents
    assert window._active_document_id == documents[1].document_id
    assert window._focus_document_id == documents[0].document_id
    assert window._layout_mode == "Multi View"
    window.close()


def test_open_partial_missing_loads_valid_subset_and_invalidates_curation(
    qtbot: object,
    tmp_path: Path,
) -> None:
    QSettings().clear()
    first = _ready_document(tmp_path / "first.png", 1)
    second = _ready_document(tmp_path / "second.png", 2)
    window = _production_window(qtbot)
    _register(window, [first, second])
    window._select_document_ids([first.document_id, second.document_id])
    review = window.review_selection_controller
    review.state.enter([first.document_id, second.document_id])
    review.state.set_picked(first.document_id, True)
    artifact = ComparisonSet(
        sources=(
            ComparisonSetSource(second.source_path),
            ComparisonSetSource(tmp_path / "missing.png"),
        )
    )
    target = tmp_path / "partial.pixelscope"
    window.comparison_set_controller.repository.save(target, artifact)

    loaded, missing = window.comparison_set_controller.open_from_path(target)

    assert loaded == 1
    assert missing == ((tmp_path / "missing.png").resolve(),)
    assert [document.document_id for document in window.selected_documents] == [second.document_id]
    assert not review.active
    window.close()


def test_corrupt_or_zero_loadable_set_leaves_workspace_unchanged(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    QSettings().clear()
    document = _ready_document(tmp_path / "current.png", 1)
    window = _production_window(qtbot)
    _register(window, [document])
    window._select_document_ids([document.document_id])
    before_registered = set(window.documents)
    before_selected = [item.document_id for item in window.selected_documents]

    broken = tmp_path / "broken.pixelscope"
    broken.write_text("{bad", encoding="utf-8")
    with pytest.raises(Exception):
        window.comparison_set_controller.open_from_path(broken)
    assert set(window.documents) == before_registered
    assert [item.document_id for item in window.selected_documents] == before_selected

    unavailable = tmp_path / "unavailable.pixelscope"
    window.comparison_set_controller.repository.save(
        unavailable,
        ComparisonSet(sources=(ComparisonSetSource(tmp_path / "gone.png"),)),
    )
    monkeypatch.setattr("pixelscope.ui.comparison_set.QMessageBox.warning", lambda *args: None)
    loaded, _missing = window.comparison_set_controller.open_from_path(unavailable)
    assert loaded == 0
    assert set(window.documents) == before_registered
    assert [item.document_id for item in window.selected_documents] == before_selected
    window.close()
