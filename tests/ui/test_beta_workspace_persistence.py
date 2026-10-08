from __future__ import annotations

import pytest

from pixelscope.app.main_window import MainWindow
from pixelscope.ui.beta_workspace_hardening import install_beta_workspace_hardening
from pixelscope.ui.plots_dock_title import PlotsDockTitleBar

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _show_plots(window: MainWindow) -> object:
    window._set_plots_visible(True)
    return window.bottom_dock


def test_hidden_floating_plots_survives_restart_and_late_hardening(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.show()

    dock = _show_plots(window)
    qtbot.waitUntil(dock.isVisible)  # type: ignore[attr-defined]
    dock.setFloating(True)
    qtbot.waitUntil(dock.isFloating)  # type: ignore[attr-defined]
    dock.hide()
    qtbot.waitUntil(dock.isHidden)  # type: ignore[attr-defined]
    window.close()

    assert not dock.isFloating()
    assert dock.isHidden()

    restored = MainWindow()
    qtbot.addWidget(restored)  # type: ignore[attr-defined]
    restored_dock = restored.bottom_dock

    assert restored_dock.isFloating()
    assert restored_dock.isHidden()

    install_beta_workspace_hardening(restored)
    qtbot.wait(20)  # type: ignore[attr-defined]

    assert restored_dock.isFloating()
    assert restored_dock.isHidden()
    assert not restored.plots_action.isChecked()

    restored.show()
    qtbot.wait(20)  # type: ignore[attr-defined]
    assert restored_dock.isHidden()
    assert not restored.plots_action.isChecked()

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


@pytest.mark.parametrize("floating_state", ["visible", "hidden", "maximized", "restored"])
def test_shutdown_normalizes_plots_after_persisting_floating_state(
    qtbot: object,
    floating_state: str,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    install_beta_workspace_hardening(window)
    window.show()

    dock = _show_plots(window)
    qtbot.waitUntil(dock.isVisible)  # type: ignore[attr-defined]
    dock.setFloating(True)
    qtbot.waitUntil(dock.isFloating)  # type: ignore[attr-defined]
    if floating_state == "hidden":
        dock.hide()
        qtbot.waitUntil(dock.isHidden)  # type: ignore[attr-defined]
    elif floating_state == "maximized":
        dock.showMaximized()
        qtbot.waitUntil(dock.isMaximized)  # type: ignore[attr-defined]
    elif floating_state == "restored":
        dock.showMaximized()
        qtbot.waitUntil(dock.isMaximized)  # type: ignore[attr-defined]
        dock.showNormal()
        qtbot.waitUntil(lambda: not dock.isMaximized())  # type: ignore[attr-defined]

    expected_visible = floating_state != "hidden"
    window.close()

    assert dock.isHidden()
    assert not dock.isFloating()
    assert not dock.isMaximized()

    restored = MainWindow()
    qtbot.addWidget(restored)  # type: ignore[attr-defined]
    assert restored.bottom_dock.isFloating()
    assert restored.bottom_dock.isHidden() is not expected_visible
    restored.close()
