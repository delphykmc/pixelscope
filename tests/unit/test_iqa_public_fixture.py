from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from pixelscope.remote.iqa_explorer import IqaExplorerModel
from pixelscope.remote.iqa_public_contract import (
    IqaAvailability,
    IqaExecutionPort,
    IqaJobState,
    IqaProviderError,
    IqaResultAccessPort,
    IqaResultCompleteness,
    IqaSubmissionIntent,
    IqaSubmissionScene,
    IqaSubmissionSource,
    IqaVariant,
)
from pixelscope.remote.iqa_public_fixture import (
    SYNTHETIC_IQA_PROFILES,
    FixtureIqaProvider,
    SyntheticIqaProfile,
    build_synthetic_iqa_result,
)


def _intent(tmp_path: Path) -> IqaSubmissionIntent:
    return IqaSubmissionIntent(
        "synthetic_pair",
        (IqaVariant("A", "A"), IqaVariant("B", "B")),
        (
            IqaSubmissionScene(
                "scene_0000",
                (
                    IqaSubmissionSource("A", tmp_path / "a.png"),
                    IqaSubmissionSource("B", tmp_path / "b.png"),
                ),
            ),
        ),
    )


@pytest.mark.parametrize(
    ("profile", "attribute_count", "variant_count", "scene_count"),
    [
        (SyntheticIqaProfile.MINIMAL, 2, 2, 3),
        (SyntheticIqaProfile.NORMAL, 10, 3, 12),
        (SyntheticIqaProfile.LARGE, 32, 16, 128),
        (SyntheticIqaProfile.PARTIAL, 10, 3, 12),
    ],
)
def test_public_fixture_profiles_are_deterministic_and_company_neutral(
    tmp_path: Path,
    profile: SyntheticIqaProfile,
    attribute_count: int,
    variant_count: int,
    scene_count: int,
) -> None:
    result = build_synthetic_iqa_result(tmp_path / profile.value, profile)

    assert result is not None
    assert len(result.attributes) == attribute_count
    assert len(result.variants) == variant_count
    assert len(result.scenes) == scene_count
    assert result.result_id == f"synthetic-{profile.value}"
    assert "server" not in repr(result).lower()
    assert "storage_root" not in repr(result).lower()
    assert "auth" not in repr(result).lower()


def test_large_fixture_keeps_spatial_data_lazy_until_reference_is_requested(
    tmp_path: Path,
) -> None:
    result = build_synthetic_iqa_result(tmp_path / "large", SyntheticIqaProfile.LARGE)
    assert result is not None
    spatial = cast(Any, result.spatial_access)
    assert spatial.load_count == 0

    model = IqaExplorerModel(result)
    first_variant = result.variants[0].variant_id
    first_attribute = result.attributes[0].attribute_id
    assert model.absolute_dataset_stat(first_variant, first_attribute).valid
    assert spatial.load_count == 0

    prepared = model.prepare_reference(first_variant)
    assert prepared.reference_ready(first_variant)
    assert spatial.load_count == len(result.scenes)


def test_partial_fixture_exposes_missing_measurement_and_public_diagnostic(
    tmp_path: Path,
) -> None:
    result = build_synthetic_iqa_result(tmp_path / "partial", SyntheticIqaProfile.PARTIAL)
    assert result is not None
    assert result.completeness is IqaResultCompleteness.PARTIAL
    assert result.diagnostics[0].code == "synthetic_partial_result"

    last_scene = result.scenes[-1]
    last_source = last_scene.sources[-1]
    last_attribute = result.attributes[-1]
    summary = last_source.summary(last_attribute.attribute_id)
    assert summary.availability is IqaAvailability.MISSING
    assert not summary.valid
    assert summary.reason == "synthetic_missing_measurement"


def test_fixture_provider_exercises_public_execution_result_and_resolver_ports(
    tmp_path: Path,
) -> None:
    provider = FixtureIqaProvider(tmp_path / "normal", SyntheticIqaProfile.NORMAL)
    assert isinstance(provider, IqaExecutionPort)
    assert isinstance(provider, IqaResultAccessPort)
    assert provider.capabilities.can_cancel

    job = provider.submit(_intent(tmp_path))
    assert provider.get_status(job).state is IqaJobState.QUEUED
    assert provider.get_status(job).state is IqaJobState.RUNNING
    assert provider.get_status(job).state is IqaJobState.COMPLETED

    reference = provider.get_result_reference(job)
    materialized = provider.materialize(reference)
    assert materialized.availability is IqaAvailability.AVAILABLE
    assert materialized.source is not None
    opened = provider.open_result(materialized.source)
    assert opened.availability is IqaAvailability.AVAILABLE
    assert opened.result is not None

    source_locator = opened.result.scenes[0].sources[0].source.locator
    resolved = provider.resolve_source(source_locator)
    assert resolved.availability is IqaAvailability.AVAILABLE
    assert resolved.source is not None
    assert resolved.source.local_path.exists()


def test_failure_profile_has_terminal_failure_and_never_publishes_result(
    tmp_path: Path,
) -> None:
    assert (
        SYNTHETIC_IQA_PROFILES[SyntheticIqaProfile.FAILURE].terminal_state
        is IqaJobState.FAILED
    )
    assert (
        build_synthetic_iqa_result(tmp_path / "failure", SyntheticIqaProfile.FAILURE)
        is None
    )

    provider = FixtureIqaProvider(
        tmp_path / "provider-failure",
        SyntheticIqaProfile.FAILURE,
    )
    job = provider.submit(_intent(tmp_path))
    assert provider.get_status(job).state is IqaJobState.QUEUED
    assert provider.get_status(job).state is IqaJobState.RUNNING
    assert provider.get_status(job).state is IqaJobState.FAILED
    with pytest.raises(IqaProviderError, match="did not publish"):
        provider.get_result_reference(job)


def test_fixture_provider_cancel_is_explicit_and_does_not_publish_result(
    tmp_path: Path,
) -> None:
    provider = FixtureIqaProvider(tmp_path / "cancel", SyntheticIqaProfile.MINIMAL)
    job = provider.submit(_intent(tmp_path))

    assert provider.cancel(job).state is IqaJobState.CANCELLED
    assert provider.get_status(job).state is IqaJobState.CANCELLED
    with pytest.raises(IqaProviderError, match="did not publish"):
        provider.get_result_reference(job)
