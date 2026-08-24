from __future__ import annotations

import pytest
from PySide6.QtCore import QByteArray, QRect, QSettings, Qt

from pixelscope.app.main_window import MainWindow
from pixelscope.core.line_profile import LineSelection
from pixelscope.core.roi import RoiBounds
from pixelscope.ui.image_viewer import RoiViewBox
from pixelscope.ui.plots_dock_title import PLOTS_FLOATING_GEOMETRY_SETTING

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _geometry_close(actual: QRect, expected: QRect, tolerance: int = 16) -> bool:
    return all(
        abs(left - right) <= tolerance
        for left, right in zip(
            (actual.x(), actual.y(), actual.width(), actual.height()),
            (expected.x(), expected.y(), expected.width(), expected.height()),
            strict=True,
        )
    )


def test_plots_workspace_fresh_settings_use_docked_hidden_histogram(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert window.bottom_dock.isHidden()
    assert not window.bottom_dock.isFloating()
    assert window.dockWidgetArea(window.bottom_dock) == Qt.DockWidgetArea.BottomDockWidgetArea
    assert window.bottom_tabs.currentIndex() == 0

    window.close()


def test_qsettings_restore_plots_visibility_floating_state_and_selected_tab(
    qtbot: object,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.show()
    window._show_plot_tab(1)
    window.bottom_dock.setFloating(True)
    qtbot.waitUntil(window.bottom_dock.isFloating)  # type: ignore[attr-defined]
    window._save_ui_state()
    window.close()

    restored = MainWindow()
    qtbot.addWidget(restored)  # type: ignore[attr-defined]
    restored.show()
    qtbot.waitUntil(restored.bottom_dock.isFloating)  # type: ignore[attr-defined]

    assert not restored.bottom_dock.isHidden()
    assert restored.bottom_tabs.currentIndex() == 1

    restored.close()


@pytest.mark.parametrize(("stored_index", "expected_index"), [(-100, 0), (100, 1)])
def test_bottom_tab_setting_is_clamped(
    qtbot: object,
    stored_index: int,
    expected_index: int,
) -> None:
    QSettings().setValue("analysis/bottom_tab", stored_index)

    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert window.bottom_tabs.currentIndex() == expected_index

    window.close()


def test_line_profile_uses_shift_drag_and_rejects_legacy_alt_drag() -> None:
    assert RoiViewBox.gesture_for_modifiers(Qt.KeyboardModifier.NoModifier) is None
    assert RoiViewBox.gesture_for_modifiers(Qt.KeyboardModifier.ShiftModifier) == "line"
    assert RoiViewBox.gesture_for_modifiers(Qt.KeyboardModifier.AltModifier) is None
    assert RoiViewBox.gesture_for_modifiers(Qt.KeyboardModifier.ControlModifier) == "roi"


def test_floating_plots_geometry_survives_hide_show_and_restart(qtbot: object) -> None:
    requested = QRect(180, 140, 760, 420)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.show()
    window._set_plots_visible(True)
    window.bottom_dock.setFloating(True)
    qtbot.waitUntil(window.bottom_dock.isFloating)  # type: ignore[attr-defined]
    window.bottom_dock.setGeometry(requested)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: QSettings().value(PLOTS_FLOATING_GEOMETRY_SETTING) is not None
    )
    qtbot.wait(50)  # type: ignore[attr-defined]
    expected = QRect(window.bottom_dock.geometry())

    window.bottom_dock.hide()
    window.bottom_dock.show()
    assert window.bottom_dock.isFloating()
    assert _geometry_close(window.bottom_dock.geometry(), expected)
    window._save_ui_state()
    window.close()

    restored = MainWindow()
    qtbot.addWidget(restored)  # type: ignore[attr-defined]
    restored.show()
    qtbot.waitUntil(restored.bottom_dock.isFloating)  # type: ignore[attr-defined]
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: _geometry_close(restored.bottom_dock.geometry(), expected)
    )

    restored.close()


def test_floating_title_double_click_maximizes_and_restores(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.show()
    window._set_plots_visible(True)
    window.bottom_dock.setFloating(True)
    qtbot.waitUntil(window.bottom_dock.isFloating)  # type: ignore[attr-defined]

    qtbot.mouseDClick(  # type: ignore[attr-defined]
        window.plots_dock_title,
        Qt.MouseButton.LeftButton,
    )
    qtbot.waitUntil(window.bottom_dock.isMaximized)  # type: ignore[attr-defined]
    assert window.plots_dock_title.maximize_button.toolTip() == "Restore Plots"

    qtbot.mouseDClick(  # type: ignore[attr-defined]
        window.plots_dock_title,
        Qt.MouseButton.LeftButton,
    )
    qtbot.waitUntil(lambda: not window.bottom_dock.isMaximized())  # type: ignore[attr-defined]
    assert window.bottom_dock.isFloating()
    assert window.plots_dock_title.maximize_button.toolTip() == "Maximize Plots"

    window.close()


def test_clear_actions_keep_roi_and_line_shortcuts_independent(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    assert "Clear ROI" in window.action_map
    assert "Clear ROI / Restore Grid" not in window.action_map

    roi = RoiBounds(1, 2, 3, 4)
    line = LineSelection(2, 4, 10)
    window._shared_roi = roi
    window._shared_line = line
    window.action_map["Clear ROI"].trigger()
    assert window._shared_roi is None
    assert window._shared_line == line

    window._shared_roi = roi
    window.action_map["Clear Line Profile"].trigger()
    assert window._shared_roi == roi
    assert window._shared_line is None
    assert "Clear ROI / Restore Grid" not in window.action_map

    window.close()


def test_reset_workspace_removes_floating_plots_geometry(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    QSettings().setValue(PLOTS_FLOATING_GEOMETRY_SETTING, b"stored")
    window.plots_dock_title._floating_geometry = QByteArray(b"stored")

    window.action_map["Reset Workspace Layout"].trigger()

    assert QSettings().value(PLOTS_FLOATING_GEOMETRY_SETTING) is None
    assert window.plots_dock_title._floating_geometry.isEmpty()
    window.close()
