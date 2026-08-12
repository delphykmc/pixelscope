from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import QSettings, Qt

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.comparison_set import (
    Session,
    SessionDifference,
    SessionSource,
)
from pixelscope.core.line_profile import LineSelection
from pixelscope.core.roi import RoiBounds
from pixelscope.io.comparison_set_repository import ComparisonSetRepository
from pixelscope.ui.display_gain import display_gain_state


def _production_window(qtbot: object) -> MainWindow:
    QSettings().clear()
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    return window


def test_session_restore_modal_gate_lives_until_final_diff_view(
    qtbot: object,
    tmp_path: Path,
) -> None:
    paths = [tmp_path / f"progress-{index}.png" for index in range(4)]
    for index, path in enumerate(paths):
        image = np.full((96, 96), 20 + index * 15, dtype=np.uint8)
        assert cv2.imwrite(str(path), image)

    session = Session(
        registered_sources=tuple(SessionSource(str(path)) for path in paths),
        selected_paths=tuple(str(path) for path in paths),
        active_path=str(paths[1]),
        primary_path=str(paths[0]),
        layout_mode="Multi View",
        roi=RoiBounds(8, 8, 32, 32),
        line=LineSelection(4, 4, 60, 4),
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
    target = tmp_path / "progress-session.pixelscope"
    ComparisonSetRepository().save(target, session)

    window = _production_window(qtbot)
    loaded, missing = window.session_controller.open_from_path(target)

    assert loaded == 4
    assert missing == ()
    dialog = window.session_controller._restore_dialog
    assert dialog is not None
    assert dialog.windowModality() == Qt.WindowModality.ApplicationModal

    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: all(document.source is not None for document in window.selected_documents),
        timeout=5000,
    )
    assert window.session_controller._restore_dialog is not None

    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_document is not None,
        timeout=5000,
    )
    assert len(window.multi_compare_view.occupied_viewers) == 5
    assert window._shared_roi == RoiBounds(8, 8, 32, 32)
    assert window._shared_line == LineSelection(4, 4, 60, 4)
    assert display_gain_state().gain == 2.0

    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.session_controller._restore_dialog is None,
        timeout=5000,
    )
    window.close()
