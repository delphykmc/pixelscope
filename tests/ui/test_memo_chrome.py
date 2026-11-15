from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication
from test_memo_evidence import windows as memo_windows

windows = memo_windows
pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def test_memo_floating_docked_chrome_and_shortcut(qtbot, request):
    window, memo = request.getfixturevalue("windows")()
    assert memo.action.shortcut().toString() == "Ctrl+Shift+M"
    memo.dock.setFloating(True)
    memo.show()
    memo.dock.activateWindow()
    QApplication.setActiveWindow(memo.dock)
    qtbot.waitUntil(lambda: memo.dock.isVisible() and memo.dock.isActiveWindow())
    assert memo.dock.windowOpacity() == 1.0
    assert not memo.dock.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert memo.panel.autoFillBackground()
    title = memo.dock.titleBarWidget()
    assert title is memo._dock_title
    assert not title.float_button.icon().isNull()
    assert not title.close_button.icon().isNull()
    clear_spy = QSignalSpy(window.action_map["Clear ROI"].triggered)
    memo._wait_for_statistics("Waiting for ROI Statistics")
    memo.panel.findings.setFocus()
    qtbot.keyClick(memo.panel.findings, Qt.Key.Key_Escape)
    assert clear_spy.count() == 1  # same Esc command, including floating focus
    assert not memo._pending_statistics and memo.restore.phase == "idle"
    output = Path.cwd() / "temp/memo-chrome"
    output.mkdir(parents=True, exist_ok=True)
    assert memo.dock.grab().save(str(output / "floating.png"))
    assert memo.action.isEnabled() and memo.action.isChecked()
    memo.panel.open_button.setFocus()
    qtbot.waitUntil(memo.panel.open_button.hasFocus)
    spy = QSignalSpy(memo.action.triggered)
    qtbot.keyClick(
        memo.panel.open_button,
        Qt.Key.Key_M,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
    )
    assert spy.count() == 1, (QApplication.applicationState(), memo.action.associatedObjects())
    qtbot.waitUntil(lambda: not memo.dock.isVisible())
    memo.action.trigger()
    qtbot.waitUntil(lambda: memo.dock.isVisible())
    title.float_button.click()
    qtbot.waitUntil(lambda: not memo.dock.isFloating())
    assert window.grab().save(str(output / "docked.png"))
    window.close()


def test_memo_toolbar_reuses_canonical_action_and_tracks_dock(qtbot, request):
    window, memo = request.getfixturevalue("windows")()
    actions = window.main_toolbar.actions()
    assert actions.count(memo.action) == 1
    assert actions.index(window.plots_action) < actions.index(memo.action)
    assert actions.index(memo.action) < actions.index(window.export_toolbar_action)
    assert not memo.action.icon().isNull()
    button = window.main_toolbar.widgetForAction(memo.action)
    assert button.isCheckable() and button.isChecked() == memo.dock.isVisible()
    if memo.dock.isVisible():
        button.click()
        qtbot.waitUntil(lambda: not memo.dock.isVisible())
    assert not button.isChecked()
    button.click()
    qtbot.waitUntil(memo.dock.isVisible)
    assert button.isChecked()
    memo.dock.setFloating(True)
    memo.dock.close()
    qtbot.waitUntil(lambda: not memo.dock.isVisible())
    assert not button.isChecked()
    memo.action.trigger()
    qtbot.waitUntil(memo.dock.isVisible)
    assert button.isChecked()
    button.click()
    qtbot.waitUntil(lambda: not memo.dock.isVisible())
    assert not button.isChecked()
    window.close()
