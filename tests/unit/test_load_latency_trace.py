from __future__ import annotations

import logging
from time import perf_counter_ns

from pixelscope.core import load_latency_trace


def test_phase_timer_records_incremental_and_total_gui_durations(
    caplog: object, monkeypatch: object
) -> None:
    monkeypatch.setattr(load_latency_trace, "_ENABLED", True)  # type: ignore[attr-defined]
    monkeypatch.setattr(  # type: ignore[attr-defined]
        load_latency_trace, "_start_ns", perf_counter_ns()
    )
    monkeypatch.setattr(  # type: ignore[attr-defined]
        load_latency_trace, "_target_document_id", "first"
    )

    with caplog.at_level(logging.WARNING, logger="pixelscope.core.load_latency_trace"):  # type: ignore[attr-defined]
        trace = load_latency_trace.PhaseTimer("render.ready", document_id="first")
        trace.checkpoint("difference")
        trace.checkpoint("image_upload")

    output = caplog.text  # type: ignore[attr-defined]
    assert "render.ready.begin" in output
    assert "render.ready.difference step=" in output
    assert "render.ready.image_upload step=" in output
    assert "scope=" in output


def test_phase_timer_ignores_unrelated_documents(
    caplog: object, monkeypatch: object
) -> None:
    monkeypatch.setattr(load_latency_trace, "_ENABLED", True)  # type: ignore[attr-defined]
    monkeypatch.setattr(  # type: ignore[attr-defined]
        load_latency_trace, "_start_ns", perf_counter_ns()
    )
    monkeypatch.setattr(  # type: ignore[attr-defined]
        load_latency_trace, "_target_document_id", "first"
    )
    with caplog.at_level(logging.WARNING, logger="pixelscope.core.load_latency_trace"):  # type: ignore[attr-defined]
        trace = load_latency_trace.PhaseTimer("render.ready", document_id="other")
        trace.checkpoint("image_upload")
    assert not caplog.text  # type: ignore[attr-defined]
