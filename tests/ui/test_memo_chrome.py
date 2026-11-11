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
