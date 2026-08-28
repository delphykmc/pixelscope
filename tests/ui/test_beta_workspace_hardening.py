from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSizePolicy

from pixelscope.app.main_window import MainWindow
from pixelscope.ui.beta_workspace_hardening import (
    install_beta_workspace_hardening,
    tile_header_compact_for_width,
)
from pixelscope.ui.plots_dock_title import PlotsDockTitleBar

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def test_tile_header_compact_mode_uses_resize_hysteresis() -> None:
    assert tile_header_compact_for_width(compact=False, width=479)
    assert not tile_header_compact_for_width(compact=False, width=480)

    assert tile_header_compact_for_width(compact=True, width=480)
    assert tile_header_compact_for_width(compact=True, width=511)
    assert not tile_header_compact_for_width(compact=True, width=512)


def test_beta_layout_policy_removes_accumulated_workspace_floors(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    sidebar = window.main_splitter.widget(0)
    assert sidebar.minimumWidth() == 320
    assert window.iqa_workspace.attribute_filter.minimumWidth() == 150

    install_beta_workspace_hardening(window)

    assert sidebar.minimumWidth() == 0
    assert window.iqa_workspace.attribute_filter.minimumWidth() == 0
    assert (
        window.iqa_workspace.sizePolicy().horizontalPolicy()
        == QSizePolicy.Policy.Ignored
    )
    assert window.iqa_workspace.status_label.wordWrap()
    assert window.iqa_workspace.result_label.wordWrap()
    assert window.iqa_workspace.dataset_label.wordWrap()
    assert window.iqa_workspace.preview_caption.wordWrap()

    assert (
        window.main_splitter.sizePolicy().verticalPolicy()
        == QSizePolicy.Policy.Ignored
    )
    assert (
        window.bottom_tabs.sizePolicy().verticalPolicy()
        == QSizePolicy.Policy.Expanding
    )
    assert window.bottom_tabs.minimumHeight() == 0

    window.close()


def test_iqa_toolbar_reuses_existing_visibility_action(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    controller = install_beta_workspace_hardening(window)
    assert install_beta_workspace_hardening(window) is controller

    toolbar_actions = window.main_toolbar.actions()
    assert toolbar_actions.count(window.iqa_workspace_action) == 1
    assert toolbar_actions.index(window.iqa_workspace_action) < toolbar_actions.index(
        window.plots_action
    )
    assert window.iqa_workspace_action.iconText() == "IQA"
    assert window.iqa_workspace_action.isCheckable()

    window.show()
    window.iqa_workspace_action.trigger()
    qtbot.waitUntil(window.iqa_dock.isVisible)  # type: ignore[attr-defined]
    assert window.iqa_workspace_action.isChecked()

    window.iqa_dock.close()
    qtbot.waitUntil(lambda: not window.iqa_dock.isVisible())  # type: ignore[attr-defined]
    assert not window.iqa_workspace_action.isChecked()

    window.close()


def _assert_regular_top_level_window(dock: object) -> None:
    flags = dock.windowFlags()
    assert (flags & Qt.WindowType.WindowType_Mask) == Qt.WindowType.Window
    assert not (flags & Qt.WindowType.Tool)
    assert not (flags & Qt.WindowType.FramelessWindowHint)
    assert not (flags & Qt.WindowType.WindowStaysOnTopHint)
    assert flags & Qt.WindowType.WindowTitleHint
    assert flags & Qt.WindowType.WindowMinimizeButtonHint
    assert flags & Qt.WindowType.WindowMaximizeButtonHint


def test_floating_plots_use_native_top_level_chrome_and_redock(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    install_beta_workspace_hardening(window)
    original_title = window.bottom_dock.titleBarWidget()
    assert isinstance(original_title, PlotsDockTitleBar)

    window.show()
    window._set_plots_visible(True)
    window.bottom_dock.setFloating(True)
    qtbot.waitUntil(window.bottom_dock.isFloating)  # type: ignore[attr-defined]
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.bottom_dock.titleBarWidget() is None
    )

    _assert_regular_top_level_window(window.bottom_dock)
    handle = window.bottom_dock.windowHandle()
    if handle is not None:
        qtbot.waitUntil(lambda: handle.transientParent() is None)  # type: ignore[attr-defined]

    window.bottom_dock.setFloating(False)
    qtbot.waitUntil(lambda: not window.bottom_dock.isFloating())  # type: ignore[attr-defined]
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.bottom_dock.titleBarWidget() is original_title
    )
    assert (
        window.dockWidgetArea(window.bottom_dock)
        == Qt.DockWidgetArea.BottomDockWidgetArea
    )

    window.close()


def test_floating_iqa_uses_native_top_level_chrome_and_redock(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    install_beta_workspace_hardening(window)
    window.show()

    window.iqa_workspace_action.trigger()
    qtbot.waitUntil(window.iqa_dock.isVisible)  # type: ignore[attr-defined]
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: isinstance(window.iqa_dock.titleBarWidget(), PlotsDockTitleBar)
    )
    original_title = window.iqa_dock.titleBarWidget()

    window.iqa_dock.setFloating(True)
    qtbot.waitUntil(window.iqa_dock.isFloating)  # type: ignore[attr-defined]
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.iqa_dock.titleBarWidget() is None
    )
    _assert_regular_top_level_window(window.iqa_dock)

    window.iqa_dock.showMaximized()
    qtbot.waitUntil(window.iqa_dock.isMaximized)  # type: ignore[attr-defined]
    window.iqa_dock.showNormal()
    qtbot.waitUntil(lambda: not window.iqa_dock.isMaximized())  # type: ignore[attr-defined]

    window.iqa_dock.setFloating(False)
    qtbot.waitUntil(lambda: not window.iqa_dock.isFloating())  # type: ignore[attr-defined]
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.iqa_dock.titleBarWidget() is original_title
    )
    assert window.iqa_workspace_action.isChecked()

    window.iqa_dock.hide()
    assert not window.iqa_workspace_action.isChecked()
    window.close()
