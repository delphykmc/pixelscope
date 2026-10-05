from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

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
    FIXTURE_SPECS,
    FixtureIqaProvider,
    IqaFixtureProfile,
    build_fixture_result,
    build_profile_result,
)


def _intent() -> IqaSubmissionIntent:
    variants = (IqaVariant("A", "A"), IqaVariant("B", "B"))
    return IqaSubmissionIntent(
        "fixture",
        variants,
        (
            IqaSubmissionScene(
                "fixture_input",
                (
                    IqaSubmissionSource("A", Path("a.png")),
                    IqaSubmissionSource("B", Path("b.png")),
                ),
            ),
        ),
    )


def test_fixture_catalog_covers_checkpoint_b_profiles() -> None:
    assert set(FIXTURE_SPECS) == set(IqaFixtureProfile)
    assert FIXTURE_SPECS[IqaFixtureProfile.MINIMAL].attribute_count == 2
    assert FIXTURE_SPECS[IqaFixtureProfile.NORMAL].variant_count == 3
    assert FIXTURE_SPECS[IqaFixtureProfile.LARGE].scene_count == 128
    assert FIXTURE_SPECS[IqaFixtureProfile.PARTIAL].completeness is IqaResultCompleteness.PARTIAL


def test_public_fixture_keeps_spatial_data_lazy_and_deterministic(tmp_path: Path) -> None:
    result = build_fixture_result(
        tmp_path / "fixture",
        attribute_count=3,
        variant_count=2,
        scene_count=4,
    )

    assert result.completeness is IqaResultCompleteness.COMPLETE
    assert len(result.scenes) == 4
    assert len(result.variants) == 2
    assert len(result.attributes) == 3
    assert result.dataset_summary("variant_000", "attribute_000").pooled.valid

    first = result.load_spatial("scene_0000")
    second = result.load_spatial("scene_0000")
    assert first.availability is IqaAvailability.AVAILABLE
    assert first.succeeded and second.succeeded
    assert first.data is not None and second.data is not None
    np.testing.assert_array_equal(
        first.data.attributes["attribute_000"].weighted_sum,
        second.data.attributes["attribute_000"].weighted_sum,
    )
    weighted_sum = first.data.attribute_for_variant(
        "variant_001",
        "attribute_000",
    ).weighted_sum
    assert float(np.asarray(weighted_sum).item()) == 1.1


def test_partial_profile_exposes_missing_measurement_without_fabricated_zero(
    tmp_path: Path,
) -> None:
    result = build_profile_result(tmp_path / "partial", IqaFixtureProfile.PARTIAL)
    scene = result.scenes[-1]
    variant = result.variants[-1]
    attribute = result.attributes[-1]

    summary = scene.source_for_variant(variant.variant_id).summary(attribute.attribute_id)
    assert result.completeness is IqaResultCompleteness.PARTIAL
    assert summary.availability is IqaAvailability.MISSING
    assert not summary.valid
    assert result.diagnostics[0].code == "fixture_metric_missing"

    dataset = result.dataset_summary(variant.variant_id, attribute.attribute_id)
    assert dataset.pooled.availability is IqaAvailability.PARTIAL
    assert dataset.scene_count == len(result.scenes) - 1
    assert dataset.pooled.weighted_mean is not None

    spatial = result.load_spatial(scene.scene_id)
    assert spatial.availability is IqaAvailability.PARTIAL
    assert spatial.data is not None
    missing_grid = spatial.data.attribute_for_variant(variant.variant_id, attribute.attribute_id)
    assert not bool(np.asarray(missing_grid.valid_mask).item())
    assert int(np.asarray(missing_grid.valid_count).item()) == 0
    assert float(np.asarray(missing_grid.weight_sum).item()) == 0.0


def test_fixture_provider_exercises_public_execution_and_result_ports(tmp_path: Path) -> None:
    provider = FixtureIqaProvider(tmp_path / "normal", IqaFixtureProfile.NORMAL)
    assert isinstance(provider, IqaExecutionPort)
    assert isinstance(provider, IqaResultAccessPort)
    assert provider.capabilities.can_cancel

    job = provider.submit(_intent())
    assert provider.get_status(job).state is IqaJobState.QUEUED
    assert provider.advance(job).state is IqaJobState.RUNNING
    assert provider.advance(job).state is IqaJobState.COMPLETED

    reference = provider.get_result_reference(job)
    materialized = provider.materialize(reference)
    assert materialized.availability is IqaAvailability.AVAILABLE
    assert materialized.source is not None
    opened = provider.open_result(materialized.source)
    assert opened.availability is IqaAvailability.AVAILABLE
    assert opened.result is not None
    assert opened.result.result_id == "fixture-normal"
    assert len(opened.result.variants) == 3


def test_fixture_provider_partial_result_and_cancel_are_explicit(tmp_path: Path) -> None:
    provider = FixtureIqaProvider(tmp_path / "partial", IqaFixtureProfile.PARTIAL)
    cancelled_job = provider.submit(_intent())
    assert provider.cancel(cancelled_job).state is IqaJobState.CANCELLED
    assert provider.advance(cancelled_job).state is IqaJobState.CANCELLED

    job = provider.submit(_intent())
    provider.advance(job)
    provider.advance(job)
    materialized = provider.materialize(provider.get_result_reference(job))
    assert materialized.availability is IqaAvailability.PARTIAL
    assert materialized.source is not None
    opened = provider.open_result(materialized.source)
    assert opened.availability is IqaAvailability.PARTIAL
    assert opened.result is not None
    assert opened.result.completeness is IqaResultCompleteness.PARTIAL


def test_failure_profile_has_terminal_failure_and_no_result(tmp_path: Path) -> None:
    provider = FixtureIqaProvider(tmp_path / "failure", IqaFixtureProfile.FAILURE)
    job = provider.submit(_intent())
    assert provider.advance(job).state is IqaJobState.RUNNING
    failed = provider.advance(job)
    assert failed.state is IqaJobState.FAILED
    assert failed.message == "Synthetic IQA job failed."

    with pytest.raises(IqaProviderError, match="result is not available"):
        provider.get_result_reference(job)


def test_fixture_source_resolution_is_explicitly_unavailable(tmp_path: Path) -> None:
    provider = FixtureIqaProvider(tmp_path / "normal")
    result = build_profile_result(tmp_path / "normal", IqaFixtureProfile.NORMAL)
    locator = result.scenes[0].sources[0].source.locator

    outcome = provider.resolve_source(locator)
    assert outcome.availability is IqaAvailability.MISSING
    assert not outcome.succeeded
    assert outcome.diagnostics[0].code == "fixture_source_not_materialized"
