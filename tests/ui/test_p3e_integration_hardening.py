from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QSettings, Qt
from PySide6.QtWidgets import QComboBox, QToolButton

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import COMPARISON_PAGE_SIZE, MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.ui.design_tokens import TOKENS
from pixelscope.ui.display_gain import display_gain_state, install_display_gain_control
from pixelscope.ui.presentation_controls import polish_presentation_controls


def _ready_documents(tmp_path: Path, count: int) -> list[ImageDocument]:
    return [
        ImageDocument.from_array(
            np.full((4, 4), index, dtype=np.uint8),
            f"image{index + 1:02d}.png",
            source_path=tmp_path / f"folder-{index:02d}" / f"image{index + 1:02d}.png",
        )
        for index in range(count)
    ]


def _pending_documents(tmp_path: Path, count: int) -> list[ImageDocument]:
    return [
        ImageDocument.pending_document(
            tmp_path / f"set-{index:02d}" / f"image{index + 1:02d}.png"
        )
        for index in range(count)
    ]


def _select_documents(window: MainWindow, documents: list[ImageDocument]) -> None:
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])


def _compose_production_window() -> tuple[MainWindow, QComboBox]:
    """Create a MainWindow through the exact production presentation composer."""

    window = MainWindow()
    return window, _compose_main_window_presentation(window)


@pytest.mark.parametrize(
    ("count", "page_count", "first_page_size"),
    ((1, 1, 1), (2, 1, 2), (6, 1, 6), (7, 2, 6)),
)
def test_canonical_selection_counts_share_one_page_authority(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    count: int,
    page_count: int,
    first_page_size: int,
) -> None:
    QSettings().clear()
    documents = _pending_documents(tmp_path, count)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    requested: list[str] = []
    monkeypatch.setattr(
        window,
        "_ensure_loaded",
        lambda document: requested.append(document.document_id),
    )

    _select_documents(window, documents)

    selected_ids = [document.document_id for document in documents]
    assert [document.document_id for document in window.selected_documents] == selected_ids
    assert [document.document_id for document in window.current_comparison_documents()] == (
        selected_ids[:first_page_size]
    )
    assert requested == selected_ids[:first_page_size]
    assert window.comparison_page_label.text() == f"1 / {page_count}"
    if count <= COMPARISON_PAGE_SIZE:
        assert not window.previous_comparison_page_button.isEnabled()
        assert not window.next_comparison_page_button.isEnabled()
    else:
        assert not window.previous_comparison_page_button.isEnabled()
        assert window.next_comparison_page_button.isEnabled()
    window.close()


def test_presentation_row_uses_stable_accessible_page_toolbuttons(
    qtbot: object,
    tmp_path: Path,
) -> None:
    QSettings().clear()
    display_gain_state().reset()
    documents = _ready_documents(tmp_path, 15)
    window, gain = _compose_production_window()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _select_documents(window, documents)
    window.show()

    previous = window.previous_comparison_page_button
    next_button = window.next_comparison_page_button
    assert isinstance(previous, QToolButton)
    assert isinstance(next_button, QToolButton)
    assert previous.accessibleName() == "Previous Comparison Page"
    assert next_button.accessibleName() == "Next Comparison Page"
    assert previous.text() == "Previous"
    assert next_button.text() == "Next"
    assert not previous.icon().isNull()
    assert not next_button.icon().isNull()
    assert previous.focusPolicy() == Qt.FocusPolicy.NoFocus
    assert next_button.focusPolicy() == Qt.FocusPolicy.NoFocus
    assert previous.size().width() == TOKENS.control_height
    assert next_button.size().width() == TOKENS.control_height
    assert window.layout_selector.height() == TOKENS.control_height
    assert gain.height() == TOKENS.control_height

    panel_layout = window.presentation_panel.layout()
    assert panel_layout is not None
    assert panel_layout.indexOf(window.presentation_controls) < panel_layout.indexOf(
        window.central_stack
    )
    assert window.presentation_controls.isAncestorOf(window.layout_selector)
    assert window.presentation_controls.isAncestorOf(window.comparison_page_group)
    assert window.presentation_controls.isAncestorOf(gain)

    page_layout = window.comparison_page_group.layout()
    assert page_layout is not None
    control_indices = (page_layout.indexOf(previous), page_layout.indexOf(next_button))
    assert not previous.isHidden()
    assert not next_button.isHidden()
    assert not previous.isEnabled()
    assert next_button.isEnabled()
    assert [shortcut.isEnabled() for shortcut in window._comparison_page_shortcuts] == [
        False,
        True,
    ]
    assert window.comparison_page_label.text() == "1 / 3"
    assert window.comparison_page_range_label.text() == "1–6 of 15"

    window.next_comparison_page()
    assert (page_layout.indexOf(previous), page_layout.indexOf(next_button)) == control_indices
    assert not previous.isHidden()
    assert not next_button.isHidden()
    assert previous.isEnabled()
    assert next_button.isEnabled()
    assert [shortcut.isEnabled() for shortcut in window._comparison_page_shortcuts] == [
        True,
        True,
    ]
    assert window.comparison_page_label.text() == "2 / 3"
    assert window.comparison_page_range_label.text() == "7–12 of 15"

    window.next_comparison_page()
    assert (page_layout.indexOf(previous), page_layout.indexOf(next_button)) == control_indices
    assert not previous.isHidden()
    assert not next_button.isHidden()
    assert previous.isEnabled()
    assert not next_button.isEnabled()
    assert [shortcut.isEnabled() for shortcut in window._comparison_page_shortcuts] == [
        True,
        False,
    ]
    assert window.comparison_page_label.text() == "3 / 3"
    assert window.comparison_page_range_label.text() == "13–15 of 15"
    window.close()
    display_gain_state().reset()


