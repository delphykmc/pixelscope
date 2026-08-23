"""Compose P5-F counters into the existing Copy Diagnostics snapshot."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from types import MethodType
from typing import Any

from pixelscope.core.diagnostics import (
    RemoteIqaDiagnostics,
    RuntimeDiagnosticsSnapshot,
    WorkerPoolDiagnostics,
)
from pixelscope.remote.iqa_transport_pool import ReusableIqaClientPool
from pixelscope.workers.iqa_thread_pool import remote_iqa_thread_pool


def install_remote_iqa_diagnostics(
    window: Any,
    transport_pool: ReusableIqaClientPool,
) -> None:
    """Extend the established immutable diagnostics read without starting work."""

    if getattr(window, "_p5f_original_runtime_diagnostics_snapshot", None) is not None:
        return
    original: Callable[[], RuntimeDiagnosticsSnapshot] = window.runtime_diagnostics_snapshot
    window._p5f_original_runtime_diagnostics_snapshot = original

    def snapshot(_window: Any) -> RuntimeDiagnosticsSnapshot:
        base = original()
        transport = transport_pool.diagnostics
        pool = remote_iqa_thread_pool()
        remote = RemoteIqaDiagnostics(
            worker_pool=WorkerPoolDiagnostics(
                active_count=pool.activeThreadCount(),
                max_count=pool.maxThreadCount(),
            ),
            http_clients_created=transport.clients_created,
            http_leases_reused=transport.leases_reused,
            http_active_leases=transport.active_leases,
            http_max_active_leases=transport.max_active_leases,
            http_idle_clients=transport.idle_clients,
            http_discarded_clients=transport.discarded_clients,
            transport_closed=transport.closed,
        )
        return replace(base, remote_iqa=remote)

    window.runtime_diagnostics_snapshot = MethodType(snapshot, window)
