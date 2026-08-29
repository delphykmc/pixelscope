from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSizePolicy, QSplitter, QWidget

from pixelscope.app.main_window import MainWindow
from pixelscope.ui.beta_workspace_hardening import install_beta_workspace_hardening

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def test_bottom_plots_can_take_height_while_iqa_is_docked(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    install_beta_workspace_hardening(window)

    assert (
        window.corner(Qt.Corner.BottomLeftCorner)
        == Qt.DockWidgetArea.BottomDockWidgetArea
    )
    assert (
        window.corner(Qt.Corner.BottomRightCorner)
        == Qt.DockWidgetArea.BottomDockWidgetArea
    )

    workspace = window.iqa_workspace
    assert workspace.minimumHeight() == 0
    assert workspace.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Ignored

    for widget_name in (
        "overview_page",
        "scene_page",
        "overview_chart_panel",
        "overview_detail_panel",
        "overview_plot",
        "hierarchy",
        "scene_trend_plot",
        "preview_scroll",
    ):
        widget = getattr(workspace, widget_name)
        assert isinstance(widget, QWidget)
        assert widget.minimumHeight() == 0
        assert widget.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Ignored

    for splitter_name in ("overview_splitter", "scene_splitter"):
        splitter = getattr(workspace, splitter_name)
        assert isinstance(splitter, QSplitter)
        assert all(splitter.isCollapsible(index) for index in range(splitter.count()))

    window.close()


def test_horizontal_workspace_uses_qt_native_collapse_policy(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    controller = install_beta_workspace_hardening(window)

    # No custom resize/allocation controller: QSplitter owns Files/Image and
    # QMainWindow/QDockWidget owns central-area/IQA sizing.
    assert not hasattr(controller, "_horizontal_allocation_controller")

    # Files is secondary and may collapse; Image is the primary workspace and
    # stays non-collapsible even when the splitter is dragged to an extreme.
    assert window.main_splitter.isCollapsible(0)
    assert not window.main_splitter.isCollapsible(1)
    assert window.main_splitter.widget(0).minimumWidth() == 0
    assert window.presentation_panel.minimumWidth() == 0
    assert window.iqa_dock.minimumWidth() == 0
    assert window.iqa_workspace.attribute_filter.maximumWidth() == window.maximumWidth()

    window.close()
