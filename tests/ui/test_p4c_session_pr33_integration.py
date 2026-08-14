from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest
from PySide6.QtCore import QSettings

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.comparison_set import Session, SessionDifference, SessionSource
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineSelection
from pixelscope.core.roi import RoiBounds
from pixelscope.io.comparison_set_repository import ComparisonSetRepository
from pixelscope.ui.display_gain import display_gain_state


def _window(qtbot: object) -> MainWindow:
    QSettings().clear()
    display_gain_state().set_gain(1.0)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    return window


def _write_gray(path: Path, value: int) -> None:
    assert cv2.imwrite(str(path), np.full((64, 64), value, dtype=np.uint8))


def _ready_gray(path: Path, value: int) -> ImageDocument:
    _write_gray(path, value)
    return ImageDocument.from_array(
        np.full((64, 64), value, dtype=np.uint8),
        path.name,
        source_path=path,
    )


def test_session_recipe_does_not_prebind_difference_provenance(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = [tmp_path / f"source-{index}.png" for index in range(2)]
    for index, path in enumerate(paths):
        _write_gray(path, 20 + index * 10)
    session = Session(
        registered_sources=tuple(SessionSource(str(path)) for path in paths),
        selected_paths=tuple(str(path) for path in paths),
        difference=SessionDifference(
            image_a_path=str(paths[0]),
            image_b_path=str(paths[1]),
            channel="Gray",
        ),
    )
    target = tmp_path / "recipe.pixelscope"
    ComparisonSetRepository().save(target, session)
    window = _window(qtbot)
    calls: list[tuple[object, object]] = []

    def observe_calculate() -> None:
        calls.append(
            (
                window.difference_panel.a_selector.currentData(),
                window.difference_panel.b_selector.currentData(),
            )
        )
        assert window._difference_source_ids is None
        assert window._difference_document is None

    monkeypatch.setattr(window.difference_panel, "calculate_difference", observe_calculate)
    loaded, missing = window.session_controller.open_from_path(target)
    assert loaded == 2
    assert missing == ()
    qtbot.waitUntil(lambda: bool(calls), timeout=5000)  # type: ignore[attr-defined]
    assert window._difference_source_ids is None
    window.close()


def test_later_comparison_page_restores_independently_of_active_presentation(
    qtbot: object,
    tmp_path: Path,
) -> None:
    paths = [tmp_path / f"later-{index:02d}.png" for index in range(12)]
    for index, path in enumerate(paths):
        _write_gray(path, 10 + index)
    session = Session(
        registered_sources=tuple(SessionSource(str(path)) for path in paths),
        selected_paths=tuple(str(path) for path in paths),
        page_anchor_path=str(paths[6]),
        active_path=str(paths[8]),
        primary_path=str(paths[6]),
        layout_mode="Multi View",
    )
    target = tmp_path / "later-page.pixelscope"
    ComparisonSetRepository().save(target, session)

    window = _window(qtbot)
    loaded, missing = window.session_controller.open_from_path(target)

    assert loaded == 12
    assert missing == ()
    assert [document.source_path for document in window.selected_documents] == paths
    assert [
        document.source_path for document in window.current_comparison_documents()
    ] == paths[6:12]
    active = window.documents.get(window._active_document_id or "")
    assert active is not None and active.source_path == paths[8]
    window.close()


def test_active_difference_restores_saved_page_before_explicit_calculate(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = [tmp_path / f"diff-page-{index:02d}.png" for index in range(12)]
    for index, path in enumerate(paths):
        _write_gray(path, 30 + index)
    session = Session(
        registered_sources=tuple(SessionSource(str(path)) for path in paths),
        selected_paths=tuple(str(path) for path in paths),
        page_anchor_path=str(paths[6]),
        active_path=None,
        primary_path=str(paths[6]),
        layout_mode="Multi View",
        difference=SessionDifference(
            image_a_path=str(paths[6]),
            image_b_path=str(paths[7]),
            channel="Gray",
        ),
    )
    target = tmp_path / "later-page-diff.pixelscope"
    ComparisonSetRepository().save(target, session)

    window = _window(qtbot)
    requested: list[Path] = []
    original_ensure_loaded = window._ensure_loaded

    def observed_ensure_loaded(document: object) -> None:
        source_path = getattr(document, "source_path", None)
        if isinstance(source_path, Path):
            requested.append(source_path)
        original_ensure_loaded(document)  # type: ignore[arg-type]

    monkeypatch.setattr(window, "_ensure_loaded", observed_ensure_loaded)
    calculations: list[tuple[object, object]] = []

    def observe_calculate() -> None:
        assert window._difference_source_ids is None
        assert window._difference_document is None
        assert [
            document.source_path for document in window.current_comparison_documents()
        ] == paths[6:12]
        calculations.append(
            (
                window.difference_panel.a_selector.currentData(),
                window.difference_panel.b_selector.currentData(),
            )
        )

    monkeypatch.setattr(window.difference_panel, "calculate_difference", observe_calculate)
    loaded, missing = window.session_controller.open_from_path(target)

    assert loaded == 12
    assert missing == ()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: bool(calculations),
        timeout=5000,
    )
    assert [
        document.source_path for document in window.current_comparison_documents()
    ] == paths[6:12]
    assert set(requested).issubset(set(paths[6:12]))
    assert not set(requested).intersection(paths[:6])
    assert window._difference_source_ids is None
    window.close()


def test_save_omits_hidden_difference_recipe_after_navigating_away_from_pair(
    qtbot: object,
    tmp_path: Path,
) -> None:
    paths = [tmp_path / f"off-page-{index:02d}.png" for index in range(12)]
    documents = [
        _ready_gray(path, 20 + index)
        for index, path in enumerate(paths)
    ]
    window = _window(qtbot)
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    window.set_layout_mode("Multi View")

    a_id = documents[0].document_id
    b_id = documents[1].document_id
    panel = window.difference_panel
    panel.set_documents(window.current_comparison_documents(), (a_id, b_id))
    panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_document is not None,
        timeout=5000,
    )
    assert window._difference_source_ids == (a_id, b_id)
    assert window.diff_action.isChecked()

    window.diff_action.trigger()
    assert not window.diff_action.isChecked()
    assert window._difference_source_ids == (a_id, b_id)

    window.next_comparison_page()
    assert [
        document.source_path for document in window.current_comparison_documents()
    ] == paths[6:12]
    assert window._difference_source_ids == (a_id, b_id)

    window._set_focus_document(documents[6].document_id)
    window._set_active_document(documents[6])
    target = tmp_path / "off-page-difference.pixelscope"
    saved = window.session_controller.save_to_path(target)

    assert saved.difference is None
    persisted = ComparisonSetRepository().load(target)
    assert persisted.difference is None
    assert persisted.page_anchor_path == str(paths[6])
    window.close()

    reopened = _window(qtbot)
    loaded, missing = reopened.session_controller.open_from_path(target)
    assert loaded == 12
    assert missing == ()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        reopened.session_controller._restore_overlay.isHidden,
        timeout=5000,
    )
    assert [
        document.source_path for document in reopened.current_comparison_documents()
    ] == paths[6:12]
    assert reopened._difference_document is None
    assert reopened._difference_source_ids is None
    reopened.close()


