from __future__ import annotations

import ctypes
import sys

import pytest

from pixelscope.app.main_window import MainWindow
from pixelscope.ui.beta_workspace_hardening import install_beta_workspace_hardening

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows native frame contract")
def test_floating_plots_keep_dock_topology_with_min_max_close_frame(qtbot: object) -> None:
    from ctypes import wintypes

    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    install_beta_workspace_hardening(window)
    window.show()
    window._set_plots_visible(True)
    dock = window.bottom_dock
    qtbot.waitUntil(dock.isVisible)  # type: ignore[attr-defined]

    dock.setFloating(True)
    qtbot.waitUntil(dock.isFloating)  # type: ignore[attr-defined]
    qtbot.waitUntil(lambda: dock.titleBarWidget() is None)  # type: ignore[attr-defined]

    user32 = ctypes.windll.user32
    get_window_long = user32.GetWindowLongPtrW
    get_window_long.argtypes = [wintypes.HWND, ctypes.c_int]
    get_window_long.restype = ctypes.c_ssize_t
    hwnd = wintypes.HWND(int(dock.winId()))

    gwl_style = -16
    gwl_exstyle = -20
    ws_sysmenu = 0x00080000
    ws_minimizebox = 0x00020000
    ws_maximizebox = 0x00010000
    ws_ex_toolwindow = 0x00000080
    ws_ex_appwindow = 0x00040000

    def regular_workspace_frame_is_active() -> bool:
        style = int(get_window_long(hwnd, gwl_style))
        ex_style = int(get_window_long(hwnd, gwl_exstyle))
        return bool(
            style & ws_sysmenu
            and style & ws_minimizebox
            and style & ws_maximizebox
            and not ex_style & ws_ex_toolwindow
            and ex_style & ws_ex_appwindow
        )

    qtbot.waitUntil(regular_workspace_frame_is_active)  # type: ignore[attr-defined]
    assert dock.isFloating()

    dock.setFloating(False)
    qtbot.waitUntil(lambda: not dock.isFloating())  # type: ignore[attr-defined]
    window.close()
