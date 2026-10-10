"""Issue #156 U8: SAME reusable conformance checks for injected providers."""

from __future__ import annotations

from pathlib import Path

import pytest

from pixelscope.remote.iqa_provider_conformance import (
    ConformanceBudget,
    IqaConformanceProvider,
    run_provider_conformance,
)
from pixelscope.remote.iqa_public_contract import (
    IqaExecutionCapabilities,
    IqaJobReference,
    IqaJobSnapshot,
    IqaJobState,
    IqaProviderError,
    IqaResultOpenOutcome,
    IqaResultReference,
    IqaResultSource,
    IqaResultSourceOutcome,
    IqaSourceLocator,
    IqaSourceResolutionOutcome,
    IqaSubmissionIntent,
    IqaSubmissionScene,
    IqaSubmissionSource,
    IqaVariant,
)
from pixelscope.remote.iqa_public_fixture import FixtureIqaProvider, IqaFixtureProfile


def _intent(tmp_path: Path) -> IqaSubmissionIntent:
    return IqaSubmissionIntent(
        "provider-conformance",
        (IqaVariant("A", "Reference"), IqaVariant("B", "Candidate")),
        (
            IqaSubmissionScene(
                "scene_0001",
                (
                    IqaSubmissionSource("A", tmp_path / "a.png"),
                    IqaSubmissionSource("B", tmp_path / "b.png"),
                ),
            ),
        ),
    )


def _fixture_factory(root: Path) -> IqaConformanceProvider:
    return FixtureIqaProvider(root, IqaFixtureProfile.MINIMAL)


def _fixture_driver(provider: IqaConformanceProvider, job: IqaJobReference) -> None:
    assert isinstance(provider, FixtureIqaProvider)
    provider.advance(job)


class PollingSyntheticAdapter:
    """A separate synthetic provider that advances in status polling.

    It deliberately does not offer an `advance` method. The same public
    conformance runner therefore validates the optional *no-driver* path.
    It is entirely local and does not connect to any service.
    """

    def __init__(self, root: Path, *, stalled: bool = False) -> None:
        self._delegate = FixtureIqaProvider(root, IqaFixtureProfile.MINIMAL)
        self._stalled = stalled

    @property
    def capabilities(self) -> IqaExecutionCapabilities:
        return self._delegate.capabilities

    def submit(self, intent: IqaSubmissionIntent) -> IqaJobReference:
        return self._delegate.submit(intent)

    def get_status(self, reference: IqaJobReference) -> IqaJobSnapshot:
        snapshot = self._delegate.get_status(reference)
        if not snapshot.state.terminal and not self._stalled:
            self._delegate.advance(reference)
        return snapshot

    def get_result_reference(self, reference: IqaJobReference) -> IqaResultReference:
        return self._delegate.get_result_reference(reference)

    def cancel(self, reference: IqaJobReference) -> IqaJobSnapshot:
        return self._delegate.cancel(reference)

    def materialize(self, reference: IqaResultReference) -> IqaResultSourceOutcome:
        return self._delegate.materialize(reference)

    def open_result(self, source: IqaResultSource) -> IqaResultOpenOutcome:
        return self._delegate.open_result(source)

    def resolve_source(self, locator: IqaSourceLocator) -> IqaSourceResolutionOutcome:
        return self._delegate.resolve_source(locator)


def test_fixture_runs_reusable_conformance_with_driver(tmp_path: Path) -> None:
    report = run_provider_conformance(
        _fixture_factory,
        workspace=tmp_path / "fixture",
        intent=_intent(tmp_path),
        drive_to_terminal=_fixture_driver,
        budget=ConformanceBudget(max_polls=4, timeout_seconds=2),
    )
    assert report.terminal_state is IqaJobState.COMPLETED
    assert report.observed_states == (IqaJobState.RUNNING, IqaJobState.COMPLETED)
    assert report.result_id == "fixture-minimal"
    assert report.overlap_calls == 8