def test_unavailable_page_analysis_state_terminates_without_retry_loop(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = [tmp_path / f"unavailable-{index}.png" for index in range(2)]
    for path in paths:
        path.write_bytes(b"pending")
    session = Session(
        registered_sources=tuple(SessionSource(str(path)) for path in paths),
        selected_paths=tuple(str(path) for path in paths),
        page_anchor_path=str(paths[0]),
        roi=RoiBounds(0, 0, 1, 1),
        line=LineSelection(0, 0, 1, 0),
        difference=SessionDifference(
            image_a_path=str(paths[0]),
            image_b_path=str(paths[1]),
            channel="Gray",
            region="Active ROI",
        ),
    )
    target = tmp_path / "unavailable-analysis.pixelscope"
    ComparisonSetRepository().save(target, session)

    window = _window(qtbot)

    def fail_load(document: Any) -> None:
        document.loading_state = "error"

    monkeypatch.setattr(window, "_ensure_loaded", fail_load)
    loaded, missing = window.session_controller.open_from_path(target)
    assert loaded == 2
    assert missing == ()

    window.session_controller._try_restore_deferred_state()

    assert window.session_controller._pending_roi is None
    assert window.session_controller._pending_line is None
    assert window.session_controller._pending_difference is None
    assert "not restored" in window.statusBar().currentMessage()
    window.close()


def test_real_session_restore_reestablishes_diff_roi_line_and_gain(
    qtbot: object,
    tmp_path: Path,
) -> None:
    paths = [tmp_path / f"real-{index}.png" for index in range(4)]
    for index, path in enumerate(paths):
        _write_gray(path, 20 + index * 10)
    session = Session(
        registered_sources=tuple(SessionSource(str(path)) for path in paths),
        selected_paths=tuple(str(path) for path in paths),
        active_path=str(paths[1]),
        primary_path=str(paths[0]),
        layout_mode="Multi View",
        roi=RoiBounds(8, 8, 24, 24),
        line=LineSelection(4, 4, 40, 4),
        display_gain=2.0,
        difference=SessionDifference(
            image_a_path=str(paths[0]),
            image_b_path=str(paths[1]),
            channel="Gray",
            mode="Absolute",
            threshold=10.0,
            gain=1,
            region="Active ROI",
        ),
    )
    target = tmp_path / "roundtrip.pixelscope"
    ComparisonSetRepository().save(target, session)
    window = _window(qtbot)
    loaded, missing = window.session_controller.open_from_path(target)
    assert loaded == 4
    assert missing == ()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: all(document.source is not None for document in window.selected_documents),
        timeout=5000,
    )
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_document is not None,
        timeout=5000,
    )
    assert window._difference_source_ids is not None
    assert window._shared_roi == RoiBounds(8, 8, 24, 24)
    assert window._shared_line == LineSelection(4, 4, 40, 4)
    assert display_gain_state().gain == 2.0
    assert len(window.multi_compare_view.occupied_viewers) == 5
    assert window.diff_action.isChecked()
    window.close()


