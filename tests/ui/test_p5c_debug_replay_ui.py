from __future__ import annotations

from pathlib import Path

import pytest

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.remote.iqa_debug_replay import parse_replay_record
from pixelscope.ui.iqa_replay_debug import register_replay_record

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _replay() -> object:
    return parse_replay_record(
        {
            "debug_format": "pixelscope-iqa-replay-v1",
            "job_id": "job_debug_ui",
            "submission_kind": "folder_pair",
            "state": "succeeded",
            "completed_scenes": 3,
            "total_scenes": 3,
            "message": "synthetic UI replay",
            "result_reference": {
                "job_id": "job_debug_ui",
                "storage_root_id": "debug_iqa",
                "relative_path": "results/job_debug_ui",
                "schema_version": 2,
                "publication_state": "complete",
            },
        }
    )


def test_debug_replay_control_is_opt_in_only(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PIXELSCOPE_REMOTE_IQA_DEBUG", raising=False)
    release = MainWindow()
    qtbot.addWidget(release)  # type: ignore[attr-defined]
    _compose_main_window_presentation(release)
    assert not hasattr(release, "remote_iqa_replay_button")
    release.close()

    monkeypatch.setenv("PIXELSCOPE_REMOTE_IQA_DEBUG", "1")
    debug = MainWindow()
    qtbot.addWidget(debug)  # type: ignore[attr-defined]
    _compose_main_window_presentation(debug)
    assert debug.remote_iqa_replay_button.text() == "Replay JSON · DEBUG"
    assert "no HTTP" in debug.remote_iqa_replay_status.text()
    debug.close()


def test_replay_registers_terminal_job_without_automatic_open(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PIXELSCOPE_REMOTE_IQA_DEBUG", "1")
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    controller = window.remote_iqa_controller
    workspace = window.remote_iqa_workspace
    result_root = tmp_path / "published"
    result_root.mkdir()
    opened: list[Path] = []
    monkeypatch.setattr(window.iqa_controller, "open_result", opened.append)

    def resolve(job: object) -> None:
        job.result_path = result_root  # type: ignore[attr-defined]
        workspace.upsert_job(job)

    monkeypatch.setattr(controller, "_resolve_result_path", resolve)
    replay = _replay()
    job = register_replay_record(window, replay)  # type: ignore[arg-type]

    assert opened == []
    assert controller._jobs[job.job_id] is job
    assert workspace.tabs.currentWidget() is workspace.jobs_page
    assert workspace.open_button.isEnabled()

    controller.open_result(job.job_id)

    assert opened == [result_root]
    assert workspace.tabs.currentWidget() is workspace.results_page
    window.close()
