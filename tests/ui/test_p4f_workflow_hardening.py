from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QFrame, QWidget

import pixelscope.ui.image_viewer as image_viewer_module
from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.comparison_set import Session, SessionDifference, SessionSource
from pixelscope.core.image_document import ImageDocument
from pixelscope.io.comparison_set_repository import ComparisonSetRepository
from pixelscope.ui.display_gain import display_gain_state


def _window(qtbot: object) -> MainWindow:
    QSettings().clear()
    display_gain_state().set_gain(1.0)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    return window


def _ready_gray(path: Path, value: int) -> ImageDocument:
    source = np.full((32, 32), value, dtype=np.uint8)
    assert cv2.imwrite(str(path), source)
    return ImageDocument.from_array(source, path.name, source_path=path)


def test_production_presentation_composition_reuses_display_gain_installation(
    qtbot: object,
) -> None:
    window = _window(qtbot)
    first_control = window._display_gain_control
    first_lifetime = window._display_gain_window_lifetime
    first_shortcuts = window.central_stack._display_gain_shortcuts

    display_gain_state().set_gain(4.0)
    second_control = _compose_main_window_presentation(window)

    assert second_control is first_control
    assert window._display_gain_control is first_control
    assert window._display_gain_window_lifetime is first_lifetime
    assert display_gain_state().gain == 4.0
    assert len(window.findChildren(QWidget, "DisplayGainControl")) == 1
    assert len(window.findChildren(QFrame, "displayGainSeparator")) == 1
    second_shortcuts = window.central_stack._display_gain_shortcuts
    assert len(second_shortcuts) == 2
    assert all(
        second is first
        for second, first in zip(second_shortcuts, first_shortcuts, strict=True)
    )
    window.close()


def test_session_save_persists_page_anchor_independently_of_active_and_primary(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window = _window(qtbot)
    documents = [
        _ready_gray(tmp_path / f"page-{index:02d}.png", 10 + index)
        for index in range(12)
    ]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    window.set_layout_mode("Multi View")
    window.next_comparison_page()

    assert [
        document.source_path for document in window.current_comparison_documents()
    ] == [document.source_path for document in documents[6:12]]

    # Session page identity is durable workspace intent in its own right. Saving the
    # page must not depend on source Active/Primary fallback being available.
    window._active_document_id = None
    window._focus_document_id = None
    target = tmp_path / "page-anchor.pixelscope"
    saved = window.session_controller.save_to_path(target)

    assert saved.page_anchor_path == str(documents[6].source_path)
    persisted = ComparisonSetRepository().load(target)
    assert persisted.page_anchor_path == str(documents[6].source_path)
    window.close()


def test_keep_selection_clears_active_difference_before_session_save(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window = _window(qtbot)
    documents = [
        _ready_gray(tmp_path / f"keep-{index:02d}.png", 20 + index * 5)
        for index in range(7)
    ]
    for document in documents:
        window.add_document(document, select=False)
    selected_ids = [document.document_id for document in documents]
    window._select_document_ids(selected_ids)
    window.set_layout_mode("Multi View")

    window.difference_panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_document is not None
        and window._difference_source_ids is not None,
        timeout=5000,
    )
    if window.diff_action.isChecked():
        window.diff_action.setChecked(False)

    review = window.review_selection_controller
    assert review.enter_review()
    review.state.set_picked(documents[0].document_id, True)
    review.state.set_picked(documents[6].document_id, True)
    review._sync_all()

    assert review.keep_picked()
    assert [document.document_id for document in window.selected_documents] == [
        documents[0].document_id,
        documents[6].document_id,
    ]
    assert not review.active
    assert review.picked_count == 0
    assert window._difference_document is None
    assert window._difference_source_ids is None
    assert not window.diff_action.isChecked()
    assert not window.diff_action.isEnabled()

    target = tmp_path / "curated.pixelscope"
    saved = window.session_controller.save_to_path(target)
    assert saved.selected_paths == (
        str(documents[0].source_path),
        str(documents[6].source_path),
    )
    assert saved.difference is None
    window.close()


def test_closed_window_disarms_application_display_gain_callbacks(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    window = _window(qtbot)
    document = _ready_gray(tmp_path / "gain.png", 80)
    window.add_document(document, select=False)
    window._select_document_ids([document.document_id])
    window.set_layout_mode("Single View")
    window.show()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.viewer.presented_document is document,
        timeout=3000,
    )

    lifetime = window._display_gain_window_lifetime
    window.close()
    assert lifetime._shutting_down

    starts: list[object] = []

    class RecordingPool:
        def start(self, worker: object) -> None:
            starts.append(worker)

    monkeypatch.setattr(  # type: ignore[attr-defined]
        image_viewer_module,
        "_display_preview_thread_pool",
        lambda: RecordingPool(),
    )

    display_gain_state().set_gain(4.0)
    qtbot.wait(1)  # type: ignore[attr-defined]

    assert starts == []
    assert window.viewer._display_preview_worker is None


def test_session_restored_difference_export_consumes_settled_result_only(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    paths = [tmp_path / "export-a.png", tmp_path / "export-b.png"]
    for index, path in enumerate(paths):
        assert cv2.imwrite(
            str(path),
            np.full((48, 48), 30 + index * 20, dtype=np.uint8),
        )
    session = Session(
        registered_sources=tuple(SessionSource(str(path)) for path in paths),
        selected_paths=tuple(str(path) for path in paths),
        page_anchor_path=str(paths[0]),
        layout_mode="Multi View",
        display_gain=2.0,
        difference=SessionDifference(
            image_a_path=str(paths[0]),
            image_b_path=str(paths[1]),
            channel="Gray",
            mode="Absolute",
        ),
    )
    session_path = tmp_path / "export-restore.pixelscope"
    ComparisonSetRepository().save(session_path, session)

    window = _window(qtbot)
    loaded, missing = window.session_controller.open_from_path(session_path)
    assert loaded == 2
    assert missing == ()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_document is not None
        and window.difference_panel._worker is None
        and window.difference_panel._preview_worker is None
        and window.session_controller._restore_overlay.isHidden(),
        timeout=5000,
    )

    controller = window.analysis_export_controller
    controller.refresh_actions()
    assert controller.difference_action.isEnabled()
    generations = tuple(document.generation for document in window.selected_documents)
    cache_state = (
        window.difference_panel.difference_cache.used_bytes,
        window.difference_panel.difference_cache.entry_count,
        window.difference_panel.difference_cache.keys(),
    )

    def forbidden_calculate(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Difference export must not recalculate a restored result")

    monkeypatch.setattr(
        window.difference_panel,
        "calculate_difference",
        forbidden_calculate,
    )
    target = tmp_path / "restored-difference.png"
    monkeypatch.setattr(  # type: ignore[attr-defined]
        "pixelscope.ui.analysis_export.QFileDialog.getSaveFileName",
        lambda *_args, **_kwargs: (str(target), "PNG (*.png)"),
    )

    controller.export_difference_image()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: controller._difference_worker is None and target.is_file(),
        timeout=5000,
    )

    assert tuple(document.generation for document in window.selected_documents) == generations
    assert (
        window.difference_panel.difference_cache.used_bytes,
        window.difference_panel.difference_cache.entry_count,
        window.difference_panel.difference_cache.keys(),
    ) == cache_state
    assert display_gain_state().gain == 2.0
    window.close()
