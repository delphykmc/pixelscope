from __future__ import annotations

from pathlib import Path

import numpy as np

from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.ui.document_list import DocumentListWidget


def test_file_icons_distinguish_kind_and_residency(qtbot: object, tmp_path: Path) -> None:
    tree = DocumentListWidget()
    qtbot.addWidget(tree)  # type: ignore[attr-defined]
    image = tree.add_document_item(
        "image",
        "image.png",
        tmp_path / "image.png",
        loading_state="pending",
        resident=False,
    )
    raw = tree.add_document_item(
        "raw",
        "frame.raw",
        tmp_path / "frame.raw",
        loading_state="pending",
        resident=False,
    )

    registered_icon = image.icon(0).cacheKey()
    assert registered_icon != raw.icon(0).cacheKey()
    assert "Not cached" in image.toolTip(0)

    tree.set_document_state(
        "image",
        loading_state="loading",
        resident=False,
    )
    loading_icon = image.icon(0).cacheKey()
    assert loading_icon != registered_icon
    assert "Loading into memory" in image.toolTip(0)

    tree.set_document_state(
        "image",
        loading_state="ready",
        resident=True,
    )
    cached_icon = image.icon(0).cacheKey()
    assert cached_icon not in (registered_icon, loading_icon)
    assert "Cached in memory" in image.toolTip(0)

    tree.set_document_state(
        "image",
        loading_state="error",
        resident=False,
    )
    error_icon = image.icon(0).cacheKey()
    assert error_icon not in (registered_icon, loading_icon, cached_icon)
    assert "Load failed" in image.toolTip(0)


def test_main_window_files_state_uses_actual_source_residency(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    ready = ImageDocument.from_array(
        np.zeros((4, 5, 3), dtype=np.uint8),
        "ready.png",
        source_path=tmp_path / "ready.png",
    )
    pending = ImageDocument.pending_document(tmp_path / "pending.png")

    window.add_document(ready, select=False)
    window.add_document(pending, select=False)

    ready_item = window.document_list.document_item(ready.document_id)
    pending_item = window.document_list.document_item(pending.document_id)
    assert ready_item is not None
    assert pending_item is not None
    assert "Cached in memory" in ready_item.toolTip(0)
    assert "Not cached" in pending_item.toolTip(0)
