from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QSettings

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.comparison_set import Session, SessionSource
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineSelection
from pixelscope.core.roi import RoiBounds
from pixelscope.ui.display_gain import display_gain_state


def _production_window(qtbot: object) -> MainWindow:
    QSettings().clear()
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    return window


def _ready_document(path: Path, value: int) -> ImageDocument:
    path.write_bytes(b"session-restore-source")
    return ImageDocument.from_array(
        np.full((4, 4), value, dtype=np.uint8),
        path.name,
        source_path=path,
    )


def test_session_restores_roi_line_gain_and_difference_recipe_lazily(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    window = _production_window(qtbot)
    a = _ready_document(tmp_path / "a.png", 1)
    b = _ready_document(tmp_path / "b.png", 2)
    registered_only = _ready_document(tmp_path / "registered-only.png", 3)
    for document in (a, b, registered_only):
        window.add_document(document, select=False)
    window._select_document_ids([a.document_id, b.document_id])
    window.set_layout_mode("Multi View")
    window._set_active_document(b)
    window._set_focus_document(a.document_id)
    window._shared_roi = RoiBounds(1, 1, 2, 2)
    window._shared_line = LineSelection(0, 0, 3, 0)
    display_gain_state().set_gain(4.0)
    window.difference_panel.set_documents(
        [a, b],
        (a.document_id, b.document_id),
        window._shared_roi,
    )
    window.difference_panel.mode.setCurrentText("Mask")
    window.difference_panel.threshold.setValue(2.0)
    window.difference_panel.gain.setValue(3)
    window.difference_panel.region.setCurrentText("Active ROI")
    window._difference_source_ids = (a.document_id, b.document_id)
    window._difference_document = object()
    target = tmp_path / "workspace.pixelscope"
    window.session_controller.save_to_path(target)

    extra = _ready_document(tmp_path / "extra.png", 9)
    window.add_document(extra, select=False)
    window._shared_roi = None
    window._shared_line = None
    display_gain_state().set_gain(1.0)
    window._difference_document = None
    window._difference_source_ids = None
    window._select_document_ids([extra.document_id])
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(  # type: ignore[attr-defined]
        window.difference_panel,
        "calculate_difference",
        lambda: calls.append(
            (
                str(window.difference_panel.a_selector.currentData()),
                str(window.difference_panel.b_selector.currentData()),
            )
        ),
    )

    loaded, missing = window.session_controller.open_from_path(target)

    assert loaded == 3
    assert missing == ()
    assert calls == []
    assert extra.document_id not in window.documents
    assert registered_only.document_id in window.documents
    qtbot.waitUntil(lambda: bool(calls))  # type: ignore[attr-defined]
    assert window._shared_roi == RoiBounds(1, 1, 2, 2)
    assert window._shared_line == LineSelection(0, 0, 3, 0)
    assert display_gain_state().gain == 4.0
    assert window.difference_panel.mode.currentText() == "Mask"
    assert window.difference_panel.threshold.value() == 2.0
    assert window.difference_panel.gain.value() == 3
    assert window.difference_panel.region.currentText() == "Active ROI"
    window.close()


def test_session_open_does_not_decode_registered_only_sources(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    paths = [tmp_path / f"image-{index:02d}.png" for index in range(12)]
    for path in paths:
        path.write_bytes(b"pending-session-source")
    session = Session(
        registered_sources=tuple(SessionSource(str(path)) for path in paths),
        selected_paths=tuple(str(path) for path in paths[:2]),
        active_path=str(paths[1]),
        layout_mode="Multi View",
    )
    target = tmp_path / "large-session.pixelscope"

    window = _production_window(qtbot)
    window.session_controller.repository.save(target, session)
    requested: list[str] = []
    monkeypatch.setattr(  # type: ignore[attr-defined]
        window,
        "_ensure_loaded",
        lambda document: requested.append(document.document_id),
    )

    loaded, missing = window.session_controller.open_from_path(target)

    assert loaded == 12
    assert missing == ()
    selected_ids = {document.document_id for document in window.selected_documents}
    assert set(requested) == selected_ids
    registered_only_ids = set(window.documents) - selected_ids
    assert registered_only_ids.isdisjoint(requested)
    window.close()
