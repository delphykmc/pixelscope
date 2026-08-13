from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QSettings

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.difference_cache import CachedDifferenceMap
from pixelscope.core.image_document import ImageDocument
from pixelscope.ui import difference_panel as difference_panel_module


def _window(
    qtbot: object,
    tmp_path: Path,
) -> tuple[MainWindow, list[ImageDocument]]:
    QSettings().clear()
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    documents = [
        ImageDocument.from_array(
            np.full((4, 4), index * 10, dtype=np.uint8),
            f"image{index + 1:02d}.png",
            source_path=tmp_path / f"image{index + 1:02d}.png",
        )
        for index in range(3)
    ]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    return window, documents


def test_cache_hit_calculate_and_toolbar_hide_show_do_not_recompute(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, documents = _window(qtbot, tmp_path)
    a, b = documents[:2]
    first = (a.document_id, a.generation)
    second = (b.document_id, b.generation)
    key = (first, second) if first <= second else (second, first)
    cached = CachedDifferenceMap(
        absolute=np.full((4, 4), 10, dtype=np.uint8),
        domain="native",
        data_range=255.0,
        channel_layout="GRAY",
        bayer_pattern=None,
    )
    assert window.difference_panel._map_cache.put(key, cached).stored

    def fail_map(*_args: object, **_kwargs: object) -> np.ndarray:
        raise AssertionError("cached Difference map was recomputed")

    monkeypatch.setattr(
        difference_panel_module,
        "compact_absolute_difference",
        fail_map,
    )
    monkeypatch.setattr(
        difference_panel_module,
        "normalized_absolute_difference",
        fail_map,
    )
    window.difference_panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_document is not None,
        timeout=5000,
    )

    difference = window._difference_document
    provenance = window._difference_source_ids
    assert difference is not None
    assert window.difference_panel._map_cache.peek(key) is cached
    assert window.diff_action.isEnabled()
    assert window.diff_action.isChecked()

    calls: list[str] = []
    monkeypatch.setattr(
        window.difference_panel,
        "calculate_difference",
        lambda *_args, **_kwargs: calls.append("calculate"),
    )
    selector_ids = (
        window.difference_panel.a_selector.currentData(),
        window.difference_panel.b_selector.currentData(),
    )

    window.diff_action.setChecked(False)
    assert window.diff_action.isEnabled()
    assert not window.diff_action.isChecked()
    assert window._difference_document is difference
    assert window._difference_source_ids == provenance
    assert calls == []

    window.diff_action.setChecked(True)
    assert window.diff_action.isEnabled()
    assert window.diff_action.isChecked()
    assert window._difference_document is difference
    assert window._difference_source_ids == provenance
    assert (
        window.difference_panel.a_selector.currentData(),
        window.difference_panel.b_selector.currentData(),
    ) == selector_ids
    assert calls == []
    assert any(
        viewer.presented_document is difference
        for viewer in window.multi_compare_view.occupied_viewers
    )
    window.close()
