"""W02b UI producer contracts: no renderer-to-exporter numeric reconstruction."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineSelection
from pixelscope.core.review_analysis import capture_presented_analysis
from pixelscope.core.roi import RoiBounds
from pixelscope.ui.analysis_export import _FrozenFeatureAdapter
from pixelscope.ui.comparison_analysis_panel import ComparisonAnalysisPanel
from pixelscope.ui.difference_panel import DifferencePanel
from pixelscope.ui.line_profile_panel import LineProfilePanel


def _document(name: str, level: int) -> ImageDocument:
    return ImageDocument.from_array(
        np.full((10, 12, 3), level, dtype=np.uint8),
        name,
    )


def test_histogram_native_series_token_and_roi_generation_staleness(
    qtbot: object,
) -> None:
    panel = ComparisonAnalysisPanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    doc = _document("hist-a.png", 5)
    roi = RoiBounds(1, 2, 6, 5)
    panel.set_documents_default([doc], roi)
    qtbot.waitUntil(
        lambda: panel.get_current_histogram_token() is not None
        and panel.get_current_histogram_token() == panel.get_presented_histogram_token(),
        timeout=10000,
    )  # type: ignore[attr-defined]
    adapter = _FrozenFeatureAdapter(panel, "histogram")
    token = adapter.get_presented_analysis_token()
    captured = capture_presented_analysis(adapter, token)
    assert captured.snapshot is not None
    assert captured.snapshot.token.roi_ref == (1, 2, 6, 5)
    assert captured.snapshot.series
    assert all(item.kind == "histogram" for item in captured.snapshot.series)
    assert sum(int(v) for v in captured.snapshot.series[0].values) == 30

    panel.set_documents_default([doc], RoiBounds(2, 2, 6, 5))
    assert capture_presented_analysis(adapter, token).snapshot is None
    qtbot.waitUntil(
        lambda: panel.get_current_histogram_token() is not None
        and panel.get_current_histogram_token() == panel.get_presented_histogram_token(),
        timeout=10000,
    )  # type: ignore[attr-defined]
    assert panel.get_presented_histogram_token() != token
    doc.generation += 1
    assert adapter.get_current_analysis_token() is None
    panel.shutdown()


def test_line_native_profile_freezes_before_plot_mode_switch(
    qtbot: object,
) -> None:
    panel = LineProfilePanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    doc = _document("line-a.png", 17)
    line = LineSelection(1, 4, 7, 4)
    panel.set_documents_default([doc], line)
    qtbot.waitUntil(
        lambda: panel.get_current_line_token() is not None
        and panel.get_current_line_token() == panel.get_presented_line_token(),
        timeout=10000,
    )  # type: ignore[attr-defined]
    adapter = _FrozenFeatureAdapter(panel, "line")
    token = adapter.get_presented_analysis_token()
    capture = capture_presented_analysis(adapter, token)
    assert capture.snapshot is not None
    assert capture.snapshot.presentation[0] == ("line_ref", "1:4:7:4")
    assert capture.snapshot.series
    assert all(series.kind == "line" for series in capture.snapshot.series)
    assert capture.snapshot.series[0].coordinates[0] == 0.0
    assert all(value == 17 for value in capture.snapshot.series[0].values)

    panel.y_mode.setCurrentText("Normalized 0–1")
    assert adapter.get_presented_analysis_token() != token
    assert capture_presented_analysis(adapter, token).snapshot is None
    panel.clear_selection()
    assert adapter.get_current_analysis_token() is None
    panel.shutdown()


def test_difference_snapshot_follows_explicit_pair_and_roi(
    qtbot: object,
) -> None:
    panel = DifferencePanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    a, b, c = (
        _document("diff-a.png", 10),
        _document("diff-b.png", 15),
        _document("diff-c.png", 20),
    )
    panel.set_documents([a, b, c], (a.document_id, b.document_id), RoiBounds(2, 3, 4, 5))
    panel.calculate_difference()
    qtbot.waitUntil(
        lambda: panel.get_current_difference_token() is not None
        and panel.get_current_difference_token() == panel.get_presented_difference_token(),
        timeout=15000,
    )  # type: ignore[attr-defined]
    adapter = _FrozenFeatureAdapter(panel, "difference")
    token = adapter.get_presented_analysis_token()
    capture = capture_presented_analysis(adapter, token)
    assert capture.snapshot is not None
    assert capture.snapshot.token.source_documents == (
        (a.document_id, a.generation),
        (b.document_id, b.generation),
    )
    assert capture.snapshot.token.roi_ref == (2, 3, 4, 5)
    assert capture.snapshot.token.difference_cache_key is not None
    assert capture.snapshot.measurements[0].metric == "MAE"
    assert capture.snapshot.measurements[0].value == 5.0

    panel.b_selector.setCurrentIndex(panel.b_selector.findData(c.document_id))
    assert capture_presented_analysis(adapter, token).snapshot is None
    panel.shutdown()


def test_difference_source_generation_invalidates_frozen_token(
    qtbot: object,
) -> None:
    panel = DifferencePanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    a, b = _document("a.png", 1), _document("b.png", 2)
    panel.set_documents([a, b], (a.document_id, b.document_id))
    panel.calculate_difference()
    qtbot.waitUntil(
        lambda: panel.get_current_difference_token() is not None,
        timeout=15000,
    )  # type: ignore[attr-defined]
    adapter = _FrozenFeatureAdapter(panel, "difference")
    token = adapter.get_presented_analysis_token()
    b.generation += 1
    assert capture_presented_analysis(adapter, token).snapshot is None
    panel.shutdown()


def test_late_statistics_worker_cannot_republish_after_completion(
    qtbot: object,
) -> None:
    panel = ComparisonAnalysisPanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    panel.set_documents_default([_document("a.png", 7)], None)
    qtbot.waitUntil(
        lambda: panel.get_current_analysis_token() is not None,
        timeout=10000,
    )  # type: ignore[attr-defined]
    saved = panel.get_presented_analysis_token()
    panel._on_result(
        panel._request_signature,
        [],
        panel._histogram_specs,
        panel.last_results,
        task_id="superseded-worker",
    )
    assert panel.get_presented_analysis_token() == saved
    panel.shutdown()


def test_late_line_worker_cannot_republish_after_completion(
    qtbot: object,
) -> None:
    panel = LineProfilePanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    panel.set_documents_default(
        [_document("a.png", 7)],
        LineSelection(1, 1, 7, 1),
    )
    qtbot.waitUntil(
        lambda: panel.get_current_line_token() is not None,
        timeout=10000,
    )  # type: ignore[attr-defined]
    saved = panel.get_presented_line_token()
    panel._on_result(
        panel._request_signature,
        [],
        panel.last_results,
        task_id="superseded-worker",
    )
    assert panel.get_presented_line_token() == saved
    panel.shutdown()


def test_late_difference_worker_cannot_republish_after_completion(
    qtbot: object,
) -> None:
    panel = DifferencePanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    a, b = _document("a.png", 3), _document("b.png", 6)
    panel.set_documents([a, b], (a.document_id, b.document_id))
    panel.calculate_difference()
    qtbot.waitUntil(
        lambda: panel.get_current_difference_token() is not None,
        timeout=15000,
    )  # type: ignore[attr-defined]
    saved = panel.get_presented_difference_token()
    cache = panel.cached_result_for_current()
    metrics = panel.last_result
    key = panel._cache_key()
    metric_key = panel._metric_key()
    assert cache is not None and metrics is not None
    assert key is not None and metric_key is not None
    panel._on_result(
        "superseded-worker",
        key,
        metric_key,
        (cache, metrics, False),
        False,
    )
    assert panel.get_presented_difference_token() == saved
    panel.shutdown()


def test_background_difference_map_does_not_authorize_implicit_capture(
    qtbot: object,
) -> None:
    panel = DifferencePanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    first, second = _document("a.png", 4), _document("b.png", 8)
    panel.set_documents([first, second], (first.document_id, second.document_id))
    panel.calculate_difference(publish_result=False)
    qtbot.waitUntil(
        lambda: panel.last_result is not None and panel._worker is None,
        timeout=15000,
    )  # type: ignore[attr-defined]
    difference_map = panel.cached_result_for_current()
    assert difference_map is not None
    selected = panel._selected_absolute(difference_map, panel.channel.currentText())
    panel._request_preview_render(difference_map, selected, publish_result=False)
    qtbot.waitUntil(
        lambda: panel._preview_worker is None and panel._preview_value is not None,
        timeout=15000,
    )  # type: ignore[attr-defined]
    assert panel.get_current_difference_token() is None
    assert panel.get_presented_difference_token() is None

    # Only the existing explicit Calculate signal authorizes the presentation.
    panel.calculate_difference()
    qtbot.waitUntil(
        lambda: panel.get_current_difference_token() is not None,
        timeout=15000,
    )  # type: ignore[attr-defined]
    panel.shutdown()


def test_line_pending_new_request_never_relabels_old_series(
    qtbot: object,
) -> None:
    """A control redraw during a new request must not publish old line samples."""
    panel = LineProfilePanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    doc = _document("line.png", 19)
    panel.set_documents_default([doc], LineSelection(1, 1, 7, 1))
    qtbot.waitUntil(
        lambda: panel.get_current_line_token() is not None,
        timeout=10000,
    )  # type: ignore[attr-defined]
    previous = panel.last_results
    old_token = panel.get_presented_line_token()
    assert old_token is not None

    # Simulate a different request becoming authoritative before its
    # asynchronous calculate has published any results.
    panel._selection = LineSelection(2, 4, 9, 4)
    signature = panel._line_request_signature()
    panel._begin_line_request(signature)
    assert panel.last_results is previous
    panel.y_mode.setCurrentText("Normalized 0–1")
    assert panel.get_current_line_token() is None
    assert panel.get_presented_line_token() is None
    adapter = _FrozenFeatureAdapter(panel, "line")
    assert capture_presented_analysis(adapter, old_token).snapshot is None
    panel.shutdown()


def test_native_line_series_domain_is_not_display_transform_domain(
    qtbot: object,
) -> None:
    panel = LineProfilePanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    baseline, target = _document("ref.png", 128), _document("target.png", 64)
    panel.set_documents_default(
        [baseline, target],
        LineSelection(1, 2, 9, 2),
        reference_priority_ids=(baseline.document_id,),
    )
    qtbot.waitUntil(
        lambda: panel.get_current_line_token() is not None,
        timeout=10000,
    )  # type: ignore[attr-defined]
    adapter = _FrozenFeatureAdapter(panel, "line")

    panel.y_mode.setCurrentText("Normalized 0–1")
    normalized_token = adapter.get_presented_analysis_token()
    normalized = capture_presented_analysis(adapter, normalized_token)
    assert normalized.snapshot is not None
    assert normalized.snapshot.token.domain == "native"
    assert dict(normalized.snapshot.presentation)["y_mode"] == "normalized"
    assert all(v == 128 for v in normalized.snapshot.series[0].values)
    assert all(v == 64 for v in normalized.snapshot.series[-1].values)

    panel.y_mode.setCurrentText("Difference from reference")
    difference_token = adapter.get_presented_analysis_token()
    difference = capture_presented_analysis(adapter, difference_token)
    assert difference.snapshot is not None
    assert difference.snapshot.token.domain == "native"
    assert dict(difference.snapshot.presentation)["y_mode"] == "reference-delta"
    assert all(v == 128 for v in difference.snapshot.series[0].values)
    assert all(v == 64 for v in difference.snapshot.series[-1].values)
    panel.shutdown()


def test_feature_availability_reports_pending_cancelled_and_stale(
    qtbot: object,
) -> None:
    from pixelscope.workers.task_worker import TaskWorker

    panel = LineProfilePanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    panel.set_documents_default([_document("a.png", 10)], LineSelection(1, 1, 7, 1))
    qtbot.waitUntil(
        lambda: panel.get_current_line_token() is not None,
        timeout=10000,
    )  # type: ignore[attr-defined]
    adapter = _FrozenFeatureAdapter(panel, "line")
    ready = adapter.get_presented_analysis_token()
    assert adapter.availability(ready, adapter.get_current_analysis_token()).state == "captured"
    panel._selection = LineSelection(2, 2, 8, 2)
    panel._begin_line_request(panel._line_request_signature())
    pending_worker = TaskWorker(lambda: None)
    panel._worker = pending_worker
    assert adapter.availability(None, adapter.get_current_analysis_token()).state == "pending"
    pending_worker.cancel()
    assert adapter.availability(None, adapter.get_current_analysis_token()).state == "cancelled"
    panel._worker = None
    assert adapter.availability(None, adapter.get_current_analysis_token()).state == "stale"
    panel.shutdown()


def test_difference_explicit_full_roi_background_does_not_renew_permission(
    qtbot: object,
) -> None:
    """A prior explicit full-image presentation cannot authorize ROI metrics.

    The native Difference map/preview is deliberately shared by Full and ROI,
    while the metric request provenance must be separate.
    """
    panel = DifferencePanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    first, second = _document("explicit-a.png", 10), _document("explicit-b.png", 30)
    panel.set_documents([first, second], (first.document_id, second.document_id))
    published: list[object] = []
    panel.result_ready.connect(lambda *_args: published.append(True))  # type: ignore[attr-defined]

    panel.calculate_difference()
    qtbot.waitUntil(
        lambda: panel.get_current_difference_token() is not None
        and panel.get_current_difference_token() == panel.get_presented_difference_token()
        and panel._worker is None,
        timeout=15000,
    )  # type: ignore[attr-defined]
    assert len(published) == 1
    adapter = _FrozenFeatureAdapter(panel, "difference")
    full_token = adapter.get_presented_analysis_token()
    assert full_token.roi_ref is None
    assert capture_presented_analysis(adapter, full_token).snapshot is not None

    roi = RoiBounds(2, 3, 4, 5)
    panel.set_active_roi(roi)
    # Cached map is still valid; only ROI metrics are refreshed in the background.
    qtbot.waitUntil(
        lambda: panel.last_result is not None and panel._worker is None,
        timeout=15000,
    )  # type: ignore[attr-defined]
    assert len(published) == 1  # no ROI-specific result_ready
    assert panel._presented_metric_key == panel._metric_key()
    assert panel.get_current_difference_token() is None
    assert panel.get_presented_difference_token() is None
    assert capture_presented_analysis(adapter, full_token).snapshot is None
    assert (
        adapter.availability(
            adapter.get_presented_analysis_token(),
            adapter.get_current_analysis_token(),
        ).state
        == "stale"
    )

    # The user explicitly authorizes presentation of those exact ROI metrics.
    panel.calculate_difference()
    qtbot.waitUntil(
        lambda: panel.get_current_difference_token() is not None
        and panel.get_current_difference_token() == panel.get_presented_difference_token(),
        timeout=15000,
    )  # type: ignore[attr-defined]
    assert len(published) == 2
    roi_token = adapter.get_presented_analysis_token()
    assert roi_token.roi_ref == (2, 3, 4, 5)
    assert capture_presented_analysis(adapter, roi_token).snapshot is not None

    # Returning to a previously explicit full-image scope via cached metrics
    # must not reuse the old event's token/request_id.
    panel.set_active_roi(None)
    assert len(published) == 2
    assert panel.get_current_difference_token() is None
    assert capture_presented_analysis(adapter, roi_token).snapshot is None
    panel.shutdown()


def test_difference_delayed_explicit_preview_cannot_authorize_new_roi(
    qtbot: object,
    monkeypatch: object,
) -> None:
    """Preview identity excludes ROI; the result_ready permission must not."""
    panel = DifferencePanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    first, second = _document("preview-a.png", 9), _document("preview-b.png", 20)
    panel.set_documents([first, second], (first.document_id, second.document_id))
    observed: list[object] = []
    panel.result_ready.connect(lambda *_args: observed.append(True))  # type: ignore[attr-defined]
    panel.calculate_difference()
    qtbot.waitUntil(
        lambda: panel.get_current_difference_token() is not None and panel._worker is None,
        timeout=15000,
    )  # type: ignore[attr-defined]
    assert len(observed) == 1

    cached = panel.cached_result_for_current()
    assert cached is not None
    selected = panel._selected_absolute(cached, panel.channel.currentText())
    panel.gain.setValue(2)
    panel._display_timer.stop()
    monkeypatch.setattr(panel, "_pool", SimpleNamespace(start=lambda _worker: None))
    metric_key = panel._metric_key()
    request_id = panel._difference_request_id
    panel._request_preview_render(cached, selected, publish_result=True)
    pending = panel._preview_worker
    assert pending is not None
    preview_key = panel._preview_cache_key(cached)
    serial = panel._preview_request_serial

    panel.set_active_roi(RoiBounds(2, 3, 4, 5))
    # Background metric worker is intentionally not started by the fixture.
    assert panel._metric_key() != metric_key
    preview = np.zeros(selected.shape[:2], dtype=np.uint8)
    panel._preview_succeeded(
        pending.task_id,
        preview,
        request_serial=serial,
        expected_key=preview_key,
        expected_map=cached,
        expected_metric_key=metric_key,
        expected_metric_request_id=request_id,
        title="old ROI preview",
        selected=selected,
        snapshot=panel._build_sampling_snapshot(selected),
        publish_result=True,
    )
    assert len(observed) == 1
    assert panel.get_current_difference_token() is None
    panel.shutdown()
