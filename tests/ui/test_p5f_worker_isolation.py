from __future__ import annotations

from collections.abc import Callable
from threading import Event, Lock

import pytest
from PySide6.QtCore import QThreadPool

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.remote.iqa_client import IqaJobClient
from pixelscope.remote.iqa_submission import (
    IqaJobCreated,
    IqaJobRequest,
    IqaJobStatus,
    IqaResultReference,
    JobState,
)
from pixelscope.remote.iqa_transport_pool import ReusableIqaClientPool
from pixelscope.ui.iqa_historical_results import install_historical_iqa_results
from pixelscope.ui.iqa_scene_inspection import install_iqa_scene_inspection
from pixelscope.ui.iqa_submission import RemoteJobRecord
from pixelscope.workers.iqa_thread_pool import REMOTE_IQA_MAX_THREADS, remote_iqa_thread_pool
from pixelscope.workers.task_worker import TaskWorker
from pixelscope.workers.thread_pools import ANALYSIS_MAX_THREADS, analysis_thread_pool


class _BlockingStatusClient(IqaJobClient):
    def __init__(self, on_start: Callable[[], None], release: Event) -> None:
        self._on_start = on_start
        self._release = release
        self.close_calls = 0

    def create_job(self, request: IqaJobRequest) -> IqaJobCreated:
        raise AssertionError("not used")

    def get_status(self, job_id: str) -> IqaJobStatus:
        self._on_start()
        self._release.wait(timeout=5.0)
        return IqaJobStatus(job_id, JobState.QUEUED, 0, 1)

    def get_result(self, job_id: str) -> IqaResultReference:
        raise AssertionError("not used")

    def cancel_job(self, job_id: str) -> IqaJobStatus:
        raise AssertionError("not used")

    def close(self) -> None:
        self.close_calls += 1


def test_remote_iqa_pool_is_distinct_and_bounded(qtbot: object) -> None:
    remote = remote_iqa_thread_pool()
    analysis = analysis_thread_pool()

    assert remote is not analysis
    assert remote.maxThreadCount() == REMOTE_IQA_MAX_THREADS == 2
    assert analysis.maxThreadCount() == ANALYSIS_MAX_THREADS == 2


def test_production_composition_binds_only_result_side_work_to_remote_iqa_pool(
    qtbot: object,
) -> None:
    remote = remote_iqa_thread_pool()
    window = MainWindow(iqa_result_pool=remote)
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)

    local_analysis = analysis_thread_pool()
    job_pool = window.remote_iqa_controller._pool

    assert window.iqa_controller.pool is remote
    assert window.iqa_scene_inspection_controller.pool is remote
    assert window.historical_iqa_results_controller.pool is remote
    assert job_pool is not remote
    assert job_pool is not local_analysis
    assert job_pool.maxThreadCount() == 2
    assert remote is not local_analysis

    assert install_iqa_scene_inspection(window, pool=remote) is (
        window.iqa_scene_inspection_controller
    )
    assert install_historical_iqa_results(window, pool=remote) is (
        window.historical_iqa_results_controller
    )
    unexpected_pool = QThreadPool(window)
    with pytest.raises(RuntimeError, match="different worker pool"):
        install_iqa_scene_inspection(window, pool=unexpected_pool)
    with pytest.raises(RuntimeError, match="different worker pool"):
        install_historical_iqa_results(window, pool=unexpected_pool)

    window.close()


def test_blocked_remote_iqa_workers_do_not_monopolize_local_analysis(
    qtbot: object,
) -> None:
    remote = remote_iqa_thread_pool()
    analysis = analysis_thread_pool()
    release = Event()
    started_count = 0
    started_lock = Lock()
    both_started = Event()
    local_done = Event()

    def blocked_remote() -> None:
        nonlocal started_count
        with started_lock:
            started_count += 1
            if started_count == REMOTE_IQA_MAX_THREADS:
                both_started.set()
        release.wait(timeout=5.0)

    workers = [TaskWorker(blocked_remote) for _ in range(REMOTE_IQA_MAX_THREADS)]
    for worker in workers:
        remote.start(worker)

    qtbot.waitUntil(both_started.is_set, timeout=3000)  # type: ignore[attr-defined]
    local_worker = TaskWorker(local_done.set)
    analysis.start(local_worker)
    qtbot.waitUntil(local_done.is_set, timeout=3000)  # type: ignore[attr-defined]

    release.set()
    assert remote.waitForDone(3000)
    assert analysis.waitForDone(3000)


def test_queued_p5c_operations_do_not_acquire_http_clients_or_leak_on_shutdown(
    qtbot: object,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    controller = window.remote_iqa_controller

    release = Event()
    two_started = Event()
    start_lock = Lock()
    started_count = 0
    clients: list[_BlockingStatusClient] = []

    def on_start() -> None:
        nonlocal started_count
        with start_lock:
            started_count += 1
            if started_count == 2:
                two_started.set()

    def build(_endpoint: str) -> IqaJobClient:
        client = _BlockingStatusClient(on_start, release)
        clients.append(client)
        return client

    transport = ReusableIqaClientPool(build, max_idle_clients=2)
    controller._client_factory = transport.client
    for index in range(4):
        job = RemoteJobRecord(
            f"job_{index}",
            "folder_pair",
            "https://iqa.example.test",
            JobState.QUEUED,
            0,
            1,
            "queued",
        )
        controller._jobs[job.job_id] = job

    controller._poll_due()
    qtbot.waitUntil(two_started.is_set, timeout=3000)  # type: ignore[attr-defined]

    assert len(clients) == 2
    assert transport.diagnostics.clients_created == 2
    assert transport.diagnostics.active_leases == 2
    assert controller._pool.activeThreadCount() == 2

    controller.shutdown()
    transport.close()
    assert transport.diagnostics.closed
    assert transport.diagnostics.active_leases == 2

    release.set()
    assert controller._pool.waitForDone(3000)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: transport.diagnostics.active_leases == 0,
        timeout=3000,
    )

    assert len(clients) == 2
    assert all(client.close_calls == 1 for client in clients)
    window.close()
