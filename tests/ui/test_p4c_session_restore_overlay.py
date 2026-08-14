from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QDialog

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.comparison_set import Session, SessionDifference, SessionSource
from pixelscope.core.image_document import ImageDocument
from pixelscope.io.comparison_set_repository import ComparisonSetRepository
from pixelscope.ui.display_gain import display_gain_state
from pixelscope.ui.session_restore_overlay import SESSION_RESTORE_STEPS


def _window(qtbot: object) -> MainWindow:
    QSettings().clear()
    display_gain_state().set_gain(1.0)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    return window


def _ready_document(path: Path, value: int) -> ImageDocument:
    path.write_bytes(b"ready-session-source")
    return ImageDocument.from_array(
        np.full((8, 8), value, dtype=np.uint8),
        path.name,
        source_path=path,
    )


def test_restore_overlay_is_main_window_owned_non_dialog(qtbot: object) -> None:
    window = _window(qtbot)
    overlay = window.session_controller._restore_overlay

    assert overlay.parentWidget() is window
    assert not isinstance(overlay, QDialog)
    assert overlay.step_count == 8
    assert tuple(row.text()[3:] for row in overlay.step_rows) == SESSION_RESTORE_STEPS
    assert overlay.isHidden()

    overlay.begin("Reading test Session")
    overlay.update_progress(4, 0.5, "3 / 6 images ready")

    assert not overlay.isHidden()
    assert overlay.step_label.text() == "Step 4 of 8 · Loading current page"
    assert overlay.detail_label.text() == "3 / 6 images ready"
    assert 400 < overlay.progress_bar.value() < 500
    assert overlay.step_rows[2].property("restoreState") == "done"
    assert overlay.step_rows[3].property("restoreState") == "current"
    assert overlay.step_rows[4].property("restoreState") == "pending"

    overlay.finish()
    assert overlay.isHidden()
    window.close()


def test_restore_overlay_reports_current_page_load_without_owning_it(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    paths = [tmp_path / "a.png", tmp_path / "b.png"]
    for path in paths:
        path.write_bytes(b"pending-image")
    target = tmp_path / "pending.pixelscope"
    ComparisonSetRepository().save(
        target,
        Session(
            registered_sources=tuple(SessionSource(str(path)) for path in paths),
            selected_paths=tuple(str(path) for path in paths),
        ),
    )

    window = _window(qtbot)
    requested: list[str] = []

    def observe_load(document: object) -> None:
        document_id = getattr(document, "document_id", None)
        if isinstance(document_id, str):
            requested.append(document_id)

    monkeypatch.setattr(window, "_ensure_loaded", observe_load)  # type: ignore[attr-defined]
    loaded, missing = window.session_controller.open_from_path(target)

    assert loaded == 2
    assert missing == ()
    window.session_controller._try_restore_deferred_state()

    overlay = window.session_controller._restore_overlay
    assert not overlay.isHidden()
    assert overlay.step_label.text() == "Step 4 of 8 · Loading current page"
    assert overlay.detail_label.text() == "0 / 2 images ready"
    assert len(set(requested)) == 2

    overlay.abort()
    window.close()


def test_restore_overlay_finishes_after_fast_path_session(
    qtbot: object,
    tmp_path: Path,
) -> None:
    paths = [tmp_path / "ready-a.png", tmp_path / "ready-b.png"]
    documents = [
        _ready_document(paths[0], 10),
        _ready_document(paths[1], 20),
    ]
    target = tmp_path / "ready.pixelscope"
    ComparisonSetRepository().save(
        target,
        Session(
            registered_sources=tuple(SessionSource(str(path)) for path in paths),
            selected_paths=tuple(str(path) for path in paths),
        ),
    )

    window = _window(qtbot)
    for document in documents:
        window.add_document(document, select=False)

    loaded, missing = window.session_controller.open_from_path(target)

    assert loaded == 2
    assert missing == ()
    overlay = window.session_controller._restore_overlay
    qtbot.waitUntil(overlay.isHidden, timeout=3000)  # type: ignore[attr-defined]
    assert overlay.progress_bar.value() == overlay.progress_bar.maximum()
    assert overlay.step_label.text() == "Step 8 of 8 · Finalizing workspace"
    window.close()


def test_full_restore_hides_overlay_after_difference_and_final_primary(
    qtbot: object,
    tmp_path: Path,
) -> None:
    paths = [tmp_path / f"full-{index}.png" for index in range(5)]
    documents = [
        _ready_document(path, 20 + index * 10)
        for index, path in enumerate(paths)
    ]
    target = tmp_path / "full.pixelscope"
    ComparisonSetRepository().save(
        target,
        Session(
            registered_sources=tuple(SessionSource(str(path)) for path in paths),
            selected_paths=tuple(str(path) for path in paths),
            primary_path=str(paths[1]),
            layout_mode="Multi View",
            display_gain=2.0,
            difference=SessionDifference(
                image_a_path=str(paths[0]),
                image_b_path=str(paths[1]),
                channel="Gray",
            ),
        ),
    )

    window = _window(qtbot)
    for document in documents:
        window.add_document(document, select=False)

    loaded, missing = window.session_controller.open_from_path(target)

    assert loaded == 5
    assert missing == ()
    overlay = window.session_controller._restore_overlay
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_document is not None,
        timeout=5000,
    )
    qtbot.waitUntil(overlay.isHidden, timeout=3000)  # type: ignore[attr-defined]
    primary = window.documents.get(window._focus_document_id or "")
    assert primary is not None
    assert primary.source_path == paths[1]
    assert overlay.progress_bar.value() == overlay.progress_bar.maximum()
    assert display_gain_state().gain == 2.0
    window.close()
