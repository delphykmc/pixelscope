from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
from PySide6.QtCore import QSettings

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.comparison_set import Session, SessionDifference, SessionSource
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
    qtbot.waitUntil(lambda: window._difference_document is not None, timeout=5000)  # type: ignore[attr-defined]
    assert window._difference_source_ids is not None
    assert window._shared_roi == RoiBounds(8, 8, 24, 24)
    assert window._shared_line == LineSelection(4, 4, 40, 4)
    assert display_gain_state().gain == 2.0
    assert len(window.multi_compare_view.occupied_viewers) == 5
    assert window.diff_action.isChecked()
    window.close()
