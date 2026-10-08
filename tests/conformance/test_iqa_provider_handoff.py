from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from pixelscope.remote.iqa_public_contract import (
    IQA_PUBLIC_CONTRACT_REVISION,
    IqaAvailability,
    IqaExecutionPort,
    IqaJobState,
    IqaProviderError,
    IqaResultAccessPort,
    IqaSubmissionIntent,
    IqaSubmissionScene,
    IqaSubmissionSource,
    IqaVariant,
)
from pixelscope.remote.iqa_public_fixture import FixtureIqaProvider, IqaFixtureProfile


def _intent(tmp_path: Path) -> IqaSubmissionIntent:
    variants = (IqaVariant("reference", "Reference"), IqaVariant("candidate", "Candidate"))
    return IqaSubmissionIntent(
        "conformance",
        variants,
        (
            IqaSubmissionScene(
                "scene_0001",
                (
                    IqaSubmissionSource("reference", tmp_path / "reference.png"),
                    IqaSubmissionSource("candidate", tmp_path / "candidate.png"),
                ),
            ),
        ),
    )


def test_public_contract_revision_and_protocol_shape(tmp_path: Path) -> None:
    provider = FixtureIqaProvider(tmp_path / "provider", IqaFixtureProfile.MINIMAL)

    assert IQA_PUBLIC_CONTRACT_REVISION == 1
    assert isinstance(provider, IqaExecutionPort)
    assert isinstance(provider, IqaResultAccessPort)
    assert provider.capabilities.can_cancel


def test_same_provider_instance_accepts_overlapping_status_calls(tmp_path: Path) -> None:
    provider = FixtureIqaProvider(tmp_path / "provider", IqaFixtureProfile.MINIMAL)
    job = provider.submit(_intent(tmp_path))

    with ThreadPoolExecutor(max_workers=8) as executor:
        snapshots = tuple(executor.map(lambda _index: provider.get_status(job), range(32)))

    assert {snapshot.reference for snapshot in snapshots} == {job}
    assert {snapshot.state for snapshot in snapshots} == {IqaJobState.QUEUED}


def test_execution_cancel_and_published_result_round_trip(tmp_path: Path) -> None:
    provider = FixtureIqaProvider(tmp_path / "provider", IqaFixtureProfile.MINIMAL)

    cancelled_job = provider.submit(_intent(tmp_path))
    cancelled = provider.cancel(cancelled_job)
    assert cancelled.state is IqaJobState.CANCELLED
    assert cancelled.state.terminal
    assert provider.get_status(cancelled_job).state is IqaJobState.CANCELLED

    completed_job = provider.submit(_intent(tmp_path))
    assert provider.advance(completed_job).state is IqaJobState.RUNNING
    assert provider.advance(completed_job).state is IqaJobState.COMPLETED

    reference = provider.get_result_reference(completed_job)
    materialized = provider.materialize(reference)
    assert materialized.succeeded
    assert materialized.source is not None
    assert materialized.availability is IqaAvailability.AVAILABLE

    opened = provider.open_result(materialized.source)
    assert opened.succeeded
    assert opened.result is not None
    assert opened.result.result_id == "fixture-minimal"
    assert opened.result.load_spatial(opened.result.scenes[0].scene_id).succeeded

    locator = opened.result.scenes[0].sources[0].source.locator
    source = provider.resolve_source(locator)
    assert source.availability is IqaAvailability.MISSING
    assert not source.succeeded
    assert source.diagnostics[0].code == "fixture_source_not_materialized"


def test_failure_profile_exposes_terminal_failure_without_result_reference(
    tmp_path: Path,
) -> None:
    provider = FixtureIqaProvider(tmp_path / "provider", IqaFixtureProfile.FAILURE)
    job = provider.submit(_intent(tmp_path))

    assert provider.advance(job).state is IqaJobState.RUNNING
    failed = provider.advance(job)
    assert failed.state is IqaJobState.FAILED
    assert failed.state.terminal

    with pytest.raises(IqaProviderError, match="result is not available"):
        provider.get_result_reference(job)
