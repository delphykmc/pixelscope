from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import QSettings

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow


@pytest.fixture(autouse=True)
def isolated_ui_settings(tmp_path: Path) -> None:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str(tmp_path / "settings"),
    )
    QSettings().clear()


def test_file_menu_groups_direct_opens_before_matching_recent_menus(qtbot: Any) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    _compose_main_window_presentation(window)

    file_menu = window.historical_iqa_results_controller.file_menu
    open_group: list[str] = []
    for action in file_menu.actions():
        if action.isSeparator():
            break
        open_group.append(action.text().replace("&", ""))

    assert open_group == [
        "Open Images...",
        "Open Folder...",
        "Open Session...",
        "Open IQA Result...",
        "Open Recent Images",
        "Open Recent Folders",
        "Open Recent Sessions",
        "Open Recent IQA Results",
    ]
    window.close()
