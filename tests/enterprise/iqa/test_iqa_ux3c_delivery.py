"""UX-3C: synthetic GUI-thread job-delivery and user-directed result workflow.

The PRIVATE SUB provider/transport is intentionally absent. The producer here
sends deterministic public-safe snapshots from a standard Python worker thread.
"""

from __future__ import annotations

from pathlib import Path
from threading import Thread

import pytest
from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow

from pixelscope_enterprise.iqa.composition import IqaJobSnapshot, IqaWindowContribution
from pixelscope_enterprise.iqa.demo import make_synthetic_result


class _PublicHost(QMainWindow):
    def current_comparison_source_paths(self) -> tuple[Path | None, ...]:
        return (Path("synthetic-a.png"), None, Path("synthetic-b.png"))


def _prepare(qtbot: object) -> tuple[_PublicHost, IqaWindowContribution]:
    host = _PublicHost()
    qtbot.addWidget(host)  # type: ignore[attr-defined]
    contribution = IqaWindowContribution()
    contribution.prepare(host)
    contribution.install_dock(host)
    contribution.install_runtime(host)
    host.show()
    return host, contribution


def test_synthetic_worker_completion_updates_hidden_dock_but_never_auto_opens(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host, contribution = _prepare(qtbot)
    result = make_synthetic_result("synthetic-completion")
    errors: list[str] = []
    observed: list[tuple[str, bool]] = []
    actual_publish = contribution.publish_job

    def record_gui_delivery(snapshot: IqaJobSnapshot) -> None:
        observed.append((snapshot.status, QThread.currentThread() == host.thread()))
        actual_publish(snapshot)

    monkeypatch.setattr(contribution, "publish_job", record_gui_delivery)

    def worker() -> None:
        try:
            contribution.post_job(IqaJobSnapshot("demo-one", "Synthetic pair", "queued"))
            contribution.post_job(IqaJobSnapshot("demo-one", "Synthetic pair", "running"))
            contribution.post_job(IqaJobSnapshot("demo-one", "Synthetic pair", "completed", result))
        except Exception as error:  # noqa: BLE001 - surface worker failure to assertion
            errors.append(str(error))

    thread = Thread(target=worker)
    thread.start()
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert not errors
    assert contribution.manager.window is None
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: contribution._records.get("demo-one") is not None
        and contribution._records["demo-one"].status == "completed",
        timeout=5000,
    )
    assert contribution.manager.window is None  # Completion never steals focus.
    assert observed == [
        ("queued", True),
        ("running", True),
        ("completed", True),
    ]
    assert contribution.jobs_dock is not None
    assert contribution.jobs_dock.isHidden()  # Status cue works while dock hidden.
    assert contribution.jobs_status_button is not None
    assert "completed" in contribution.jobs_status_button.text()
    contribution.jobs_status_button.click()
    qtbot.waitUntil(contribution.jobs_dock.isVisible, timeout=5000)  # type: ignore[attr-defined]
    assert contribution.jobs_list is not None
    assert contribution.jobs_list.count() == 1
    assert contribution.jobs_list.item(0).data(Qt.ItemDataRole.UserRole) == "demo-one"
    contribution.jobs_list.setCurrentRow(0)
    assert contribution.view_selected_button is not None
    assert contribution.view_selected_button.isEnabled()
    analysis = contribution.open_selected_result()
    assert analysis is not None
    qtbot.addWidget(analysis)  # type: ignore[attr-defined]
    assert analysis.active_result_id == "synthetic-completion"
    assert contribution.open_analysis() is analysis
    contribution.shutdown()
    host.close()


def test_synthetic_failed_cancelled_jobs_are_not_viewable(qtbot: object) -> None:
    host, contribution = _prepare(qtbot)

    def worker() -> None:
        contribution.post_job(IqaJobSnapshot("demo-fail", "Simulated failure", "queued"))
        contribution.post_job(IqaJobSnapshot("demo-fail", "Simulated failure", "running"))
        contribution.post_job(IqaJobSnapshot("demo-fail", "Simulated failure", "failed"))
        contribution.post_job(IqaJobSnapshot("demo-cancel", "Simulated cancellation", "queued"))
        contribution.post_job(IqaJobSnapshot("demo-cancel", "Simulated cancellation", "cancelled"))

    thread = Thread(target=worker)
    thread.start()
    thread.join(timeout=5)
    assert not thread.is_alive()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(contribution._records) == 2
        and contribution._records["demo-cancel"].status == "cancelled",
        timeout=5000,
    )
    assert contribution.manager.window is None
    assert contribution.jobs_list is not None
    assert contribution.jobs_list.count() == 2
    assert contribution.jobs_status_button is not None
    assert "cancelled" in contribution.jobs_status_button.text()
    for index in range(2):
        contribution.jobs_list.setCurrentRow(index)
        assert contribution.open_selected_result() is None
        assert contribution.view_selected_button is not None
        assert not contribution.view_selected_button.isEnabled()
    contribution.shutdown()
    host.close()


