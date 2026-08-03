from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtWidgets import QToolButton

from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument


def _ready_documents(count: int, prefix: str) -> list[ImageDocument]:
    return [
        ImageDocument.from_array(
            np.full((8, 10, 3), index * 10, dtype=np.uint8),
            f"{prefix}-{index + 1}.png",
        )
        for index in range(count)
    ]


def _navigation_labels(window: MainWindow) -> list[str]:
    layout = window.viewer.header.navigation_layout
    labels: list[str] = []
    for index in range(layout.count()):
        widget = layout.itemAt(index).widget()
        if isinstance(widget, QToolButton):
            labels.append(widget.text())
    return labels


def test_split_mode_uses_channel_loading_placeholders_without_unsplit_render(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    initial = _ready_documents(1, "initial")[0]
    window.add_document(initial)
    window.split_channels_action.trigger()
    assert window.split_channels_action.isChecked()
    assert len(window.multi_compare_view.occupied_viewers) == 3

    pending_path = tmp_path / "pending.png"
    pending = ImageDocument.pending_document(pending_path)
    window.add_document(pending, select=False)
    monkeypatch.setattr(window, "_ensure_loaded", lambda _document: None)

    window._select_document_ids([pending.document_id])

    visible_viewers = [
        viewer for viewer in window.multi_compare_view.visible_viewers if not viewer.isHidden()
    ]
    assert window.central_stack.currentWidget() is window.multi_compare_view
    assert window.multi_compare_view.capacity == 4
    assert len(visible_viewers) == 3
    assert all(viewer.document is None for viewer in visible_viewers)
    assert all(
        viewer._pending_document is not None  # noqa: SLF001 - loading presentation contract
        and viewer._pending_document.document_id.startswith(f"{pending.document_id}:split:")
        for viewer in visible_viewers
    )
    assert all(viewer._pending_document is not pending for viewer in visible_viewers)  # noqa: SLF001
    assert not window.split_channels_action.isEnabled()
    assert window.split_channels_action.isChecked()

    loaded = ImageDocument.from_array(
        np.full((8, 10, 3), 40, dtype=np.uint8),
        pending.display_name,
        source_path=pending_path,
    )
    loaded.document_id = pending.document_id
    loaded.generation = pending.generation
    window.documents[pending.document_id] = loaded
    window._render_selection()

    split_documents = [
        viewer.document for viewer in window.multi_compare_view.occupied_viewers
    ]
    assert len(split_documents) == 3
    assert [document.display_name.rsplit(" · ", 1)[-1] for document in split_documents] == [
        "R",
        "G",
        "B",
    ]
    assert window.split_channels_action.isEnabled()
    assert window.split_channels_action.isChecked()


@pytest.mark.parametrize("source_count", (3, 5))
def test_new_difference_is_first_in_multi_view(
    qtbot: object,
    source_count: int,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = _ready_documents(source_count, f"multi-diff-{source_count}")
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    window.set_layout_mode("Multi View")

    window.difference_panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_document is not None and window.diff_action.isChecked(),
        timeout=3000,
    )

    difference = window._difference_document
    assert difference is not None
    displayed = [
        viewer.document
        for viewer in window.multi_compare_view.occupied_viewers
        if viewer.document is not None
    ]
    assert displayed[0] is difference
    assert [document.document_id for document in displayed[1:]] == [
        document.document_id for document in documents
    ]
    assert window._focus_document_id == difference.document_id


def test_difference_calculated_in_single_view_stays_single_and_opens_diff(
    qtbot: object,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = _ready_documents(3, "single-diff")
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    window.set_layout_mode("Single View")

    window.difference_panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_document is not None
        and window.viewer.document is window._difference_document,
        timeout=3000,
    )

    assert window._layout_mode == "Single View"
    assert window.central_stack.currentWidget() is window.viewer
    assert window.viewer.document is window._difference_document
    assert _navigation_labels(window) == ["1", "2", "3", "Diff"]

    window.diff_action.trigger()
    assert not window.diff_action.isChecked()
    assert window._layout_mode == "Single View"
    assert window.viewer.document is documents[0]

    window.diff_action.trigger()
    assert window.diff_action.isChecked()
    assert window._layout_mode == "Single View"
    assert window.viewer.document is window._difference_document
    assert _navigation_labels(window) == ["1", "2", "3", "Diff"]
