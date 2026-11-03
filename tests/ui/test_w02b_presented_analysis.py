"""W02b UI producer contracts: no renderer-to-exporter numeric reconstruction."""
from __future__ import annotations

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
    panel.set_documents(
        [a, b, c], (a.document_id, b.document_id), RoiBounds(2, 3, 4, 5)
    )
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
        (a.document_id, a.generation), (b.document_id, b.generation)
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
        panel._request_signature, [], panel._histogram_specs,
        panel.last_results, task_id="superseded-worker",
    )
    assert panel.get_presented_analysis_token() == saved
    panel.shutdown()


def test_late_line_worker_cannot_republish_after_completion(
    qtbot: object,
) -> None:
    panel = LineProfilePanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    panel.set_documents_default(
        [_document("a.png", 7)], LineSelection(1, 1, 7, 1),
    )
    qtbot.waitUntil(
        lambda: panel.get_current_line_token() is not None,
        timeout=10000,
    )  # type: ignore[attr-defined]
    saved = panel.get_presented_line_token()
    panel._on_result(
        panel._request_signature, [], panel.last_results,
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
        "superseded-worker", key, metric_key, (cache, metrics, False), False,
    )
    assert panel.get_presented_difference_token() == saved
    panel.shutdown()
