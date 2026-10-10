"""Reusable, Qt-free IQA provider conformance checks for public and PRIVATE SUB adapters.

This is a development/acceptance harness, not a production runtime worker.
The assertion set is intentionally provider-neutral. Private code imports this
module and supplies its own factory, intent and optional deterministic driver.
No enterprise server, credentials, environment lookup or pytest dependency.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pixelscope.remote.iqa_public_contract import (
    IqaAvailability,
    IqaExecutionPort,
    IqaJobReference,
    IqaJobSnapshot,
    IqaJobState,
    IqaProviderError,
    IqaResultAccessPort,
    IqaSubmissionIntent,
)


class IqaConformanceProvider(IqaExecutionPort, IqaResultAccessPort, Protocol):
    """Combined public ports used by a single reusable acceptance run."""


ProviderFactory = Callable[[Path], IqaConformanceProvider]
TerminalDriver = Callable[[IqaConformanceProvider, IqaJobReference], None]


@dataclass(frozen=True)
class ConformanceBudget:
    """Finite status polling budget, including the deterministic driver path."""

    max_polls: int = 12
    timeout_seconds: float = 5.0
    interval_seconds: float = 0.02

    def __post_init__(self) -> None:
        if self.max_polls < 1 or self.timeout_seconds <= 0 or self.interval_seconds < 0:
            raise ValueError("conformance polling budget must be positive and bounded")


@dataclass(frozen=True)
class ConformanceReport:
    """Small, non-sensitive execution evidence for downstream tests."""

    terminal_state: IqaJobState
    observed_states: tuple[IqaJobState, ...]
    result_id: str | None
    overlap_calls: int


def _check_snapshot(snapshot: IqaJobSnapshot, job: IqaJobReference) -> None:
    assert isinstance(snapshot, IqaJobSnapshot), "status must return IqaJobSnapshot"
    assert snapshot.reference == job, "provider returned another job reference"
    assert isinstance(snapshot.state, IqaJobState), "provider returned unknown state"
    progress = snapshot.progress
    if progress.completed is not None:
        assert progress.completed >= 0
    if progress.total is not None:
        assert progress.total >= 0
    if progress.completed is not None and progress.total is not None:
        assert progress.completed <= progress.total


def _wait_for_terminal(
    provider: IqaConformanceProvider,
    job: IqaJobReference,
    *,
    drive_to_terminal: TerminalDriver | None,
    budget: ConformanceBudget,
) -> tuple[IqaJobSnapshot, tuple[IqaJobState, ...]]:
    started = time.monotonic()
    observed: list[IqaJobState] = []
    previous_completed: int | None = None
    previous_state: IqaJobState | None = None

    for _ in range(budget.max_polls):
        if time.monotonic() - started >= budget.timeout_seconds:
            break
        if drive_to_terminal is not None:
            drive_to_terminal(provider, job)
        snapshot = provider.get_status(job)
        _check_snapshot(snapshot, job)
        # Allow QUEUED -> COMPLETED for providers with fast jobs; prohibit
        # terminal regressions and RUNNING -> QUEUED.
        if previous_state is IqaJobState.RUNNING:
            assert snapshot.state is not IqaJobState.QUEUED, "job state regressed"
        if previous_state is not None and previous_state.terminal:
            assert snapshot.state is previous_state, "terminal job state changed"
        progress = snapshot.progress.completed
        if previous_completed is not None and progress is not None:
            assert progress >= previous_completed, "completed progress regressed"
        if progress is not None:
            previous_completed = progress
        observed.append(snapshot.state)
        previous_state = snapshot.state
        if snapshot.state.terminal:
            return snapshot, tuple(observed)
        if drive_to_terminal is None:
            remaining = budget.timeout_seconds - (time.monotonic() - started)
            if remaining > 0:
                time.sleep(min(budget.interval_seconds, remaining))

    raise AssertionError(
        f"IQA provider failed to reach a terminal state in "
        f"{budget.max_polls} status polls / {budget.timeout_seconds:g}s"
    )


def run_provider_conformance(
    factory: ProviderFactory,
    *,
    workspace: Path,
    intent: IqaSubmissionIntent,
    drive_to_terminal: TerminalDriver | None = None,
    budget: ConformanceBudget | None = None,
    expected_terminal: IqaJobState = IqaJobState.COMPLETED,
    overlap_calls: int = 8,
) -> ConformanceReport:
    """Run the SAME execution/result assertions for fixture or injected provider.

    The factory owns configuration and can point at a synthetic/private adapter.
    When the provider progresses autonomously, omit `drive_to_terminal` and
    bounded status polling is used. Deterministic fixtures may supply a driver
    that advances one step per bounded poll. `get_status` itself is a synchronous
    provider method: adapters must impose their own per-call network timeout.

    Failure runs must reject result readiness. Successful runs must expose a
    materializable result, an openable normalized public result and an explicit
    source-resolution outcome. None of the checks assume fixture-specific IDs.
    """
    if expected_terminal not in (IqaJobState.COMPLETED, IqaJobState.FAILED):
        raise ValueError("conformance terminal must be completed or failed")
    if overlap_calls < 0 or overlap_calls > 64:
        raise ValueError("overlap_calls must be between 0 and 64")
    effective_budget = budget if budget is not None else ConformanceBudget()
    provider = factory(workspace)
    assert isinstance(provider, IqaExecutionPort), "provider lacks execution port"
    assert isinstance(provider, IqaResultAccessPort), "provider lacks result port"
    assert isinstance(provider.capabilities.can_cancel, bool)

    job = provider.submit(intent)
    assert isinstance(job, IqaJobReference)
    assert job.job_id, "provider returned empty job ID"

    if overlap_calls:
        # Concurrency matters because Client workers may share one provider
        # instance; status snapshots need not be identical during transitions.
        with ThreadPoolExecutor(max_workers=min(overlap_calls, 8)) as executor:
            snapshots = tuple(
                executor.map(lambda _: provider.get_status(job), range(overlap_calls))
            )
        for snapshot in snapshots:
            _check_snapshot(snapshot, job)

    terminal, observed = _wait_for_terminal(
        provider, job, drive_to_terminal=drive_to_terminal, budget=effective_budget
    )
    assert terminal.state is expected_terminal, "unexpected terminal IQA job state"

    if expected_terminal is IqaJobState.FAILED:
        try:
            provider.get_result_reference(job)
        except IqaProviderError:
            return ConformanceReport(terminal.state, observed, None, overlap_calls)
        raise AssertionError("failed job exposed a result reference")

    reference = provider.get_result_reference(job)
    assert reference.reference_id, "completed job returned empty result reference"
    materialized = provider.materialize(reference)
    assert materialized.succeeded, "completed result not materializable"
    assert materialized.availability in (IqaAvailability.AVAILABLE, IqaAvailability.PARTIAL)
    assert materialized.source is not None
    opened = provider.open_result(materialized.source)
    assert opened.succeeded, "completed result not openable"
    assert opened.availability in (IqaAvailability.AVAILABLE, IqaAvailability.PARTIAL)
    assert opened.result is not None
    result = opened.result
    assert result.result_id and result.scenes and result.variants and result.attributes

    spatial = result.load_spatial(result.scenes[0].scene_id)
    assert isinstance(spatial.availability, IqaAvailability)
    if spatial.succeeded:
        assert spatial.data is not None
    else:
        assert spatial.availability in (
            IqaAvailability.MISSING,
            IqaAvailability.FAILED,
        )
    first_source = result.scenes[0].sources[0].source
    resolved = provider.resolve_source(first_source.locator)
    assert isinstance(resolved.availability, IqaAvailability)
    if resolved.succeeded:
        assert resolved.source is not None
    else:
        assert resolved.availability is not IqaAvailability.AVAILABLE

    return ConformanceReport(terminal.state, observed, result.result_id, overlap_calls)
