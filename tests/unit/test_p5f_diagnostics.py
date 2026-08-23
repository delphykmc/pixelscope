from __future__ import annotations

from pixelscope.core.diagnostics import (
    DifferenceCacheDiagnostics,
    RemoteIqaDiagnostics,
    RuntimeDiagnosticsSnapshot,
    SourceResidencyDiagnostics,
    WorkerDiagnostics,
    WorkerPoolDiagnostics,
    format_runtime_diagnostics,
)
from pixelscope.core.preload import PreloadDiagnostics


def test_remote_iqa_diagnostics_extend_existing_copy_surface() -> None:
    snapshot = RuntimeDiagnosticsSnapshot(
        source=SourceResidencyDiagnostics(0, 1024, 0, 0),
        difference=DifferenceCacheDiagnostics(0, 512, 0),
        workers=WorkerDiagnostics(
            foreground_loads=WorkerPoolDiagnostics(0, 2),
            preload=WorkerPoolDiagnostics(0, 1),
        ),
        preload=PreloadDiagnostics(
            enabled=True,
            planned_target_count=0,
            active_worker_count=0,
            promotion_count=0,
            successful_retained_count=0,
            stale_drop_count=0,
            cancellation_request_count=0,
            failure_count=0,
        ),
        normal_load_stale_drop_count=0,
        remote_iqa=RemoteIqaDiagnostics(
            worker_pool=WorkerPoolDiagnostics(1, 2),
            http_clients_created=2,
            http_leases_reused=5,
            http_active_leases=1,
            http_max_active_leases=2,
            http_idle_clients=1,
            http_discarded_clients=0,
            transport_closed=False,
        ),
    )

    text = format_runtime_diagnostics(snapshot)

    assert "Remote IQA" in text
    assert "Workers: active 1 / max 2" in text
    assert "HTTP clients created: 2" in text
    assert "HTTP leases reused: 5" in text
    assert "HTTP idle clients: 1" in text
    assert "Transport closed: no" in text