def test_difference_restore_finishes_with_saved_source_primary(
    qtbot: object,
    tmp_path: Path,
) -> None:
    paths = [tmp_path / f"primary-{index}.png" for index in range(5)]
    for index, path in enumerate(paths):
        _write_gray(path, 40 + index * 10)
    session = Session(
        registered_sources=tuple(SessionSource(str(path)) for path in paths),
        selected_paths=tuple(str(path) for path in paths),
        page_anchor_path=str(paths[0]),
        active_path=None,
        primary_path=str(paths[1]),
        layout_mode="Multi View",
        display_gain=2.0,
        difference=SessionDifference(
            image_a_path=str(paths[0]),
            image_b_path=str(paths[1]),
            channel="Gray",
            mode="Absolute",
        ),
    )
    target = tmp_path / "source-primary.pixelscope"
    ComparisonSetRepository().save(target, session)

    window = _window(qtbot)
    loaded, missing = window.session_controller.open_from_path(target)

    assert loaded == 5
    assert missing == ()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_document is not None,
        timeout=5000,
    )
    primary = window.documents.get(window._focus_document_id or "")
    assert primary is not None
    assert primary.source_path == paths[1]
    assert display_gain_state().gain == 2.0
    assert len(window.multi_compare_view.occupied_viewers) == 6
    window.close()
