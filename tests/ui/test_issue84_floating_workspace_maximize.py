from __future__ import annotations

import pytest
from PySide6.QtCore import QByteArray, QRect, QSettings, Qt
from PySide6.QtWidgets import QDockWidget

from pixelscope.app.main_window import MainWindow
from pixelscope.ui.beta_workspace_hardening import (
    BetaWorkspaceHardeningController,
    install_beta_workspace_hardening,
)
from pixelscope.ui.plots_dock_title import (
    IQA_FLOATING_GEOMETRY_SETTING,
    PLOTS_FLOATING_GEOMETRY_SETTING,
    PlotsDockTitleBar,
)

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _show_workspace(window: MainWindow, workspace: str) -> QDockWidget:
    if workspace == "plots":
        window._set_plots_visible(True)
        return window.bottom_dock
    window.iqa_workspace_action.trigger()
    return window.iqa_dock


def _prepare_floating_workspace(
    window: MainWindow,
    workspace: str,
    qtbot: object,
) -> tuple[QDockWidget, PlotsDockTitleBar]:
    dock = _show_workspace(window, workspace)
    qtbot.waitUntil(dock.isVisible)  # type: ignore[attr-defined]
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: isinstance(dock.titleBarWidget(), PlotsDockTitleBar)
    )
    dock.setFloating(True)
    qtbot.waitUntil(dock.isFloating)  # type: ignore[attr-defined]
    title = PlotsDockTitleBar.controller_for_dock(dock)
    assert isinstance(title, PlotsDockTitleBar)
    qtbot.waitUntil(lambda: not title._restoring_floating_geometry)  # type: ignore[attr-defined]
    return dock, title


def _setting_geometry(setting: str) -> QByteArray:
    value = QSettings().value(setting)
    return QByteArray(value) if isinstance(value, QByteArray | bytes) else QByteArray()


