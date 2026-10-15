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


def test_phase_timer_ignores_unrelated_documents(caplog: object, monkeypatch: object) -> None:
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


def test_worker_scope_rejects_speculative_and_stale_image_events(
    caplog: object, monkeypatch: object
) -> None:
    monkeypatch.setattr(load_latency_trace, "_ENABLED", True)  # type: ignore[attr-defined]
    load_latency_trace.begin("test")
    load_latency_trace.target("foreground")
    session = load_latency_trace.session_for("foreground")
    assert session is not None
    caplog.clear()  # type: ignore[attr-defined]

    with caplog.at_level(logging.WARNING, logger="pixelscope.core.load_latency_trace"):  # type: ignore[attr-defined]
        with load_latency_trace.worker_scope(None, None):
            load_latency_trace.mark("preload_must_be_hidden")
            load_latency_trace.PhaseTimer("preload").checkpoint("hidden")
        with load_latency_trace.worker_scope("foreground", session):
            load_latency_trace.mark("foreground_visible")
            load_latency_trace.PhaseTimer("foreground").checkpoint("visible")
        with load_latency_trace.worker_scope("foreground", session - 1):
            load_latency_trace.mark("stale_must_be_hidden")
    lines = caplog.text  # type: ignore[attr-defined]
    assert "foreground_visible" in lines
    assert "foreground.visible" in lines
    assert "preload_must_be_hidden" not in lines
    assert "stale_must_be_hidden" not in lines
    assert "preload.hidden" not in lines


def test_phase_timer_logs_thread_cpu_time(caplog: object, monkeypatch: object) -> None:
    monkeypatch.setattr(load_latency_trace, "_ENABLED", True)  # type: ignore[attr-defined]
    load_latency_trace.begin("test")

    with caplog.at_level(logging.WARNING, logger="pixelscope.core.load_latency_trace"):  # type: ignore[attr-defined]
        load_latency_trace.PhaseTimer("io.fromfile").checkpoint("returned")
    assert "cpu_step=" in caplog.text  # type: ignore[attr-defined]
    assert "cpu_scope=" in caplog.text  # type: ignore[attr-defined]
