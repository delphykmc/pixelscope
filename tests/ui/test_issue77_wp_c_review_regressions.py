from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pixelscope.app.bootstrap import (
    compose_main_window_presentation as _compose_main_window_presentation,
)
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.ui.quick_compare import QuickCompareController

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _window(qtbot: object) -> tuple[MainWindow, QuickCompareController]:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    controller = window.quick_compare_controller
    assert isinstance(controller, QuickCompareController)
    return window, controller


def _document(name: str, value: int, tmp_path: Path) -> ImageDocument:
    return ImageDocument.from_array(
        np.full((6, 8), value, dtype=np.uint8),
        name,
        source_path=tmp_path / name,
    )


def _add(window: MainWindow, documents: list[ImageDocument]) -> None:
    for document in documents:
        window.add_document(document, select=False)


def _ids(window: MainWindow) -> list[str]:
    return [document.document_id for document in window.selected_documents]


def _wait_for_difference(
    qtbot: object,
    window: MainWindow,
    pair: tuple[str, str],
) -> None:
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.difference_panel.has_cached_map() and window.diff_action.isEnabled(),
        timeout=5000,
    )
    assert window._difference_source_ids is None
    assert not window.diff_action.isChecked()


def test_two_file_quick_compare_across_page_boundary_does_not_pin_pair(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    documents = [_document(f"{index}.png", index + 1, tmp_path) for index in range(7)]
    _add(window, documents)
    window._select_document_ids([document.document_id for document in documents[:5]])

    controller._apply_registered_drop([documents[5].document_id, documents[6].document_id])

    assert _ids(window) == [document.document_id for document in documents]
    assert window._difference_source_ids is None
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: controller._pending_difference_pair is None, timeout=3000
    )
    assert window.central_stack.updatesEnabled()
    assert "current page" in window.statusBar().currentMessage().lower()
    window.close()


def test_existing_difference_binding_survives_pagination_growth(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    documents = [_document(f"{index}.png", index + 1, tmp_path) for index in range(7)]
    _add(window, documents)

    controller._apply_registered_drop([documents[0].document_id, documents[1].document_id])
    pair = (documents[0].document_id, documents[1].document_id)
    _wait_for_difference(qtbot, window, pair)
    window.diff_action.setChecked(True)
    assert window._difference_source_ids == pair

    controller._apply_registered_drop([document.document_id for document in documents[2:]])

    assert _ids(window) == [document.document_id for document in documents]
    assert window._difference_source_ids == pair
    window.next_comparison_page()
    assert window._difference_source_ids == pair
    window.close()


def test_three_view_control_is_inserted_before_trailing_command_row_stretch(qtbot: object) -> None:
    window, controller = _window(qtbot)
    layout = window.presentation_controls_layout
    group_index = layout.indexOf(controller.three_view_group)
    spacer_indices = [
        index
        for index in range(layout.count())
        if layout.itemAt(index) is not None and layout.itemAt(index).spacerItem() is not None
    ]

    assert group_index >= 0
    assert spacer_indices
    assert group_index < min(spacer_indices)
    assert getattr(window, "_command_row_metric_refresh", None) is not None
    window.close()
