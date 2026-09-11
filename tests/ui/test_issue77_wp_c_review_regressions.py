from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QEvent

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.display_transform import render_ordinary_display_preview
from pixelscope.core.image_document import ImageDocument
from pixelscope.ui.display_gain import display_gain_state
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
        lambda: window._difference_source_ids == pair and window.diff_action.isChecked(),
        timeout=5000,
    )


def _ordinary_gain_preview(document: ImageDocument, gain: float) -> np.ndarray:
    assert document.source is not None
    assert document.preview is not None
    return render_ordinary_display_preview(
        document.source,
        channel_layout=document.channel_layout,
        transform=document.display_transform,
        canonical_preview=document.preview,
        gain=gain,
    )


def test_blink_release_rejoins_display_gain_presentation_authority(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    first = _document("a.png", 10, tmp_path)
    second = _document("b.png", 200, tmp_path)
    _add(window, [first, second])
    window._select_document_ids([first.document_id, second.document_id])
    window.show()
    qtbot.wait(20)  # type: ignore[attr-defined]

    reference_viewer = controller._viewer_for_document(first.document_id)
    alternate_viewer = controller._viewer_for_document(second.document_id)
    assert reference_viewer is not None
    assert alternate_viewer is not None
    alternate_image = np.array(alternate_viewer.image_item.image, copy=True)

    assert controller._begin_blink()
    assert np.array_equal(reference_viewer.image_item.image, alternate_image)

    state = display_gain_state()
    state.set_gain(2.0)
    expected_alternate = _ordinary_gain_preview(second, 2.0)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: controller._blink_cache_preview is not None
        and np.array_equal(reference_viewer.image_item.image, expected_alternate),
        timeout=5000,
    )
    assert controller._blink_snapshot is not None

    controller._end_blink()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: reference_viewer._displayed_gain == 2.0
        and reference_viewer._display_preview_worker is None,
        timeout=5000,
    )

    assert reference_viewer._displayed_gain == 2.0
    assert not np.array_equal(reference_viewer.image_item.image, expected_alternate)
    state.reset()
    window.close()


def test_blink_restores_when_application_deactivates(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    first = _document("a.png", 10, tmp_path)
    second = _document("b.png", 200, tmp_path)
    _add(window, [first, second])
    window._select_document_ids([first.document_id, second.document_id])
    window.show()
    qtbot.wait(20)  # type: ignore[attr-defined]

    reference_viewer = controller._viewer_for_document(first.document_id)
    assert reference_viewer is not None
    reference_image = np.array(reference_viewer.image_item.image, copy=True)

    assert controller._begin_blink()
    event = QEvent(QEvent.Type.ApplicationDeactivate)
    assert not controller.eventFilter(window, event)

    assert controller._blink_snapshot is None
    assert np.array_equal(reference_viewer.image_item.image, reference_image)
    window.close()


def test_single_view_blink_uses_current_visible_second_source_as_reference(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    first = _document("a.png", 10, tmp_path)
    second = _document("b.png", 200, tmp_path)
    _add(window, [first, second])
    window._select_document_ids([first.document_id, second.document_id])
    window.set_layout_mode("Single View")
    window.show_selected_image(1)
    window.show()
    qtbot.wait(20)  # type: ignore[attr-defined]

    assert window.viewer.document is second
    reference_image = np.array(window.viewer.image_item.image, copy=True)
    authority = (
        tuple(_ids(window)),
        window._current_index,
        window._focus_document_id,
        window._active_document_id,
        window._difference_source_ids,
    )

    assert controller._begin_blink()
    snapshot = controller._blink_snapshot
    assert snapshot is not None
    assert snapshot.viewer is window.viewer
    assert snapshot.reference is second
    assert snapshot.alternate is first
    assert np.array_equal(window.viewer.image_item.image, first.preview)

    controller._end_blink()
    assert window.viewer.document is second
    assert np.array_equal(window.viewer.image_item.image, reference_image)
    assert authority == (
        tuple(_ids(window)),
        window._current_index,
        window._focus_document_id,
        window._active_document_id,
        window._difference_source_ids,
    )
    window.close()


def test_single_view_blink_renders_alternate_at_current_display_gain(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    first = _document("a.png", 10, tmp_path)
    second = _document("b.png", 100, tmp_path)
    _add(window, [first, second])
    window._select_document_ids([first.document_id, second.document_id])
    window.set_layout_mode("Single View")
    window.show_selected_image(1)
    window.show()
    qtbot.wait(20)  # type: ignore[attr-defined]

    assert window.viewer.document is second
    state = display_gain_state()
    state.set_gain(2.0)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.viewer._displayed_gain == 2.0
        and window.viewer._display_preview_worker is None,
        timeout=5000,
    )
    expected_reference = _ordinary_gain_preview(second, 2.0)
    expected_alternate = _ordinary_gain_preview(first, 2.0)
    assert np.array_equal(window.viewer.image_item.image, expected_reference)

    assert controller._begin_blink()
    snapshot = controller._blink_snapshot
    assert snapshot is not None
    assert snapshot.reference is second
    assert snapshot.alternate is first
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: controller._blink_cache_preview is not None
        and np.array_equal(window.viewer.image_item.image, expected_alternate),
        timeout=5000,
    )

    controller._end_blink()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.viewer._displayed_gain == 2.0
        and window.viewer._display_preview_worker is None,
        timeout=5000,
    )
    assert window.viewer.document is second
    assert np.array_equal(window.viewer.image_item.image, expected_reference)
    state.reset()
    window.close()


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
    assert controller._pending_difference_pair is None
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
