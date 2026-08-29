from __future__ import annotations

import pytest

from pixelscope.app.main_window import MainWindow
from pixelscope.ui.beta_workspace_hardening import install_beta_workspace_hardening
from pixelscope.ui.plots_dock_title import PlotsDockTitleBar

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _show_workspace(window: MainWindow, workspace: str) -> object:
    if workspace == "plots":
        window._set_plots_visible(True)
        return window.bottom_dock
    window.iqa_workspace_action.trigger()
    return window.iqa_dock


@pytest.mark.parametrize("workspace", ["plots", "iqa"])
def test_hidden_floating_workspace_survives_restart_and_late_hardening(
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
    window._save_ui_state()
    window.close()

    restored = MainWindow()
    qtbot.addWidget(restored)  # type: ignore[attr-defined]
    restored_dock = restored.bottom_dock if workspace == "plots" else restored.iqa_dock

    assert restored_dock.isFloating()
    assert restored_dock.isHidden()

    install_beta_workspace_hardening(restored)
    qtbot.wait(20)  # type: ignore[attr-defined]

    assert restored_dock.isFloating()
    assert restored_dock.isHidden()
    action = restored.plots_action if workspace == "plots" else restored.iqa_workspace_action
    assert not action.isChecked()

    restored.show()
    qtbot.wait(20)  # type: ignore[attr-defined]
    assert restored_dock.isHidden()
    assert not action.isChecked()

    restored_dock.show()
    qtbot.waitUntil(restored_dock.isVisible)  # type: ignore[attr-defined]
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: isinstance(restored_dock.titleBarWidget(), PlotsDockTitleBar)
    )
    title = restored_dock.titleBarWidget()
    assert isinstance(title, PlotsDockTitleBar)
    assert title.float_button.toolTip().startswith("Dock ")
    assert title.maximize_button.isVisible()
    assert title.close_button.isVisible()
    assert not hasattr(title, "minimize_button")
    restored.close()
