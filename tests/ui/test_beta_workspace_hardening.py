from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import QByteArray, QSettings, Qt
from PySide6.QtWidgets import QSizePolicy

from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.ui.beta_workspace_hardening import install_beta_workspace_hardening
from pixelscope.ui.design_tokens import TOKENS
from pixelscope.ui.plots_dock_title import (
    IQA_FLOATING_GEOMETRY_SETTING,
    PLOTS_FLOATING_GEOMETRY_SETTING,
    PlotsDockTitleBar,
)
from pixelscope.ui.tile_header import TileHeader

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def test_tile_header_compact_mode_uses_resize_hysteresis() -> None:
    assert TileHeader.compact_for_width(compact=False, width=479)
    assert not TileHeader.compact_for_width(compact=False, width=480)

    assert TileHeader.compact_for_width(compact=True, width=480)
    assert TileHeader.compact_for_width(compact=True, width=511)
    assert not TileHeader.compact_for_width(compact=True, width=512)


def test_tile_header_document_refresh_preserves_hysteresis_band(qtbot: object) -> None:
    header = TileHeader()
    qtbot.addWidget(header)  # type: ignore[attr-defined]
    header.show()
    header.resize(470, header.height())
    qtbot.waitUntil(lambda: header.compact)  # type: ignore[attr-defined]

    header.resize(500, header.height())
    qtbot.waitUntil(lambda: header.width() == 500)  # type: ignore[attr-defined]
    assert header.compact

    document = ImageDocument.from_array(
        np.zeros((8, 8), dtype=np.uint8),
        "refresh.png",
    )
    header.set_document(document)
    assert header.compact

    header.resize(TileHeader.COMPACT_EXIT_WIDTH, header.height())
    qtbot.waitUntil(lambda: not header.compact)  # type: ignore[attr-defined]
    header.close()


def test_beta_layout_policy_removes_accumulated_workspace_floors(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    sidebar = window.main_splitter.widget(0)
    assert sidebar.minimumWidth() == 320
    assert window.iqa_workspace.attribute_filter.minimumWidth() == 150
    assert window.iqa_workspace.attribute_filter.maximumWidth() == 230

    install_beta_workspace_hardening(window)

    assert sidebar.minimumWidth() == 0
    assert window.main_splitter.isCollapsible(0)
    assert not window.main_splitter.isCollapsible(1)
    assert window.iqa_workspace.attribute_filter.minimumWidth() == 0
    assert window.iqa_workspace.attribute_filter.maximumWidth() == window.maximumWidth()
    assert (
        window.iqa_workspace.sizePolicy().horizontalPolicy()
        == QSizePolicy.Policy.Ignored
    )
    assert (
        window.iqa_workspace.sizePolicy().verticalPolicy()
        == QSizePolicy.Policy.Ignored
    )
    assert window.iqa_workspace.status_label.wordWrap()
    assert window.iqa_workspace.result_label.wordWrap()
    assert window.iqa_workspace.dataset_label.wordWrap()
    assert window.iqa_workspace.preview_caption.wordWrap()
    assert window.iqa_workspace.overview_plot.minimumHeight() == 0
    assert window.iqa_workspace.scene_trend_plot.minimumHeight() == 0
    assert window.iqa_workspace.hierarchy.minimumHeight() == 0

    assert (
        window.corner(Qt.Corner.BottomLeftCorner)
        == Qt.DockWidgetArea.BottomDockWidgetArea
    )
    assert (
        window.corner(Qt.Corner.BottomRightCorner)
        == Qt.DockWidgetArea.BottomDockWidgetArea
    )
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


def _assert_styled_floating_workspace(dock: object) -> PlotsDockTitleBar:
    assert dock.isFloating()
    assert dock.isWindow()
    title = dock.titleBarWidget()
    assert isinstance(title, PlotsDockTitleBar)
    assert TOKENS.workspace_background in title.styleSheet()
    assert not hasattr(title, "minimize_button")
    assert title.float_button.toolTip().startswith("Dock ")
    return title


def _show_workspace(window: MainWindow, workspace: str) -> object:
    if workspace == "plots":
        window._set_plots_visible(True)
        return window.bottom_dock
    window.iqa_workspace_action.trigger()
    return window.iqa_dock


def _prepare_styled_floating(window: MainWindow, workspace: str, qtbot: object) -> object:
    dock = _show_workspace(window, workspace)
    qtbot.waitUntil(dock.isVisible)  # type: ignore[attr-defined]
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: isinstance(dock.titleBarWidget(), PlotsDockTitleBar)
    )
    dock.setFloating(True)
    qtbot.waitUntil(dock.isFloating)  # type: ignore[attr-defined]
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: isinstance(dock.titleBarWidget(), PlotsDockTitleBar)
    )
    return dock


def _assert_transient_parent_detached(dock: object, qtbot: object) -> None:
    handle = dock.windowHandle()
    if handle is not None:
        qtbot.waitUntil(lambda: handle.transientParent() is None)  # type: ignore[attr-defined]


