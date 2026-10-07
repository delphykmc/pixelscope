"""Compose P5-F counters into the existing Copy Diagnostics snapshot."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any

from pixelscope.core.diagnostics import ExtensionDiagnosticsSection, RuntimeDiagnosticsSnapshot
from pixelscope.remote.iqa_transport_pool import ReusableIqaClientPool
from pixelscope.ui.lifecycle_hooks import OwnerCallback, WeakOwnerHook
from pixelscope.workers.iqa_thread_pool import remote_iqa_thread_pool


def install_remote_iqa_diagnostics(
    window: Any,
    transport_pool: ReusableIqaClientPool,
) -> None:
    """Extend the established immutable diagnostics read without starting work."""

    if getattr(window, "_p5f_original_runtime_diagnostics_snapshot", None) is not None:
        return
    original: Callable[[], RuntimeDiagnosticsSnapshot] = OwnerCallback(
        window.runtime_diagnostics_snapshot
    )
    window._p5f_original_runtime_diagnostics_snapshot = original

    def snapshot(_window: Any) -> RuntimeDiagnosticsSnapshot:
        base = original()
        transport = transport_pool.diagnostics
        pool = remote_iqa_thread_pool()
        section = ExtensionDiagnosticsSection(
            "Remote IQA",
            (
                f"Workers: active {pool.activeThreadCount()} / max {pool.maxThreadCount()}",
                f"HTTP clients created: {transport.clients_created}",
                f"HTTP leases reused: {transport.leases_reused}",
                f"HTTP active leases: {transport.active_leases}",
                f"HTTP max active leases: {transport.max_active_leases}",
                f"HTTP idle clients: {transport.idle_clients}",
                f"HTTP discarded clients: {transport.discarded_clients}",
                f"Transport closed: {'yes' if transport.closed else 'no'}",
            ),
        )
        return replace(base, extension_sections=base.extension_sections + (section,))

    window.runtime_diagnostics_snapshot = WeakOwnerHook(window, snapshot)