def test_injected_synthetic_provider_runs_identical_checks_without_driver(
    tmp_path: Path,
) -> None:
    report = run_provider_conformance(
        lambda root: PollingSyntheticAdapter(root),
        workspace=tmp_path / "synthetic-adapter",
        intent=_intent(tmp_path),
        budget=ConformanceBudget(max_polls=4, timeout_seconds=2, interval_seconds=0),
        overlap_calls=0,
    )
    assert report.terminal_state is IqaJobState.COMPLETED
    assert report.observed_states == (
        IqaJobState.QUEUED,
        IqaJobState.RUNNING,
        IqaJobState.COMPLETED,
    )
    assert report.result_id == "fixture-minimal"


def test_injected_synthetic_provider_also_handles_concurrent_status_calls(
    tmp_path: Path,
) -> None:
    """The adapter is not the fixture class, yet passes overlapping port calls."""
    report = run_provider_conformance(
        lambda root: PollingSyntheticAdapter(root),
        workspace=tmp_path / "concurrent-adapter",
        intent=_intent(tmp_path),
        budget=ConformanceBudget(max_polls=4, timeout_seconds=2, interval_seconds=0),
        overlap_calls=8,
    )
    assert report.overlap_calls == 8
    assert report.terminal_state is IqaJobState.COMPLETED
    assert report.result_id == "fixture-minimal"


def test_bounded_conformance_fails_closed_on_never_terminal_provider(
    tmp_path: Path,
) -> None:
    with pytest.raises(AssertionError, match="3 status polls"):
        run_provider_conformance(
            lambda root: PollingSyntheticAdapter(root, stalled=True),
            workspace=tmp_path / "stalled",
            intent=_intent(tmp_path),
            budget=ConformanceBudget(max_polls=3, timeout_seconds=2, interval_seconds=0),
            overlap_calls=0,
        )


def test_failed_fixture_runs_same_terminal_and_result_readiness_contract(
    tmp_path: Path,
) -> None:
    report = run_provider_conformance(
        lambda root: FixtureIqaProvider(root, IqaFixtureProfile.FAILURE),
        workspace=tmp_path / "failed",
        intent=_intent(tmp_path),
        drive_to_terminal=_fixture_driver,
        expected_terminal=IqaJobState.FAILED,
        overlap_calls=0,
    )
    assert report.terminal_state is IqaJobState.FAILED
    assert report.result_id is None
    assert report.observed_states == (IqaJobState.RUNNING, IqaJobState.FAILED)


@pytest.mark.parametrize(
    ("max_polls", "seconds", "interval"),
    [(0, 1.0, 0.0), (2, 0.0, 0.0), (2, 1.0, -0.01)],
)
def test_invalid_budget_rejected(
    max_polls: int, seconds: float, interval: float
) -> None:
    with pytest.raises(ValueError, match="polling budget"):
        ConformanceBudget(
            max_polls=max_polls,
            timeout_seconds=seconds,
            interval_seconds=interval,
        )


def test_invalid_expectations_and_overlap_budget_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="terminal"):
        run_provider_conformance(
            _fixture_factory,
            workspace=tmp_path,
            intent=_intent(tmp_path),
            expected_terminal=IqaJobState.CANCELLED,
        )
    with pytest.raises(ValueError, match="overlap_calls"):
        run_provider_conformance(
            _fixture_factory, workspace=tmp_path, intent=_intent(tmp_path), overlap_calls=65
        )


def test_fixture_failure_still_reports_public_provider_error(tmp_path: Path) -> None:
    provider = FixtureIqaProvider(tmp_path, IqaFixtureProfile.FAILURE)
    job = provider.submit(_intent(tmp_path))
    provider.advance(job)
    provider.advance(job)
    with pytest.raises(IqaProviderError, match="result is not available"):
        provider.get_result_reference(job)
