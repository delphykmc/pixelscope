from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QSettings

from pixelscope.app.main_window import MainWindow
from pixelscope.core.difference_cache import CachedDifferenceMap
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.preload import PreloadMemberRequest
from pixelscope.workers.task_worker import TaskError, TaskWorker


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path: Path) -> None:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    QSettings().clear()


def _task_error(message: str, *, exception_type: str = "RuntimeError") -> TaskError:
    return TaskError(
        task_id="diagnostic-task",
        document_id=None,
        generation=0,
        message=message,
        exception_type=exception_type,
        traceback_text='Traceback at "C:\\Users\\alice\\private.py"',
    )


def test_runtime_snapshot_aggregates_existing_owners_without_mutation(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    source = window.residency_manager
    source.record("resident-a", 4)
    source.record("resident-b", 6)
    source.touch("resident-a")

    difference = window.difference_panel.difference_cache
    difference_key = (("a", 0), ("b", 0))
    cached = CachedDifferenceMap(
        absolute=np.ones((2, 3), dtype=np.uint8),
        data_range=255.0,
        channel_layout="GRAY",
        bayer_pattern=None,
    )
    assert difference.put(difference_key, cached).stored

    normal_worker = TaskWorker(lambda: None)
    window._workers[normal_worker.task_id] = normal_worker
    window._load_worker_targets[normal_worker.task_id] = "foreground-a"

    plan = window.preload_controller.set_plan(("preload-a",))
    assert plan is not None
    request = PreloadMemberRequest(
        plan_generation=plan.generation,
        document_id="preload-a",
        document_generation=0,
        source_path_identity="redacted-by-request-contract",
        profile_identity="",
        require_exact_raw_size=False,
        normal_load_token=0,
    )
    assert window.preload_controller.start_member(request)
    preload_worker = TaskWorker(lambda: None)
    window._preload_workers[preload_worker.task_id] = preload_worker
    window._preload_worker_requests[preload_worker.task_id] = request

    source_order = source.resident_document_ids
    difference_order = difference.keys()
    preload_generation = window.preload_controller.generation
    selection = tuple(window._selection_order)

    def unexpected_work(*_args: object, **_kwargs: object) -> None:
        pytest.fail("snapshot read started or refreshed runtime work")

    monkeypatch.setattr(window, "_start_load", unexpected_work)
    monkeypatch.setattr(window, "_start_preload", unexpected_work)
    monkeypatch.setattr(window, "_refresh_preload_plan", unexpected_work)
    monkeypatch.setattr(window, "_render_selection", unexpected_work)

    first = window.runtime_diagnostics_snapshot()
    second = window.runtime_diagnostics_snapshot()

    assert first == second
    assert first.source.used_bytes == 10
    assert first.source.resident_count == 2
    assert first.difference.used_bytes == cached.nbytes == 6
    assert first.difference.entry_count == 1
    assert first.workers.foreground_loads.active_count == 1
    assert first.workers.foreground_loads.max_count == 2
    assert first.workers.preload.active_count == 1
    assert first.workers.preload.max_count == 1
    assert first.preload.active_worker_count == 1
    assert source.resident_document_ids == source_order
    assert difference.keys() == difference_order
    assert window.preload_controller.generation == preload_generation
    assert tuple(window._selection_order) == selection
    assert window._workers == {normal_worker.task_id: normal_worker}
    assert window._preload_workers == {preload_worker.task_id: preload_worker}


def test_stale_and_failure_instrumentation_is_bounded_and_sanitized(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    source_path = tmp_path / "foreground.png"
    document = ImageDocument.pending_document(source_path)
    window.add_document(document, select=False)
    window._load_tokens[document.document_id] = 2
    stale_result = ImageDocument.from_array(
        np.ones((2, 2), dtype=np.uint8),
        source_path.name,
        source_path=source_path,
    )

    window._load_succeeded(document.document_id, 1, stale_result)
    window._load_succeeded("removed-document", 1, stale_result)
    window._load_failed(
        document.document_id,
        source_path,
        _task_error("obsolete failure"),
        request_token=1,
    )
    window._load_failed(
        document.document_id,
        source_path,
        _task_error(r"decode failed at C:\Users\alice\images\foreground.png token=secret"),
        request_token=2,
    )

    plan = window.preload_controller.set_plan(("preload-document",))
    assert plan is not None
    request = PreloadMemberRequest(
        plan_generation=plan.generation,
        document_id="preload-document",
        document_generation=0,
        source_path_identity="identity",
        profile_identity="",
        require_exact_raw_size=False,
        normal_load_token=0,
    )
    assert window.preload_controller.start_member(request)
    window._preload_worker_requests["preload-task"] = request
    window._preload_failed(
        "preload-task",
        _task_error("decode failed at /home/alice/private/preload.raw password=hunter2"),
    )

    snapshot = window.runtime_diagnostics_snapshot()

    assert snapshot.normal_load_stale_drop_count == 3
    assert snapshot.preload.failure_count == 1
    assert [failure.subsystem for failure in snapshot.recent_failures] == [
        "foreground-load",
        "preload",
    ]
    joined = " ".join(failure.message for failure in snapshot.recent_failures)
    assert "alice" not in joined
    assert "foreground.png" not in joined
    assert "preload.raw" not in joined
    assert "secret" not in joined
    assert "hunter2" not in joined
    assert "Traceback" not in joined