def _normal_test_geometry(available: QRect) -> QRect:
    width = max(1, available.width() * 2 // 3)
    height = max(1, available.height() * 2 // 3)
    return QRect(
        available.x() + (available.width() - width) // 2,
        available.y() + (available.height() - height) // 2,
        width,
        height,
    )


@pytest.mark.parametrize(
    ("workspace", "setting"),
    [
        ("plots", PLOTS_FLOATING_GEOMETRY_SETTING),
        ("iqa", IQA_FLOATING_GEOMETRY_SETTING),
    ],
)
def test_custom_maximize_restore_preserves_normal_geometry_and_exit_paths(
    qtbot: object,
    workspace: str,
    setting: str,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    install_beta_workspace_hardening(window)
    window.show()
    dock, title = _prepare_floating_workspace(window, workspace, qtbot)

    available = title._available_screen_geometry()
    assert isinstance(available, QRect)
    normal_geometry = _normal_test_geometry(available)
    dock.setGeometry(normal_geometry)
    qtbot.waitUntil(lambda: dock.geometry() == normal_geometry)  # type: ignore[attr-defined]
    title._remember_floating_geometry()
    normal_state = QByteArray(title._floating_geometry)
    assert not normal_state.isEmpty()
    assert _setting_geometry(setting) == normal_state

    for _ in range(3):
        title.maximize_button.click()
        qtbot.waitUntil(lambda: title._workspace_maximized)  # type: ignore[attr-defined]
        assert dock.isFloating()
        assert not dock.isMaximized()
        assert dock.geometry() == available
        assert title.maximize_button.toolTip().startswith("Restore ")
        assert QByteArray(title._floating_geometry) == normal_state
        assert _setting_geometry(setting) == normal_state

        title.maximize_button.click()
        qtbot.waitUntil(  # type: ignore[attr-defined]
            lambda: not title._workspace_maximized and not title._restoring_floating_geometry
        )
        assert dock.isFloating()
        assert not dock.isMaximized()
        assert dock.geometry() == normal_geometry
        assert title.maximize_button.toolTip().startswith("Maximize ")
        assert QByteArray(title._floating_geometry) == normal_state
        assert _setting_geometry(setting) == normal_state

    # The custom Dock action must leave custom-maximized state without entering
    # native WindowMaximized state or corrupting the retained normal geometry.
    title.maximize_button.click()
    qtbot.waitUntil(lambda: title._workspace_maximized)  # type: ignore[attr-defined]
    title.float_button.click()
    qtbot.waitUntil(lambda: not dock.isFloating())  # type: ignore[attr-defined]
    assert not title._workspace_maximized
    assert not dock.isMaximized()
    assert QByteArray(title._floating_geometry) == normal_state

    # Floating-title double-click is the other redock exit path. Keep it covered
    # without sleeps so queued work cannot be hidden by timing slack.
    dock.setFloating(True)
    qtbot.waitUntil(dock.isFloating)  # type: ignore[attr-defined]
    qtbot.waitUntil(lambda: not title._restoring_floating_geometry)  # type: ignore[attr-defined]
    title.maximize_button.click()
    qtbot.waitUntil(lambda: title._workspace_maximized)  # type: ignore[attr-defined]
    qtbot.mouseDClick(title, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
    qtbot.waitUntil(lambda: not dock.isFloating())  # type: ignore[attr-defined]
    assert not title._workspace_maximized
    assert not dock.isMaximized()

    window.close()


@pytest.mark.parametrize("workspace", ["plots", "iqa"])
def test_docked_custom_maximize_restores_original_dock_area(
    qtbot: object,
    workspace: str,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    install_beta_workspace_hardening(window)
    window.show()

    dock = _show_workspace(window, workspace)
    qtbot.waitUntil(dock.isVisible)  # type: ignore[attr-defined]
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: isinstance(dock.titleBarWidget(), PlotsDockTitleBar)
    )
    title = PlotsDockTitleBar.controller_for_dock(dock)
    assert isinstance(title, PlotsDockTitleBar)
    original_area = window.dockWidgetArea(dock)
    assert original_area != Qt.DockWidgetArea.NoDockWidgetArea
    available = title._available_screen_geometry()
    assert isinstance(available, QRect)

    title.maximize_button.click()
    qtbot.waitUntil(lambda: title._workspace_maximized and dock.isFloating())  # type: ignore[attr-defined]
    assert not dock.isMaximized()
    assert dock.geometry() == available
    assert title.maximize_button.toolTip().startswith("Restore ")

    title.maximize_button.click()
    qtbot.waitUntil(lambda: not dock.isFloating())  # type: ignore[attr-defined]
    assert not title._workspace_maximized
    assert not dock.isMaximized()
    assert window.dockWidgetArea(dock) == original_area
    assert title.maximize_button.toolTip().startswith("Maximize ")

    window.close()


def test_workspace_window_ownership_and_shutdown_quiesce_remain_bounded(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    hardening = install_beta_workspace_hardening(window)
    assert isinstance(hardening, BetaWorkspaceHardeningController)
    assert hardening.parent() is window
    window.show()

    managed: list[tuple[QDockWidget, PlotsDockTitleBar]] = []
    for workspace in ("plots", "iqa"):
        dock, title = _prepare_floating_workspace(window, workspace, qtbot)
        assert title.parentWidget() is dock
        assert title._geometry_restore_timer.parent() is title
        title.maximize_button.click()
        qtbot.waitUntil(lambda title=title: title._workspace_maximized)  # type: ignore[attr-defined]
        managed.append((dock, title))

    # The hardening controllers and their timers are also parent-bounded. Starting
    # the timers here makes closeEvent's quiesce contract observable without a
    # fixed sleep or manual event-loop drain inside the test.
    assert len(hardening._dock_controllers) == 2
    for controller in hardening._dock_controllers:
        assert controller.parent() in (window.bottom_dock, window.iqa_dock)
        assert controller._normalize_timer.parent() is controller
        assert controller._detach_timer.parent() is controller
        controller._normalize_timer.start(60_000)
        controller._detach_timer.start(60_000)
        assert controller._normalize_timer.isActive()
        assert controller._detach_timer.isActive()

    for _dock, title in managed:
        title._geometry_restore_timer.start(60_000)
        assert title._geometry_restore_timer.isActive()

    window.close()

    for dock, title in managed:
        assert title._quiescing
        assert not title._geometry_restore_timer.isActive()
        assert not title._workspace_maximized
        assert dock.isHidden()
        assert not dock.isFloating()
        assert not dock.isMaximized()

    for controller in hardening._dock_controllers:
        assert controller._quiescing
        assert not controller._normalize_timer.isActive()
        assert not controller._detach_timer.isActive()
