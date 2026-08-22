from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QDockWidget, QTableWidgetItem

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.app.settings import (
    ApplicationSettings,
    QSettingsAdapter,
    SettingsRepository,
)
from pixelscope.remote.iqa_domain import LoadStatus
from pixelscope.remote.iqa_result_reader import load_result
from pixelscope.remote.iqa_settings import RemoteIqaSettings, RemoteIqaStorageRoot
from pixelscope.remote.iqa_submission import JobState
from pixelscope.remote.iqa_v2_fixture import write_golden_result_v2
from pixelscope.ui.iqa_remote_settings import RemoteIqaSettingsDialog
from pixelscope.ui.iqa_submission import RemoteIqaWorkspace, RemoteJobRecord


@pytest.fixture(autouse=True)
def isolated_ui_settings(tmp_path: Path) -> None:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str(tmp_path),
    )
    QSettings().clear()


def _repository() -> SettingsRepository:
    return SettingsRepository(QSettingsAdapter(QSettings()))


def _make_partial(root: Path) -> Path:
    result_root = write_golden_result_v2(root, scene_count=3)
    manifest_path = result_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["publication_state"] = "partial"
    manifest["scene_outcomes"] = [
        {"scene_id": "scene_000000", "status": "succeeded"},
        {"scene_id": "scene_000001", "status": "succeeded"},
        {"scene_id": "scene_000002", "status": "succeeded"},
        {
            "scene_id": "scene_000003",
            "status": "failed",
            "error": {
                "code": "source_unavailable",
                "message": "source was unavailable",
                "retryable": True,
            },
        },
    ]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return result_root


def test_remote_settings_dialog_round_trips_machine_local_mapping(
    qtbot: object,
) -> None:
    repository = _repository()
    dialog = RemoteIqaSettingsDialog(
        repository,
        ApplicationSettings(),
        ApplicationSettings().performance_settings(),
    )
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert dialog.category_list.findItems("Remote IQA", Qt.MatchFlag.MatchExactly)
    dialog.remote_server_url.setText("https://iqa.example.test")
    dialog.remote_roots.setRowCount(1)
    dialog.remote_roots.setItem(0, 0, QTableWidgetItem("shared"))
    dialog.remote_roots.setItem(0, 1, QTableWidgetItem("C:/shared"))
    dialog._refresh_staging_choices("shared")

    settings = dialog.settings()

    assert settings.remote_iqa == RemoteIqaSettings(
        "https://iqa.example.test",
        (RemoteIqaStorageRoot("shared", "C:/shared"),),
        "shared",
    )
    assert "restart" not in dialog.remote_page.toolTip().casefold()


def test_production_composition_extends_exactly_one_existing_iqa_dock(
    qtbot: object,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    _compose_main_window_presentation(window)

    assert isinstance(window.iqa_dock.widget(), RemoteIqaWorkspace)
    assert window.iqa_dock.widget() is window.remote_iqa_workspace
    assert window.remote_iqa_workspace.tabs.count() == 3
    assert [
        window.remote_iqa_workspace.tabs.tabText(index)
        for index in range(window.remote_iqa_workspace.tabs.count())
    ] == ["Setup", "Jobs", "Results"]
    assert window.iqa_workspace.parent() is window.remote_iqa_workspace.results_page
    iqa_docks = [
        dock
        for dock in window.findChildren(QDockWidget)
        if dock.objectName() == "iqaWorkspaceDock"
    ]
    assert iqa_docks == [window.iqa_dock]
    assert isinstance(window.create_settings_dialog(), RemoteIqaSettingsDialog)
    window.close()


def test_job_open_result_reuses_p5b_controller_and_is_never_automatic(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    controller = window.remote_iqa_controller
    workspace = window.remote_iqa_workspace
    opened: list[Path] = []
    monkeypatch.setattr(window.iqa_controller, "open_result", opened.append)
    path = tmp_path / "published"
    path.mkdir()
    job = RemoteJobRecord(
        "job_000001",
        "current_pair",
        "https://iqa.example.test",
        JobState.SUCCEEDED,
        1,
        1,
        "result published",
        result_path=path,
    )
    controller._jobs[job.job_id] = job
    workspace.upsert_job(job)

    assert opened == []
    controller.open_result(job.job_id)

    assert opened == [path]
    assert workspace.tabs.currentWidget() is workspace.results_page
    window.close()


def test_valid_partial_result_shows_compact_status_and_failed_scene_diagnostics(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    root = _make_partial(tmp_path / "partial")
    outcome = load_result(root)
    assert outcome.status is LoadStatus.SUCCESS

    window.remote_iqa_workspace.present_result_outcome(outcome)

    assert window.remote_iqa_workspace.partial_status.isVisible() is False or (
        "3 / 4 Scenes succeeded" in window.remote_iqa_workspace.partial_status.text()
    )
    assert "3 / 4 Scenes succeeded" in window.remote_iqa_workspace.partial_status.text()
    assert window.remote_iqa_workspace.partial_diagnostics.topLevelItemCount() == 1
    item = window.remote_iqa_workspace.partial_diagnostics.topLevelItem(0)
    assert item.text(0) == "scene_000003"
    assert item.text(1) == "failed"
    assert item.text(2) == "source_unavailable"
    window.close()


def test_shutdown_rejects_late_submission_callbacks_without_remote_cancel(
    qtbot: object,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    controller = window.remote_iqa_controller
    generation = controller._generation

    controller.shutdown()
    controller._submission_ready("late", None, generation, object())

    assert controller._jobs == {}
    assert not controller._poll_timer.isActive()
    assert not controller._state_timer.isActive()
    window.close()
