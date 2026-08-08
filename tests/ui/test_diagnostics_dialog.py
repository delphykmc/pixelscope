from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog

from pixelscope.app.main_window import MainWindow
from pixelscope.core.diagnostics import format_runtime_diagnostics
from pixelscope.core.image_document import ImageDocument
from pixelscope.ui.diagnostics_dialog import DiagnosticsDialog


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path: Path) -> None:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    QSettings().clear()


def test_help_diagnostics_action_opens_runtime_dialog(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[DiagnosticsDialog] = []

    def fake_exec(dialog: DiagnosticsDialog) -> int:
        opened.append(dialog)
        return int(QDialog.DialogCode.Rejected)

    monkeypatch.setattr(DiagnosticsDialog, "exec", fake_exec)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    help_action = next(action for action in window.menuBar().actions() if action.text() == "&Help")
    help_menu = help_action.menu()
    assert help_menu is not None
    assert [action.text() for action in help_menu.actions()] == ["Diagnostics..."]

    window.action_map["Diagnostics..."].trigger()

    assert len(opened) == 1
    assert opened[0].windowTitle() == "Runtime Diagnostics"
    assert opened[0].text.isReadOnly()


def test_refresh_copy_and_save_use_identical_sanitized_displayed_text(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    private_path = tmp_path / "private-user" / "registered.png"
    document = ImageDocument.from_array(
        np.ones((2, 3), dtype=np.uint8),
        private_path.name,
        source_path=private_path,
    )
    window.add_document(document, select=False)
    window._record_runtime_failure(
        "foreground-load",
        "decode",
        RuntimeError(r"failed at C:\Users\private-user\registered.png token=secret"),
    )

    calls = 0

    def snapshot_provider():  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return window.runtime_diagnostics_snapshot()

    def unexpected_work(*_args: object, **_kwargs: object) -> None:
        pytest.fail("diagnostics UI started or refreshed runtime work")

    monkeypatch.setattr(window, "_start_load", unexpected_work)
    monkeypatch.setattr(window, "_start_preload", unexpected_work)
    monkeypatch.setattr(window, "_refresh_preload_plan", unexpected_work)
    monkeypatch.setattr(window, "_render_selection", unexpected_work)

    dialog = DiagnosticsDialog(snapshot_provider, window)
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    assert calls == 1
    assert dialog.displayed_text == format_runtime_diagnostics(
        window.runtime_diagnostics_snapshot()
    )
    assert "private-user" not in dialog.displayed_text
    assert "registered.png" not in dialog.displayed_text
    assert "secret" not in dialog.displayed_text

    window._normal_load_stale_drop_count = 4
    dialog.refresh_button.click()
    assert calls == 2
    assert "Foreground stale drops: 4" in dialog.displayed_text

    dialog.copy_button.click()
    assert QApplication.clipboard().text() == dialog.displayed_text

    saved_path = tmp_path / "saved-diagnostics.txt"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: (str(saved_path), "Text files (*.txt)"),
    )
    dialog.save_button.click()

    assert saved_path.read_text(encoding="utf-8") == dialog.displayed_text
    assert calls == 2
