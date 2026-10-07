from __future__ import annotations

from typing import Any

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QMessageBox, QVBoxLayout, QWidget

from pixelscope.app.main_window import MainWindow
from pixelscope.app.settings import ApplicationSettings, QSettingsAdapter, SettingsRepository
from pixelscope.app.window_contribution import MenuActionFactory, SettingsPageHost

pytestmark = pytest.mark.usefixtures("isolated_synced_qsettings")


class _SettingsContribution:
    def __init__(self) -> None:
        self.events: list[str] = []
        self.fail_validation = False
        self.page: QWidget | None = None

    def prepare(self, window: Any) -> None:
        del window

    def install_dock(self, window: Any) -> None:
        del window

    def install_actions(
        self,
        window: Any,
        menu_name: str,
        add_action: MenuActionFactory,
    ) -> None:
        del window, menu_name, add_action

    def install_settings(self, settings: SettingsPageHost) -> None:
        page = QWidget()
        page.setObjectName("testExtensionSettingsPage")
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Extension-owned settings", page))
        settings.add_contributed_page(
            "Test Extension",
            page,
            validate=self._validate,
            save=self._save,
            reset=self._reset,
        )
        self.page = page

    def shutdown(self) -> None:
        self.events.append("shutdown")

    def _validate(self) -> None:
        self.events.append("validate")
        if self.fail_validation:
            raise ValueError("extension value is invalid")

    def _save(self) -> None:
        self.events.append("save")

    def _reset(self) -> None:
        self.events.append("reset")


def _repository() -> SettingsRepository:
    return SettingsRepository(QSettingsAdapter(QSettings()))


def test_generic_settings_contribution_adds_page_and_participates_in_save(
    qtbot: object,
) -> None:
    repository = _repository()
    initial = repository.save(ApplicationSettings())
    contribution = _SettingsContribution()
    window = MainWindow(
        initial,
        initial.performance_settings(),
        repository,
        window_contributions=(contribution,),
    )
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    dialog = window.create_settings_dialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    labels = [
        dialog.category_list.item(index).text()
        for index in range(dialog.category_list.count())
    ]
    assert labels == ["General", "Files", "Performance", "Test Extension"]
    assert contribution.page is not None
    assert dialog.page_stack.indexOf(contribution.page) == 3

    save = dialog.button_box.button(QDialogButtonBox.StandardButton.Save)
    assert save is not None
    qtbot.mouseClick(save, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]

    assert contribution.events == ["validate", "save"]
    assert dialog.result() == int(QDialog.DialogCode.Accepted)


def test_generic_settings_validation_blocks_base_save_and_surfaces_message(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _repository()
    initial = repository.save(ApplicationSettings(difference_gain=3))
    contribution = _SettingsContribution()
    contribution.fail_validation = True
    window = MainWindow(
        initial,
        initial.performance_settings(),
        repository,
        window_contributions=(contribution,),
    )
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    dialog = window.create_settings_dialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.difference_gain.setValue(7)

    warnings: list[tuple[str, str]] = []

    def capture_warning(
        _parent: object,
        title: str,
        message: str,
    ) -> QMessageBox.StandardButton:
        warnings.append((title, message))
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "warning", capture_warning)
    save = dialog.button_box.button(QDialogButtonBox.StandardButton.Save)
    assert save is not None
    qtbot.mouseClick(save, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]

    assert contribution.events == ["validate"]
    assert repository.load() == initial
    assert dialog.result() == int(QDialog.DialogCode.Rejected)
    assert warnings == [("Invalid extension settings", "extension value is invalid")]


def test_generic_settings_reset_runs_extension_hook(qtbot: object) -> None:
    repository = _repository()
    initial = repository.save(ApplicationSettings(difference_gain=5))
    contribution = _SettingsContribution()
    window = MainWindow(
        initial,
        initial.performance_settings(),
        repository,
        window_contributions=(contribution,),
    )
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    dialog = window.create_settings_dialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    qtbot.mouseClick(  # type: ignore[attr-defined]
        dialog.reset_button,
        Qt.MouseButton.LeftButton,
    )

    assert contribution.events == ["reset"]
    assert repository.load() == ApplicationSettings()
