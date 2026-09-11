from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QMenu

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _window(qtbot: object) -> MainWindow:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    return window


def _add_folder(
    window: MainWindow,
    folder: Path,
    count: int = 3,
) -> list[ImageDocument]:
    documents = [
        ImageDocument.from_array(
            np.full((4, 5), index, dtype=np.uint8),
            f"frame-{index}.png",
            source_path=folder / f"frame-{index}.png",
        )
        for index in range(count)
    ]
    for document in documents:
        window.add_document(document, select=False)
    return documents


def _selected_ids(window: MainWindow) -> list[str]:
    return [document.document_id for document in window.selected_documents]


def _same_position_menu(window: MainWindow, document_id: str) -> tuple[QMenu, QMenu]:
    item = window.document_list.document_item(document_id)
    assert item is not None
    menu = window.workflow_files_context_menu.build_menu_for_item(item)
    action = next(
        candidate
        for candidate in menu.actions()
        if candidate.text() == "Compare same position with..."
    )
    submenu = action.menu()
    assert submenu is not None
    return menu, submenu


def test_image_context_menu_adds_chosen_same_ordinal_without_difference(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window = _window(qtbot)
    folders = [tmp_path / name for name in ("reference", "candidate", "alternate")]
    by_folder = [_add_folder(window, folder) for folder in folders]
    anchor = by_folder[0][1]
    window._select_document_ids([anchor.document_id])

    _menu, submenu = _same_position_menu(window, anchor.document_id)
    actions = submenu.actions()
    assert [action.text() for action in actions] == [
        "candidate",
        "alternate",
    ]
    assert all("position 2" in action.toolTip() for action in actions)

    actions[1].trigger()

    assert _selected_ids(window) == [anchor.document_id, by_folder[2][1].document_id]
    assert not window.diff_action.isChecked()
    assert window._difference_document is None
    assert "Added alternate at position 2" in window.statusBar().currentMessage()

    folder_item = window.document_list.topLevelItem(0)
    folder_menu = window.workflow_files_context_menu.build_menu_for_item(folder_item)
    assert not any(
        action.text() == "Compare same position with..." for action in folder_menu.actions()
    )
    window.close()


def test_context_menu_requires_selected_anchor_and_omits_selected_or_short_folders(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window = _window(qtbot)
    first = _add_folder(window, tmp_path / "first")
    short = _add_folder(window, tmp_path / "short", count=1)
    third = _add_folder(window, tmp_path / "third")
    window._select_document_ids([first[2].document_id])

    _unselected_parent, unselected_menu = _same_position_menu(window, third[2].document_id)
    assert not unselected_menu.isEnabled()

    _anchor_parent, anchor_menu = _same_position_menu(window, first[2].document_id)
    assert [action.text() for action in anchor_menu.actions()] == ["third"]
    assert all(short_document.document_id not in _selected_ids(window) for short_document in short)

    anchor_menu.actions()[0].trigger()
    _updated_parent, updated_menu = _same_position_menu(window, first[2].document_id)
    assert not updated_menu.isEnabled()
    window.close()


def test_context_targets_disambiguate_duplicate_folder_names(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window = _window(qtbot)
    anchor = _add_folder(window, tmp_path / "reference")[0]
    first_target = tmp_path / "left" / "scene"
    second_target = tmp_path / "right" / "scene"
    _add_folder(window, first_target)
    _add_folder(window, second_target)
    window._select_document_ids([anchor.document_id])

    _parent, submenu = _same_position_menu(window, anchor.document_id)

    assert [action.text() for action in submenu.actions()] == [
        f"scene — {first_target.parent}",
        f"scene — {second_target.parent}",
    ]
    window.close()


def test_alt_shortcuts_skip_ineligible_folders_then_plain_pagedown_moves_group(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window = _window(qtbot)
    first = _add_folder(window, tmp_path / "a")
    _add_folder(window, tmp_path / "b-short", count=1)
    third = _add_folder(window, tmp_path / "c")
    fourth = _add_folder(window, tmp_path / "d")
    window._select_document_ids([first[1].document_id])
    window.show()
    window.activateWindow()
    QApplication.setActiveWindow(window)
    window.viewer.setFocus()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: QApplication.activeWindow() is window,
        timeout=3000,
    )

    qtbot.keyClick(  # type: ignore[attr-defined]
        window.viewer,
        Qt.Key.Key_PageDown,
        Qt.KeyboardModifier.AltModifier,
    )
    assert _selected_ids(window) == [first[1].document_id, third[1].document_id]

    qtbot.keyClick(  # type: ignore[attr-defined]
        window.viewer,
        Qt.Key.Key_PageDown,
        Qt.KeyboardModifier.AltModifier,
    )
    assert _selected_ids(window) == [
        first[1].document_id,
        third[1].document_id,
        fourth[1].document_id,
    ]

    qtbot.keyClick(window.viewer, Qt.Key.Key_PageDown)  # type: ignore[attr-defined]
    assert _selected_ids(window) == [
        first[2].document_id,
        third[2].document_id,
        fourth[2].document_id,
    ]
    qtbot.keyClick(window.viewer, Qt.Key.Key_PageUp)  # type: ignore[attr-defined]
    assert _selected_ids(window) == [
        first[1].document_id,
        third[1].document_id,
        fourth[1].document_id,
    ]
    window.close()


def test_alt_pageup_uses_active_anchor_and_addition_preserves_primary(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window = _window(qtbot)
    first = _add_folder(window, tmp_path / "a")
    second = _add_folder(window, tmp_path / "b")
    third = _add_folder(window, tmp_path / "c")
    window._select_document_ids([third[1].document_id])
    window._set_focus_document(third[1])
    window.show()
    window.activateWindow()
    QApplication.setActiveWindow(window)
    window.viewer.setFocus()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: QApplication.activeWindow() is window,
        timeout=3000,
    )

    qtbot.keyClick(  # type: ignore[attr-defined]
        window.viewer,
        Qt.Key.Key_PageUp,
        Qt.KeyboardModifier.AltModifier,
    )

    assert _selected_ids(window) == [third[1].document_id, second[1].document_id]
    assert window._focus_document_id == third[1].document_id
    assert window._primary_document_for_page(window.current_comparison_documents()) is third[1]
    assert first[1].document_id not in _selected_ids(window)
    window.close()


@pytest.mark.parametrize("focus_surface", ("files", "viewer", "statistics"))
def test_alt_bootstrap_is_application_wide(
    qtbot: object,
    tmp_path: Path,
    focus_surface: str,
) -> None:
    window = _window(qtbot)
    first = _add_folder(window, tmp_path / "first")
    second = _add_folder(window, tmp_path / "second")
    window._select_document_ids([first[0].document_id])
    focus_widget = {
        "files": window.document_list,
        "viewer": window.viewer,
        "statistics": window.comparison_analysis_panel.region_scope,
    }[focus_surface]
    window.show()
    window.activateWindow()
    QApplication.setActiveWindow(window)
    focus_widget.setFocus()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: QApplication.activeWindow() is window and focus_widget.hasFocus(),
        timeout=3000,
    )

    qtbot.keyClick(  # type: ignore[attr-defined]
        focus_widget,
        Qt.Key.Key_PageDown,
        Qt.KeyboardModifier.AltModifier,
    )

    assert _selected_ids(window) == [first[0].document_id, second[0].document_id]
    window.close()


def test_bootstrap_capacity_and_invalid_group_are_safe_noops(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window = _window(qtbot)
    by_folder = [_add_folder(window, tmp_path / f"folder-{index}") for index in range(7)]
    selected = [documents[1].document_id for documents in by_folder[:6]]
    window._select_document_ids(selected)

    window.add_next_folder_at_same_position()
    assert _selected_ids(window) == selected
    assert "requires 1–5 selected images" in window.statusBar().currentMessage()

    duplicate_folder_ids = [by_folder[0][0].document_id, by_folder[0][1].document_id]
    window._select_document_ids(duplicate_folder_ids)
    window.add_next_folder_at_same_position()
    assert _selected_ids(window) == duplicate_folder_ids
    assert "requires 1–5 selected images" in window.statusBar().currentMessage()
    window.close()


def test_alt_shortcuts_are_distinct_from_plain_folder_position_bindings(
    qtbot: object,
) -> None:
    window = _window(qtbot)
    keys = {shortcut.key() for shortcut in window._selection_shortcuts}

    assert QKeySequence(Qt.Key.Key_PageUp) in keys
    assert QKeySequence(Qt.Key.Key_PageDown) in keys
    assert QKeySequence("Alt+PgUp") in keys
    assert QKeySequence("Alt+PgDown") in keys
    window.close()
