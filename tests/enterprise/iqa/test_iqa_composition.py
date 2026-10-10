"""Issue #156 U6: explicit enterprise composition, settings and job ownership."""

from __future__ import annotations

from pathlib import Path
from threading import Thread

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDockWidget, QMainWindow

from pixelscope_enterprise.iqa.analysis_window import AnalysisWindowManager
from pixelscope_enterprise.iqa.composition import IqaJobSnapshot, IqaWindowContribution
from pixelscope_enterprise.iqa.demo import make_synthetic_result


class _Host(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.registered: list[QDockWidget] = []
        self.paths: tuple[Path | None, ...] = (Path("a.png"), None, Path("b.png"))

    def current_comparison_source_paths(self) -> tuple[Path | None, ...]:
        return self.paths

    def register_contributed_dock(self, dock: QDockWidget) -> None:
        self.registered.append(dock)


def _settings_factory(path: Path) -> QSettings:
    return QSettings(str(path), QSettings.Format.IniFormat)


def test_injected_iqa_settings_preserve_job_and_window_geometry(
    qtbot: object, tmp_path: Path
) -> None:
    path = tmp_path / "private-iqa-only.ini"

    def factory() -> QSettings:
        return _settings_factory(path)

    manager = AnalysisWindowManager(settings_factory=factory)
    window = manager.show()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.close()
    stored = factory()
    stored.sync()
    assert stored.contains("analysis_window_geometry")
    assert stored.contains("analysis_window_spatial_dock_state")
    assert not stored.contains("settings/schema_version")
    manager.shutdown()
    assert manager.window is None
    with pytest.raises(RuntimeError, match="shut down"):
        manager.show()


def test_window_contribution_jobs_are_user_opened_and_workers_private(
    qtbot: object, tmp_path: Path
) -> None:
    host = _Host()
    qtbot.addWidget(host)  # type: ignore[attr-defined]
    calls: list[tuple[Path | None, ...]] = []

    def factory() -> QSettings:
        return _settings_factory(tmp_path / "full-settings.ini")

    contribution = IqaWindowContribution(settings_factory=factory, start_job=calls.append)
    contribution.prepare(host)
    contribution.install_dock(host)
    assert contribution.jobs_dock in host.registered
    assert not contribution.jobs_dock.isVisible()

    actions: dict[str, QAction] = {}

    def add_action(menu: str, title: str, callback: object, shortcut: str | None = None) -> QAction:
        assert menu in ("IQA", "View")
        action = QAction(title, host)
        action.triggered.connect(callback)  # type: ignore[attr-defined]
        if shortcut is not None:
            action.setShortcut(shortcut)
        actions[title] = action
        return action

    for menu in ("IQA", "View"):
        contribution.install_actions(host, menu, add_action)
    contribution.install_runtime(host)
    host.show()
    qtbot.waitUntil(host.isVisible, timeout=4000)  # type: ignore[attr-defined]
    assert set(actions) == {"Open IQA Analysis", "Run IQA", "Show IQA Jobs"}
    assert actions["Show IQA Jobs"].isCheckable()
    assert not actions["Show IQA Jobs"].isChecked()
    assert contribution.jobs_status_button is not None
    assert contribution.jobs_status_button.isHidden()
    actions["Run IQA"].trigger()
    assert calls == [host.paths]

    synthetic = make_synthetic_result("u6-complete")
    contribution.publish_job(IqaJobSnapshot("j1", "Pair 1", "queued"))
    assert not contribution.jobs_status_button.isHidden()
    assert "queued" in contribution.jobs_status_button.text()
    assert contribution.jobs_dock is not None
    assert contribution.jobs_dock.isHidden()  # Hidden list does not conceal status.
    contribution.publish_job(IqaJobSnapshot("j1", "Pair 1", "running"))
    assert "running" in contribution.jobs_status_button.text()
    assert contribution.jobs_list is not None
    assert contribution.jobs_list.count() == 1
    assert contribution.manager.window is None
    contribution.jobs_list.setCurrentRow(0)
    assert contribution.view_selected_button is not None
    assert not contribution.view_selected_button.isEnabled()
    contribution.publish_job(IqaJobSnapshot("j1", "Pair 1", "completed", synthetic))
    assert contribution.view_selected_button.isEnabled()
    assert contribution.manager.window is None  # Completion is a notification, not auto-open.
    assert "completed" in contribution.jobs_status_button.text()
    assert contribution.jobs_dock.isHidden()
    contribution.jobs_status_button.click()
    qtbot.waitUntil(contribution.jobs_dock.isVisible, timeout=4000)  # type: ignore[attr-defined]
    assert actions["Show IQA Jobs"].isChecked()
    actions["Show IQA Jobs"].trigger()
    assert contribution.jobs_dock.isHidden()
    assert not actions["Show IQA Jobs"].isChecked()
    actions["Show IQA Jobs"].trigger()
    assert not contribution.jobs_dock.isHidden()
    assert actions["Show IQA Jobs"].isChecked()
    contribution.jobs_dock.hide()
    assert not actions["Show IQA Jobs"].isChecked()
    result_window = contribution.open_selected_result()
    assert result_window is not None
    qtbot.addWidget(result_window)  # type: ignore[attr-defined]
    assert result_window.active_result_id == "u6-complete"
    assert contribution.open_analysis() is result_window  # Exactly one analysis window.

    contribution.shutdown()
    contribution.shutdown()
    assert contribution.manager.window is None
    with pytest.raises(RuntimeError, match="shut down"):
        contribution.open_analysis()
    host.close()


def test_job_snapshot_rejects_invalid_or_leaked_incomplete_result() -> None:
    with pytest.raises(ValueError, match="invalid IQA"):
        IqaJobSnapshot("", "Pair", "queued")
    with pytest.raises(ValueError, match="invalid IQA"):
        IqaJobSnapshot("j", "Pair", "unknown")
    with pytest.raises(ValueError, match="only completed"):
        IqaJobSnapshot("j", "Pair", "running", make_synthetic_result("bad"))


def test_without_authorized_starter_has_no_run_action_or_auto_worker(
    qtbot: object,
) -> None:
    host = _Host()
    qtbot.addWidget(host)  # type: ignore[attr-defined]
    contribution = IqaWindowContribution()
    contribution.prepare(host)
    contribution.install_dock(host)
    actions: dict[str, QAction] = {}

    def add_action(menu: str, title: str, callback: object, shortcut: str | None = None) -> QAction:
        action = QAction(title, host)
        action.triggered.connect(callback)  # type: ignore[attr-defined]
        actions[title] = action
        return action

    contribution.install_actions(host, "IQA", add_action)
    assert "Open IQA Analysis" in actions
    assert "Run IQA" not in actions
    with pytest.raises(RuntimeError, match="not installed"):
        contribution.request_analysis()
    contribution.shutdown()
    host.close()


def test_worker_thread_cannot_mutate_iqa_job_widgets(qtbot: object) -> None:
    host = _Host()
    qtbot.addWidget(host)  # type: ignore[attr-defined]
    contribution = IqaWindowContribution()
    contribution.prepare(host)
    contribution.install_dock(host)
    errors: list[str] = []

    def publish_on_worker() -> None:
        try:
            contribution.publish_job(IqaJobSnapshot("j-worker", "Worker", "running"))
        except RuntimeError as exc:
            errors.append(str(exc))

    worker = Thread(target=publish_on_worker, daemon=True)
    worker.start()
    worker.join(timeout=4)
    assert not worker.is_alive()
    assert errors == ["IQA job updates must be dispatched onto the Qt GUI thread"]
    assert contribution.jobs_list is not None
    assert contribution.jobs_list.count() == 0
    contribution.shutdown()
    host.close()