def test_production_composition_wires_page_gain_focus_and_lifetime(
    qtbot: object,
    tmp_path: Path,
) -> None:
    QSettings().clear()
    display_gain_state().reset()
    documents = _ready_documents(tmp_path, 15)
    window, gain = _compose_production_window()
    window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    _select_documents(window, documents)
    window.show()
    qtbot.waitUntil(lambda: window.isVisible())  # type: ignore[attr-defined]

    selected_ids = tuple(document.document_id for document in window.selected_documents)
    previous = window.previous_comparison_page_button
    next_button = window.next_comparison_page_button
    assert isinstance(previous, QToolButton)
    assert isinstance(next_button, QToolButton)
    assert not previous.isEnabled()
    assert next_button.isEnabled()

    qtbot.mouseClick(next_button, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
    qtbot.waitUntil(lambda: window._page_start == 6)  # type: ignore[attr-defined]
    assert tuple(document.document_id for document in window.selected_documents) == selected_ids
    assert window.comparison_page_label.text() == "2 / 3"
    assert previous.isEnabled()
    assert next_button.isEnabled()

    qtbot.mouseClick(next_button, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
    qtbot.waitUntil(lambda: window._page_start == 12)  # type: ignore[attr-defined]
    assert tuple(document.document_id for document in window.selected_documents) == selected_ids
    assert window.comparison_page_label.text() == "3 / 3"
    assert previous.isEnabled()
    assert not next_button.isEnabled()

    qtbot.mouseClick(previous, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
    qtbot.waitUntil(lambda: window._page_start == 6)  # type: ignore[attr-defined]
    assert tuple(document.document_id for document in window.selected_documents) == selected_ids
    assert window.comparison_page_label.text() == "2 / 3"

    qtbot.mouseClick(previous, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
    qtbot.waitUntil(lambda: window._page_start == 0)  # type: ignore[attr-defined]
    assert tuple(document.document_id for document in window.selected_documents) == selected_ids
    assert not previous.isEnabled()
    assert next_button.isEnabled()

    window.set_layout_mode("Single View")
    qtbot.waitUntil(lambda: window.viewer.document is documents[0])  # type: ignore[attr-defined]
    presentation_target = window.viewer._graphics.viewport()
    presentation_target.setFocus()
    qtbot.waitUntil(lambda: presentation_target.hasFocus())  # type: ignore[attr-defined]

    for _ in range(10):
        qtbot.keyClick(presentation_target, Qt.Key.Key_Plus)  # type: ignore[attr-defined]
    qtbot.waitUntil(lambda: gain.currentData() == 16.0)  # type: ignore[attr-defined]
    assert display_gain_state().gain == 16.0
    qtbot.keyClick(presentation_target, Qt.Key.Key_Plus)  # type: ignore[attr-defined]
    assert gain.currentData() == 16.0

    for _ in range(2):
        qtbot.keyClick(presentation_target, Qt.Key.Key_Minus)  # type: ignore[attr-defined]
    qtbot.waitUntil(lambda: gain.currentData() == 4.0)  # type: ignore[attr-defined]

    group = window.document_list.topLevelItem(0)
    assert group is not None
    assert group.isExpanded()
    window.document_list.setCurrentItem(group)
    window.document_list.setFocus()
    qtbot.waitUntil(lambda: window.document_list.hasFocus())  # type: ignore[attr-defined]

    qtbot.keyClick(window.document_list, Qt.Key.Key_Minus)  # type: ignore[attr-defined]
    assert not group.isExpanded()
    assert gain.currentData() == 4.0
    assert display_gain_state().gain == 4.0

    qtbot.keyClick(window.document_list, Qt.Key.Key_Plus)  # type: ignore[attr-defined]
    assert group.isExpanded()
    assert gain.currentData() == 4.0
    assert display_gain_state().gain == 4.0

    presentation_target.setFocus()
    qtbot.waitUntil(lambda: presentation_target.hasFocus())  # type: ignore[attr-defined]
    for _ in range(10):
        qtbot.keyClick(presentation_target, Qt.Key.Key_Minus)  # type: ignore[attr-defined]
    qtbot.waitUntil(lambda: gain.currentData() == 1.0)  # type: ignore[attr-defined]
    assert display_gain_state().gain == 1.0
    qtbot.keyClick(presentation_target, Qt.Key.Key_Minus)  # type: ignore[attr-defined]
    assert gain.currentData() == 1.0

    destroyed: list[bool] = []
    window.destroyed.connect(lambda *_args: destroyed.append(True))
    window.close()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QCoreApplication.processEvents()
    qtbot.waitUntil(lambda: bool(destroyed))  # type: ignore[attr-defined]
    assert destroyed == [True]

    second_window, second_gain = _compose_production_window()
    qtbot.addWidget(second_window)  # type: ignore[attr-defined]
    second_document = _ready_documents(tmp_path / "second-window", 1)[0]
    _select_documents(second_window, [second_document])
    second_window.set_layout_mode("Single View")
    second_window.show()
    qtbot.waitUntil(lambda: second_window.viewer.document is second_document)  # type: ignore[attr-defined]
    second_target = second_window.viewer._graphics.viewport()
    second_target.setFocus()
    qtbot.waitUntil(lambda: second_target.hasFocus())  # type: ignore[attr-defined]
    qtbot.keyClick(second_target, Qt.Key.Key_Plus)  # type: ignore[attr-defined]
    qtbot.waitUntil(lambda: second_gain.currentData() == 2.0)  # type: ignore[attr-defined]
    assert display_gain_state().gain == 2.0

    second_window.close()
    display_gain_state().reset()


def test_fifty_selected_documents_keep_decode_and_protection_page_bounded(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    QSettings().clear()
    documents = _pending_documents(tmp_path, 50)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    requested: list[str] = []
    monkeypatch.setattr(
        window,
        "_ensure_loaded",
        lambda document: requested.append(document.document_id),
    )

    _select_documents(window, documents)

    selected_ids = [document.document_id for document in documents]
    assert [document.document_id for document in window.selected_documents] == selected_ids
    assert [document.document_id for document in window.current_comparison_documents()] == (
        selected_ids[:COMPARISON_PAGE_SIZE]
    )
    assert requested == selected_ids[:COMPARISON_PAGE_SIZE]
    assert window.comparison_page_label.text() == "1 / 9"
    assert window.comparison_page_range_label.text() == "1–6 of 50"
    protected = window._residency_protected_document_ids()
    assert set(selected_ids[:COMPARISON_PAGE_SIZE]).issubset(protected)
    assert not set(selected_ids[COMPARISON_PAGE_SIZE:]).intersection(protected)
    assert window.preload_controller.current_plan is None

    requested.clear()
    window.next_comparison_page()
    assert requested == selected_ids[6:12]
    assert [document.document_id for document in window.selected_documents] == selected_ids
    assert window.preload_controller.current_plan is None

    for _ in range(7):
        window.next_comparison_page()

    assert window._page_start == 48
    assert [document.document_id for document in window.current_comparison_documents()] == (
        selected_ids[48:50]
    )
    assert window.comparison_page_label.text() == "9 / 9"
    assert window.comparison_page_range_label.text() == "49–50 of 50"
    assert window.multi_compare_view.capacity == COMPARISON_PAGE_SIZE
    assert [viewer.document for viewer in window.multi_compare_view.visible_viewers[2:]] == [
        None,
        None,
        None,
        None,
    ]
    assert [document.document_id for document in window.selected_documents] == selected_ids
    window.close()


def test_display_gain_change_does_not_reissue_numerical_analysis_requests(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    QSettings().clear()
    display_gain_state().reset()
    documents = _ready_documents(tmp_path, 2)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    gain = install_display_gain_control(window)
    polish_presentation_controls(window)
    _select_documents(window, documents)
    window.show()

    statistics_requests: list[object] = []
    difference_requests: list[object] = []
    line_requests: list[object] = []
    monkeypatch.setattr(
        window.comparison_analysis_panel,
        "set_documents",
        lambda *args, **kwargs: statistics_requests.append((args, kwargs)),
    )
    monkeypatch.setattr(
        window.difference_panel,
        "set_documents",
        lambda *args, **kwargs: difference_requests.append((args, kwargs)),
    )
    monkeypatch.setattr(
        window.line_profile_panel,
        "set_documents",
        lambda *args, **kwargs: line_requests.append((args, kwargs)),
    )
    native_sources = [
        document.source.copy() for document in documents if document.source is not None
    ]
    generations = [document.generation for document in documents]
    resident_bytes = window.residency_manager.used_bytes

    gain.setCurrentIndex(gain.findData(4.0))
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: all(
            viewer._displayed_gain == 4.0 and viewer._display_preview_worker is None
            for viewer in window.multi_compare_view.occupied_viewers
        )
    )

    assert statistics_requests == []
    assert difference_requests == []
    assert line_requests == []
    assert [document.generation for document in documents] == generations
    assert window.residency_manager.used_bytes == resident_bytes
    for document, native in zip(documents, native_sources, strict=True):
        assert document.source is not None
        assert np.array_equal(document.source, native)

    window.close()
    display_gain_state().reset()
