from __future__ import annotations

import pytest

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.remote.iqa_submission import IqaResultReference, JobState
from pixelscope.ui.iqa_result_retry import RESULT_REFERENCE_RETRY_DELAYS_SECONDS
from pixelscope.ui.iqa_submission import RemoteJobRecord

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def test_terminal_result_reference_failure_reenters_with_bounded_backoff(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    controller = window.remote_iqa_controller
    retry = window.remote_iqa_result_retry_controller
    workspace = window.remote_iqa_workspace
    job = RemoteJobRecord(
        "job_retry_000001",
        "folder_pair",
        "http://127.0.0.1:8765",
        JobState.SUCCEEDED,
        3,
        3,
        "result reference unavailable · http: HTTP 500",
    )
    controller._jobs[job.job_id] = job
    workspace.upsert_job(job)
    attempts: list[str] = []

    def start_fetch(target: RemoteJobRecord) -> None:
        attempts.append(target.job_id)
        controller._result_fetch_jobs.add(target.job_id)

    monkeypatch.setattr(controller, "_fetch_result_reference", start_fetch)
    retry._next_due[job.job_id] = 0.0
    retry._tick()

    assert attempts == [job.job_id]
    assert retry._retry_count[job.job_id] == 1

    controller._result_fetch_jobs.discard(job.job_id)
    retry._tick()
    assert job.job_id in retry._next_due

    retry._next_due[job.job_id] = 0.0
    retry._tick()
    assert attempts == [job.job_id, job.job_id]
    assert retry._retry_count[job.job_id] == 2

    job.result_reference = IqaResultReference(
        job.job_id,
        "debug_iqa",
        "results/job_retry_000001",
        2,
        "complete",
    )
    controller._result_fetch_jobs.discard(job.job_id)
    retry._tick()

    assert job.job_id not in retry._retry_count
    assert job.job_id not in retry._next_due
    window.close()


def test_terminal_result_reference_retry_limit_is_bounded(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    controller = window.remote_iqa_controller
    retry = window.remote_iqa_result_retry_controller
    workspace = window.remote_iqa_workspace
    job = RemoteJobRecord(
        "job_retry_exhausted",
        "folder_pair",
        "http://127.0.0.1:8765",
        JobState.PARTIAL,
        3,
        4,
        "result reference unavailable · http: HTTP 500",
    )
    controller._jobs[job.job_id] = job
    workspace.upsert_job(job)
    attempts: list[str] = []
    monkeypatch.setattr(
        controller,
        "_fetch_result_reference",
        lambda target: attempts.append(target.job_id),
    )
    retry._retry_count[job.job_id] = len(RESULT_REFERENCE_RETRY_DELAYS_SECONDS)
    retry._tick()

    assert attempts == []
    assert "retry limit reached" in (job.message or "")
    window.close()
