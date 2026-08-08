from __future__ import annotations

import numpy as np

from pixelscope.core.image_document import ImageDocument
from pixelscope.core.roi import RoiBounds
from pixelscope.ui.comparison_analysis_panel import (
    ComparisonAnalysisPanel,
    automatic_histogram_spec,
)
from pixelscope.workers.task_worker import TaskWorker


def _rgb_document(name: str, value: int) -> ImageDocument:
    return ImageDocument.from_array(
        np.full((8, 10, 3), value, dtype=np.uint8),
        name,
    )


def _request_signature(
    panel: ComparisonAnalysisPanel,
    documents: list[ImageDocument],
    bounds: RoiBounds | None,
) -> tuple[object, ...]:
    specs = [automatic_histogram_spec(document) for document in documents]
    return panel._analysis_request_signature(documents, bounds, specs)


def test_repeated_identical_statistics_request_keeps_pending_timer_identity(
    qtbot: object,
) -> None:
    panel = ComparisonAnalysisPanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    documents = [_rgb_document("a.png", 10), _rgb_document("b.png", 20)]

    panel.set_documents(documents, None, "Full image")

    assert panel._worker is None
    assert panel._refresh_timer.isActive()
    pending_timer_id = panel._refresh_timer.timerId()
    assert pending_timer_id >= 0
    assert panel.status.text() == "Preparing analysis..."

    panel.set_documents(documents, None, "Full image")

    assert panel._worker is None
    assert panel._refresh_timer.isActive()
    assert panel._refresh_timer.timerId() == pending_timer_id
    assert panel.status.text() == "Preparing analysis..."
    panel.shutdown()


def test_repeated_identical_statistics_request_does_not_restart_completed_analysis(
    qtbot: object,
) -> None:
    panel = ComparisonAnalysisPanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    documents = [_rgb_document("a.png", 10), _rgb_document("b.png", 20)]

    panel.set_documents(documents, None, "Full image")
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(panel.last_results) == 2 and panel._worker is None,
        timeout=3000,
    )
    completed_results = panel.last_results
    assert panel.activity.isHidden()
    assert not panel._refresh_timer.isActive()

    panel.set_documents(documents, None, "Full image")

    assert panel.last_results is completed_results
    assert panel._worker is None
    assert not panel._refresh_timer.isActive()
    assert panel.activity.isHidden()


def test_repeated_identical_statistics_request_keeps_running_worker(qtbot: object) -> None:
    panel = ComparisonAnalysisPanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    documents = [_rgb_document("a.png", 10), _rgb_document("b.png", 20)]
    worker = TaskWorker(lambda: ())

    panel._documents = documents
    panel._bounds = None
    panel._request_signature = _request_signature(panel, documents, None)
    panel._worker = worker
    panel._set_activity("Calculating...", busy=True)

    panel.set_documents(documents, None, "Full image")

    assert panel._worker is worker
    assert not worker.is_cancelled
    assert not panel._refresh_timer.isActive()
    assert panel.status.text() == "Calculating..."
    panel.shutdown()


def test_changed_statistics_request_cancels_running_worker(qtbot: object) -> None:
    panel = ComparisonAnalysisPanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    documents = [_rgb_document("a.png", 10), _rgb_document("b.png", 20)]
    worker = TaskWorker(lambda: ())

    panel._documents = documents
    panel._bounds = None
    panel._request_signature = _request_signature(panel, documents, None)
    panel._worker = worker
    panel._set_activity("Calculating...", busy=True)

    panel.set_documents(documents, RoiBounds(0, 0, 5, 4), "Active ROI")

    assert worker.is_cancelled
    assert panel._refresh_timer.isActive()
    assert panel.status.text() == "Preparing analysis..."
    panel.shutdown()
