"""One isolated real-MainWindow composition smoke for Issue #156 U6.

Run in its own pytest process on Windows to avoid mixing MAIN's many native
Qt teardown paths with the small in-memory/synthetic IQA tests.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings

from pixelscope.app.bootstrap import compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.app.settings import QSettingsAdapter, SettingsRepository
from pixelscope_enterprise.iqa.composition import IqaJobSnapshot, IqaWindowContribution


def test_real_main_window_contribution_menus_dock_runtime_and_shutdown(
    qtbot: object, tmp_path: Path
) -> None:
    base = QSettings(str(tmp_path / "base-settings.ini"), QSettings.Format.IniFormat)
    repository = SettingsRepository(QSettingsAdapter(base))
    application_settings = repository.load()
    calls: list[tuple[Path | None, ...]] = []

    def private_iqa_settings() -> QSettings:
        return QSettings(
            str(tmp_path / "private-iqa-settings.ini"), QSettings.Format.IniFormat
        )

    contribution = IqaWindowContribution(
        settings_factory=private_iqa_settings, start_job=calls.append
    )
    window = MainWindow(
        application_settings,
        application_settings.performance_settings(),
        repository,
        window_contributions=(contribution,),
    )
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    compose_main_window_presentation(window, runtime_contributions=(contribution,))
    assert contribution._runtime_installed
    assert window._menu_map["IQA"].title().replace("&", "") == "IQA"
    iqa_menu = {item.text() for item in window._menu_map["IQA"].actions()}
    assert {"Open IQA Analysis", "Run IQA"}.issubset(iqa_menu)
    assert contribution.jobs_dock in window._contributed_docks
    assert window.action_map["Show IQA Jobs"].isCheckable()

    window.show()
    qtbot.waitUntil(window.isVisible, timeout=5000)  # type: ignore[attr-defined]
    window.action_map["Run IQA"].trigger()
    assert calls == [window.current_comparison_source_paths()]
    assert contribution.manager.window is None
    contribution.publish_job(IqaJobSnapshot("main-smoke", "Native host", "completed"))
    assert contribution.jobs_status_button is not None
    assert contribution.jobs_status_button.isVisible()
    assert "completed" in contribution.jobs_status_button.text()
    assert contribution.jobs_dock is not None and contribution.jobs_dock.isHidden()
    contribution.jobs_status_button.click()
    qtbot.waitUntil(contribution.jobs_dock.isVisible, timeout=5000)  # type: ignore[attr-defined]
    assert window.action_map["Show IQA Jobs"].isChecked()

    window.close()
    assert contribution._closed
    assert contribution.manager.window is None
