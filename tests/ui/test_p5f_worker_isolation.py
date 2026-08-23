from __future__ import annotations

from threading import Event, Lock

from pixelscope.workers.iqa_thread_pool import REMOTE_IQA_MAX_THREADS, remote_iqa_thread_pool
from pixelscope.workers.task_worker import TaskWorker
from pixelscope.workers.thread_pools import ANALYSIS_MAX_THREADS, analysis_thread_pool


def test_remote_iqa_pool_is_distinct_and_bounded(qtbot: object) -> None:
    remote = remote_iqa_thread_pool()
    analysis = analysis_thread_pool()

    assert remote is not analysis
    assert remote.maxThreadCount() == REMOTE_IQA_MAX_THREADS == 2
    assert analysis.maxThreadCount() == ANALYSIS_MAX_THREADS == 2


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