def test_floating_plots_keep_styled_title_and_redock(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    install_beta_workspace_hardening(window)
    original_title = window.bottom_dock.titleBarWidget()
    assert isinstance(original_title, PlotsDockTitleBar)
    assert not hasattr(original_title, "minimize_button")

    window.show()
    dock = _prepare_styled_floating(window, "plots", qtbot)

    assert _assert_styled_floating_workspace(dock) is original_title
    _assert_transient_parent_detached(dock, qtbot)

    dock.setFloating(False)
    qtbot.waitUntil(lambda: not dock.isFloating())  # type: ignore[attr-defined]
    assert dock.titleBarWidget() is original_title
    assert original_title.float_button.toolTip().startswith("Float ")
    assert window.dockWidgetArea(dock) == Qt.DockWidgetArea.BottomDockWidgetArea

    window.close()


def test_floating_iqa_keeps_styled_title_and_redock(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    install_beta_workspace_hardening(window)
    window.show()

    dock = _show_workspace(window, "iqa")
    qtbot.waitUntil(dock.isVisible)  # type: ignore[attr-defined]
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: isinstance(dock.titleBarWidget(), PlotsDockTitleBar)
    )
    original_title = dock.titleBarWidget()

    dock.setFloating(True)
    qtbot.waitUntil(dock.isFloating)  # type: ignore[attr-defined]
    assert _assert_styled_floating_workspace(dock) is original_title
    _assert_transient_parent_detached(dock, qtbot)

    dock.showMaximized()
    qtbot.waitUntil(dock.isMaximized)  # type: ignore[attr-defined]
    dock.showNormal()
    qtbot.waitUntil(lambda: not dock.isMaximized())  # type: ignore[attr-defined]

    dock.setFloating(False)
    qtbot.waitUntil(lambda: not dock.isFloating())  # type: ignore[attr-defined]
    assert dock.titleBarWidget() is original_title
    assert window.iqa_workspace_action.isChecked()

    dock.hide()
    assert not window.iqa_workspace_action.isChecked()
    window.close()


@pytest.mark.parametrize("workspace", ["plots", "iqa"])
def test_late_install_preserves_hidden_floating_workspace(
    qtbot: object,
    workspace: str,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.show()

    dock = _show_workspace(window, workspace)
    qtbot.waitUntil(dock.isVisible)  # type: ignore[attr-defined]
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: isinstance(dock.titleBarWidget(), PlotsDockTitleBar)
    )
    dock.setFloating(True)
    qtbot.waitUntil(dock.isFloating)  # type: ignore[attr-defined]
    dock.hide()
    qtbot.waitUntil(dock.isHidden)  # type: ignore[attr-defined]

    install_beta_workspace_hardening(window)
    qtbot.wait(20)  # type: ignore[attr-defined]

    assert dock.isFloating()
    assert dock.isHidden()
    action = window.plots_action if workspace == "plots" else window.iqa_workspace_action
    assert not action.isChecked()

    dock.show()
    qtbot.waitUntil(dock.isVisible)  # type: ignore[attr-defined]
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: isinstance(dock.titleBarWidget(), PlotsDockTitleBar)
    )
    _assert_styled_floating_workspace(dock)
    _assert_transient_parent_detached(dock, qtbot)
    window.close()


@pytest.mark.parametrize(
    ("workspace", "setting"),
    [
        ("plots", PLOTS_FLOATING_GEOMETRY_SETTING),
        ("iqa", IQA_FLOATING_GEOMETRY_SETTING),
    ],
)
def test_reset_workspace_clears_retained_floating_geometry(
    qtbot: object,
    workspace: str,
    setting: str,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    install_beta_workspace_hardening(window)
    window.show()
    dock = _prepare_styled_floating(window, workspace, qtbot)

    title = PlotsDockTitleBar.controller_for_dock(dock)
    assert isinstance(title, PlotsDockTitleBar)
    stale_geometry = QByteArray(f"stale-{workspace}".encode())
    title._floating_geometry = QByteArray(stale_geometry)
    QSettings().setValue(setting, stale_geometry)

    window.action_map["Reset Workspace Layout"].trigger()

    assert QSettings().value(setting) is None
    assert title._floating_geometry.isEmpty()
    assert not dock.isFloating()
    assert dock.isHidden()

    dock.setFloating(True)
    qtbot.waitUntil(dock.isFloating)  # type: ignore[attr-defined]
    dock.show()
    qtbot.waitUntil(dock.isVisible)  # type: ignore[attr-defined]
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: isinstance(dock.titleBarWidget(), PlotsDockTitleBar)
    )
    assert title._floating_geometry != stale_geometry
    persisted = QSettings().value(setting)
    if isinstance(persisted, QByteArray | bytes):
        assert QByteArray(persisted) != stale_geometry

    window.close()
