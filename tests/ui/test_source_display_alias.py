from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtWidgets import QInputDialog

from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineSelection
from pixelscope.ui.folder_display_tags import install_folder_display_tags
from pixelscope.ui.plot_text import middle_elide

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
    analysis = window.comparison_analysis_panel
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(analysis.last_results) == 4 and analysis._worker is None,
        timeout=5000,
    )

    def assert_analysis_labels():
        assert [analysis.image_summary.item(i, 1).text() for i in range(4)] == [
            document.display_name for document in documents
        ]
        assert [plot.plotItem.titleLabel.text for plot in analysis.plots[:4]] == [
            middle_elide(f"{i + 1} · {document.display_name}")
            for i, document in enumerate(documents)
        ]

    assert_analysis_labels()

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
        document.display_name == label
        for document, label in zip(documents, comparison_labels(documents), strict=True)
    )
    assert all(
        document.display_name == window.line_profile_panel._document_label(document)
        for document in documents
    )
    assert all(
        document.display_name in window.difference_panel.a_selector.itemText(index)
        for index, document in enumerate(documents)
    )

    panel = window.difference_panel
    panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: panel.last_result is not None and panel.difference_cache.entry_count >= 1,
        timeout=3000,
    )
    cached_key = panel._cache_key()
    assert cached_key is not None
    cached_value = panel.difference_cache.peek(cached_key)
    cached_entries = panel.difference_cache.entry_count
    previous_difference = window._difference_document
    before_focus = window._focus_document_id
    before_active = window._active_document_id
    before_pick = [viewer.header.pick.isChecked() for viewer in presented]

    before_ids = tuple(window.documents)
    before_generations = tuple(doc.generation for doc in documents)
    before_arrays = tuple(id(doc.source) for doc in documents)
    before_selected = tuple(window._selection_order)
    before_cache_key = window.difference_panel._cache_key()
    previous_statistics = analysis.last_results
    previous_analysis_request = analysis._request_signature

    tags.set_tag(paths[0].parent, "Reference")
    assert documents[0].display_name == "[Reference] chart.png"
    assert_analysis_labels()
    assert analysis.last_results is previous_statistics
    assert analysis._request_signature == previous_analysis_request
    assert analysis._worker is None
    assert tuple(window.documents) == before_ids
    assert tuple(doc.generation for doc in documents) == before_generations
    assert tuple(id(doc.source) for doc in documents) == before_arrays
    assert tuple(window._selection_order) == before_selected
    assert window.difference_panel._cache_key() == before_cache_key
    assert panel.difference_cache.entry_count == cached_entries
    assert panel.difference_cache.peek(cached_key) is cached_value
    assert window._difference_document is previous_difference
    assert window._focus_document_id == before_focus
    assert window._active_document_id == before_active
    assert [viewer.header.pick.isChecked() for viewer in presented] == before_pick

    tags.set_tag(paths[0].parent, "")
    assert documents[0].display_name == "base / chart.png"
    assert_analysis_labels()
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


def test_source_replacement_reapplies_alias_without_changing_document_id(
    qtbot: object, tmp_path: Path
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    install_folder_display_tags(window)
    first = _document(tmp_path / "before" / "same.png")
    second = _document(tmp_path / "after" / "same.png")
    window.add_document(first, select=False)
    window.add_document(second, select=False)
    old_id = first.document_id
    assert first.display_name == "before / same.png"
    replacement = _document(first.source_path)
    replacement.document_id = old_id
    replacement.generation = first.generation + 1
    window.documents[old_id] = replacement
    window._update_document_item(replacement)
    assert replacement.display_name == "before / same.png"
    assert replacement.document_id == old_id
    assert second.display_name == "after / same.png"
    window.close()


def test_tag_updates_line_reference_labels_without_changing_analysis_or_reference(
    qtbot: object, tmp_path: Path
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    tags = install_folder_display_tags(window)
    documents = [_document(tmp_path / folder / "same.png") for folder in ("a", "b")]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    window._shared_line_changed(LineSelection(0, 0, 6))
    line = window.line_profile_panel
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(line.last_results) == 2 and line._worker is None, timeout=5000
    )
    line.y_mode.setCurrentText("Difference from reference")
    line.reference_selector.setCurrentIndex(1)
    reference = (line._reference_document_id, line._reference_locked)
    results = line.last_results
    signature = line._request_signature
    changes: list[int] = []
    line.reference_selector.currentIndexChanged.connect(changes.append)

    for tag in ("Reference", ""):
        tags.set_tag(documents[1].source_path.parent, tag)
        assert line._document_label(documents[1]) == documents[1].display_name
        assert line.reference_selector.currentData() == documents[1].document_id
        assert line.reference_selector.itemText(1) == (f"2 · {line._document_label(documents[1])}")
        assert (line._reference_document_id, line._reference_locked) == reference
        assert line.last_results is results
        assert line._request_signature == signature
        assert line._worker is None
        assert changes == []
    window.close()
