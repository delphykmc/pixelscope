from __future__ import annotations

from pixelscope.core.diagnostics import (
    DifferenceCacheDiagnostics,
    RuntimeDiagnosticsSnapshot,
    SourceResidencyDiagnostics,
    WorkerDiagnostics,
    WorkerPoolDiagnostics,
    format_runtime_diagnostics,
)
from pixelscope.core.preload import PreloadDiagnostics


def test_promotion_counter_has_deterministic_copy_diagnostics_field() -> None:
    snapshot = RuntimeDiagnosticsSnapshot(
        source=SourceResidencyDiagnostics(0, 1024, 0, 0),
        difference=DifferenceCacheDiagnostics(0, 2048, 0),
        workers=WorkerDiagnostics(
            foreground_loads=WorkerPoolDiagnostics(1, 2),
            preload=WorkerPoolDiagnostics(0, 1),
        ),
        preload=PreloadDiagnostics(
            enabled=True,
            planned_target_count=0,
            active_worker_count=0,
            successful_retained_count=0,
            stale_drop_count=0,
            cancellation_request_count=0,
            failure_count=0,
            promotion_count=1,
        ),
        normal_load_stale_drop_count=0,
    )

    first = format_runtime_diagnostics(snapshot)
    second = format_runtime_diagnostics(snapshot)

    assert first == second
    assert "Promoted to foreground: 1" in first
    assert "Foreground loads: active 1 / max 2" in first
    assert "Preload: active 0 / max 1" in first
