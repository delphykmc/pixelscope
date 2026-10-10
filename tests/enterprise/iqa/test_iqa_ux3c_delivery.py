"""UX-3C: synthetic GUI-thread job-delivery and user-directed result workflow.

The PRIVATE SUB provider/transport is intentionally absent. The producer here
sends deterministic public-safe snapshots from a standard Python worker thread.
"""

from __future__ import annotations

from pathlib import Path
from threading import Thread

import pytest
from PySide6.QtCore import Qt
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
) -> None:
    host, contribution = _prepare(qtbot)
    result = make_synthetic_result("synthetic-completion")
    errors: list[str] = []

    def worker() -> None:
        try:
            contribution.post_job(IqaJobSnapshot("demo-one", "Synthetic pair", "queued"))
            contribution.post_job(IqaJobSnapshot("demo-one", "Synthetic pair", "running"))
            contribution.post_job(
                IqaJobSnapshot("demo-one", "Synthetic pair", "completed", result)
            )
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
