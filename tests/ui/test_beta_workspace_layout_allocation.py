from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSizePolicy

from pixelscope.ui.beta_workspace_hardening import install_beta_workspace_hardening
from pixelscope.app.main_window import MainWindow

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def test_bottom_plots_owns_both_lower_corners(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    install_beta_workspace_hardening(window)

    assert window.corner(Qt.Corner.BottomLeftCorner) == Qt.DockWidgetArea.BottomDockWidgetArea
    assert window.corner(Qt.Corner.BottomRightCorner) == Qt.DockWidgetArea.BottomDockWidgetArea
    assert window.bottom_tabs.minimumHeight() == 0
    assert window.bottom_tabs.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Expanding

    window.close()

def test_horizontal_workspace_uses_qt_native_collapse_policy(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    controller = install_beta_workspace_hardening(window)

    # No custom resize/allocation controller: QSplitter owns Files/Image and
    # QMainWindow/QDockWidget owns the Base Plots workspace.
    assert not hasattr(controller, "_horizontal_allocation_controller")

    # Files is secondary and may collapse; Image is the primary workspace and
    # stays non-collapsible even when the splitter is dragged to an extreme.
    assert window.main_splitter.isCollapsible(0)
    assert not window.main_splitter.isCollapsible(1)
    assert window.main_splitter.widget(0).minimumWidth() == 0
    assert window.presentation_panel.minimumWidth() == 0

    window.close()