def test_queued_publication_is_quiesced_before_shutdown(qtbot: object) -> None:
    host, contribution = _prepare(qtbot)
    contribution.post_job(IqaJobSnapshot("late", "Late completion", "queued"))
    assert contribution.jobs_list is not None
    # Even GUI callers get queued delivery; nothing mutates synchronously.
    assert contribution.jobs_list.count() == 0
    contribution.shutdown()
    qtbot.wait(40)  # type: ignore[attr-defined]
    assert contribution.jobs_list.count() == 0
    assert not contribution._records
    assert contribution.jobs_status_button is not None
    assert contribution.jobs_status_button.isHidden()
    with pytest.raises(RuntimeError, match="not available"):
        contribution.post_job(IqaJobSnapshot("late", "Late", "completed"))
    with pytest.raises(TypeError, match="validated snapshot"):
        contribution.post_job("not a snapshot")  # type: ignore[arg-type]
    host.close()


def test_cancel_selected_job_requires_provider_and_explicit_job_capability(
    qtbot: object,
) -> None:
    host = _PublicHost()
    qtbot.addWidget(host)  # type: ignore[attr-defined]
    cancellations: list[str] = []
    contribution = IqaWindowContribution(cancel_job=cancellations.append)
    contribution.prepare(host)
    contribution.install_dock(host)

    actions: dict[str, QAction] = {}

    def add_action(
        _menu: str, title: str, callback: object, _shortcut: str | None = None
    ) -> QAction:
        action = QAction(title, host)
        action.triggered.connect(callback)  # type: ignore[attr-defined]
        actions[title] = action
        return action

    contribution.install_actions(host, "IQA", add_action)
    cancel = actions["Cancel Selected IQA Job"]
    assert "Run IQA" not in actions
    assert not cancel.isEnabled()
    assert contribution.cancel_selected_button is not None
    assert not contribution.cancel_selected_button.isEnabled()

    contribution.publish_job(IqaJobSnapshot("j1", "Cancellable active", "running", can_cancel=True))
    contribution.publish_job(IqaJobSnapshot("j2", "Unknown capability", "running"))
    contribution.publish_job(IqaJobSnapshot("j3", "Already completed", "completed"))
    assert contribution.jobs_list is not None
    assert contribution.jobs_list.count() == 3

    contribution.jobs_list.setCurrentRow(1)  # Running, but provider says no.
    assert not cancel.isEnabled()
    contribution.jobs_list.setCurrentRow(2)  # Terminal job.
    assert not cancel.isEnabled()
    contribution.jobs_list.setCurrentRow(0)  # Explicit true capability.
    assert cancel.isEnabled()
    assert contribution.cancel_selected_button.isEnabled()
    cancel.trigger()
    assert cancellations == ["j1"]
    # Request is visibly pending but must not fabricate a terminal state.
    assert "cancel requested" in contribution.jobs_list.item(0).text()
    assert contribution._records["j1"].status == "running"
    assert not cancel.isEnabled()  # Suppress duplicate requests.
    assert not contribution.cancel_selected_button.isEnabled()
    contribution.request_cancel_selected()
    assert cancellations == ["j1"]

    contribution.publish_job(IqaJobSnapshot("j1", "Cancellable active", "running", can_cancel=True))
    assert not cancel.isEnabled()  # An ordinary status poll is not rejection.
    contribution.publish_job(IqaJobSnapshot("j1", "Cancelled by provider", "cancelled"))
    assert "cancel requested" not in contribution.jobs_list.item(0).text()
    assert not cancel.isEnabled()
    assert contribution.open_selected_result() is None
    contribution.shutdown()
    host.close()


def test_cancel_callback_error_preserves_running_truth(
    qtbot: object,
) -> None:
    host = _PublicHost()
    qtbot.addWidget(host)  # type: ignore[attr-defined]
    calls: list[str] = []

    def reject_cancel(job_id: str) -> None:
        calls.append(job_id)
        raise RuntimeError("provider could not submit cancellation")

    contribution = IqaWindowContribution(cancel_job=reject_cancel)
    contribution.prepare(host)
    contribution.install_dock(host)
    contribution.publish_job(IqaJobSnapshot("active", "Needs backend", "queued", can_cancel=True))
    assert contribution.jobs_list is not None
    contribution.jobs_list.setCurrentRow(0)
    assert contribution.cancel_selected_button is not None
    assert contribution.cancel_selected_button.isEnabled()
    with pytest.raises(RuntimeError, match="could not submit"):
        contribution.request_cancel_selected()
    assert calls == ["active"]
    assert contribution._records["active"].status == "queued"
    assert "cancel requested" not in contribution.jobs_list.item(0).text()
    assert contribution.cancel_selected_button.isEnabled()
    contribution.shutdown()
    host.close()


def test_cancelled_status_does_not_automatically_imply_cancel_command(
    qtbot: object,
) -> None:
    host, contribution = _prepare(qtbot)
    contribution.publish_job(IqaJobSnapshot("reported", "Provider cancelled", "cancelled"))
    assert contribution.cancel_selected_button is None
    assert contribution.jobs_list is not None
    contribution.jobs_list.setCurrentRow(0)
    assert contribution.open_selected_result() is None
    with pytest.raises(RuntimeError, match="not installed"):
        contribution.request_cancel_selected()
    contribution.shutdown()
    host.close()


@pytest.mark.parametrize("state", ["completed", "failed", "cancelled"])
def test_terminal_snapshot_rejects_cancel_capability(state: str) -> None:
    with pytest.raises(ValueError, match="only cancellable active"):
        IqaJobSnapshot("j", "Terminal", state, can_cancel=True)
