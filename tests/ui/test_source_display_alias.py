from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtWidgets import QInputDialog

from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.ui.folder_display_tags import install_folder_display_tags

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _document(path: Path) -> ImageDocument:
    return ImageDocument.from_array(
        np.full((8, 10, 3), 10, dtype=np.uint8),
        path.name,
        source_path=path,
    )


def test_four_duplicate_sources_share_display_alias_across_presentations(
    qtbot: object, tmp_path: Path
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    tags = install_folder_display_tags(window)
    paths = [tmp_path / folder / "chart.png" for folder in ("base", "noise", "tone", "sharp")]
    documents = [_document(path) for path in paths]
    for document in documents:
        window.add_document(document, select=False)
    assert [document.display_name for document in documents] == [
        f"{folder} / chart.png" for folder in ("base", "noise", "tone", "sharp")
    ]

    window._select_document_ids([document.document_id for document in documents])
    window.set_layout_mode("Multi View")
    window.show()
    qtbot.wait(20)  # type: ignore[attr-defined]

    presented = [viewer for viewer in window.multi_compare_view.occupied_viewers if viewer.document]
    assert {viewer.header._display_name for viewer in presented} == {
        document.display_name for document in documents
    }
    assert all(viewer.header.edit_tag.isVisible() for viewer in presented)
    assert all(
        viewer.header._display_name in viewer.header.name.toolTip()
        and str(viewer.document.source_path) in viewer.header.name.toolTip()
        for viewer in presented
    )

    # This is the existing typed/statistics + plots + line + Difference label
    # path, not another registered source or a new identity authority.
    from pixelscope.ui.comparison_analysis_panel import comparison_labels

    assert all(
        document.display_name in label
        for document, label in zip(documents, comparison_labels(documents), strict=True)
    )
    assert all(
        document.display_name in window.line_profile_panel._document_label(document)
        for document in documents
    )
    assert all(
        document.display_name in window.difference_panel.a_selector.itemText(index)
        for index, document in enumerate(documents)
    )

    before_ids = tuple(window.documents)
    before_generations = tuple(doc.generation for doc in documents)
    before_arrays = tuple(id(doc.source) for doc in documents)
    before_selected = tuple(window._selection_order)
    before_cache_key = window.difference_panel._cache_key()

    tags.set_tag(paths[0].parent, "Reference")
    assert documents[0].display_name == "[Reference] chart.png"
    assert tuple(window.documents) == before_ids
    assert tuple(doc.generation for doc in documents) == before_generations
    assert tuple(id(doc.source) for doc in documents) == before_arrays
    assert tuple(window._selection_order) == before_selected
    assert window.difference_panel._cache_key() == before_cache_key

    tags.set_tag(paths[0].parent, "")
    assert documents[0].display_name == "base / chart.png"
    window.close()


def test_tile_header_edits_existing_persistent_folder_tag(
    qtbot: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    tags = install_folder_display_tags(window)
    source = _document(tmp_path / "originals" / "sample.png")
    window.add_document(source)
    window.show()
    qtbot.wait(20)  # type: ignore[attr-defined]

    monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: ("기준 영상", True))
    assert window.viewer.header.edit_tag.isVisible()
    window.viewer.header.edit_tag.click()
    assert tags.tag_for_folder(source.source_path.parent) == "기준 영상"
    assert source.display_name == "[기준 영상] sample.png"
    window.close()

    reopened = MainWindow()
    qtbot.addWidget(reopened)  # type: ignore[attr-defined]
    install_folder_display_tags(reopened)
    replacement = _document(tmp_path / "originals" / "sample.png")
    reopened.add_document(replacement)
    assert replacement.display_name == "[기준 영상] sample.png"
    reopened.close()


def test_aliases_remain_stable_across_six_image_pagination_and_removal(
    qtbot: object, tmp_path: Path
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    install_folder_display_tags(window)
    documents = [_document(tmp_path / f"run-{index}" / "same.png") for index in range(7)]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([doc.document_id for doc in documents])
    first_labels = {doc.document_id: doc.display_name for doc in documents}
    assert len(set(first_labels.values())) == 7
    window.next_comparison_page()
    assert window._page_start == 6
    assert {doc.document_id: doc.display_name for doc in documents} == first_labels

    # Removing a source may shorten another presentation label but cannot
    # modify generation, selected/order identity or native bytes.
    window._remove_document_ids([documents[-1].document_id])
    assert documents[-1].document_id not in window.documents
    assert all(doc.display_name == first_labels[doc.document_id] for doc in documents[:-1])
    window.close()
