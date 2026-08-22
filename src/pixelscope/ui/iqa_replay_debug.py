"""Debug-only logical replay injection for Remote IQA terminal jobs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from pixelscope.remote.iqa_debug_replay import (
    IqaReplayRecord,
    ReplayValidationError,
    load_replay_record,
)
from pixelscope.ui.iqa_request_debug import request_debug_enabled
from pixelscope.ui.iqa_submission import RemoteJobRecord


class RemoteIqaReplayDebugController(QObject):
    """Load logical terminal-job records into the existing Jobs/Open Result path."""

    def __init__(
        self,
        window: Any,
        button: QPushButton,
        status: QLabel,
    ) -> None:
        super().__init__(window)
        self.window = window
        self.button = button
        self.status = status
        button.clicked.connect(self.choose_replay)  # type: ignore[attr-defined]

    @Slot()
    def choose_replay(self) -> None:
        selected, _filter = QFileDialog.getOpenFileName(
            self.window,
            "Replay Remote IQA Debug JSON",
            "",
            "JSON files (*.json);;All files (*)",
        )
        if selected:
            self.replay_path(Path(selected))

    def replay_path(self, path: Path | str) -> RemoteJobRecord | None:
        try:
            replay = load_replay_record(path)
            job = register_replay_record(self.window, replay)
        except (OSError, ReplayValidationError, RuntimeError, ValueError) as exc:
            self.status.setText(f"DEBUG replay blocked · {_bounded(str(exc))}")
            return None
        self.status.setText(
            f"DEBUG replay loaded · {job.job_id} · use Open Result explicitly"
        )
        return job


def register_replay_record(window: Any, replay: IqaReplayRecord) -> RemoteJobRecord:
    """Inject one terminal debug job without creating an HTTP client or opening the result."""

    controller = getattr(window, "remote_iqa_controller", None)
    workspace = getattr(window, "remote_iqa_workspace", None)
    if controller is None or workspace is None:
        raise RuntimeError("Remote IQA must be installed before debug replay")
    if not getattr(controller, "_active", False):
        raise RuntimeError("Remote IQA controller is not active")
    if replay.job_id in getattr(controller, "_result_resolve_jobs", set()):
        raise RuntimeError("the replay job is already resolving")

    job = RemoteJobRecord(
        replay.job_id,
        replay.submission_kind,
        "debug-replay://local",
        replay.state,
        replay.completed_scenes,
        replay.total_scenes,
        replay.message or "debug replay loaded",
        result_reference=replay.result_reference,
    )
    controller._jobs[job.job_id] = job
    workspace.upsert_job(job)
    workspace.tabs.setCurrentWidget(workspace.jobs_page)
    controller._resolve_result_path(job)
    return job


def install_remote_iqa_replay_debug(
    window: Any,
) -> RemoteIqaReplayDebugController | None:
    """Install a Jobs-tab replay action only when the shared P5-C debug opt-in is active."""

    if not request_debug_enabled():
        return None
    workspace = getattr(window, "remote_iqa_workspace", None)
    if workspace is None:
        raise RuntimeError("Remote IQA must be installed before debug replay")
    jobs_layout = workspace.jobs_page.layout()
    if not isinstance(jobs_layout, QVBoxLayout):
        raise RuntimeError("Remote IQA Jobs layout is unavailable for debug replay")

    row = QHBoxLayout()
    row.setSpacing(6)
    status = QLabel("DEBUG · Replay logical job/result JSON · no HTTP", workspace.jobs_page)
    status.setObjectName("remoteIqaDebugReplayStatus")
    button = QPushButton("Replay JSON · DEBUG", workspace.jobs_page)
    button.setObjectName("remoteIqaDebugReplayJson")
    button.setToolTip(
        "Load a bounded logical terminal-job replay record. Result opening remains explicit."
    )
    row.addWidget(status, 1)
    row.addWidget(button)
    jobs_layout.addLayout(row)

    controller = RemoteIqaReplayDebugController(window, button, status)
    window.remote_iqa_replay_debug_controller = controller
    window.remote_iqa_replay_button = button
    window.remote_iqa_replay_status = status
    return controller


def _bounded(value: str) -> str:
    clean = " ".join(value.split())
    return (clean or "unexpected debug replay error")[:512]
