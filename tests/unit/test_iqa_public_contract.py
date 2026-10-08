from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import numpy as np
import pytest

from pixelscope.remote.iqa_domain import CompactAttributeData
from pixelscope.remote.iqa_public_contract import (
    IqaAvailability,
    IqaJobProgress,
    IqaJobState,
    IqaMeasurementSummary,
    IqaProviderError,
    IqaProviderErrorKind,
    IqaResolvedSource,
    IqaResultReference,
    IqaResultSource,
    IqaResultSourceOutcome,
    IqaSource,
    IqaSourceLocator,
    IqaSourceResolutionOutcome,
    IqaSpatialSceneData,
    IqaSubmissionIntent,
    IqaSubmissionScene,
    IqaSubmissionSource,
    IqaVariant,
)


def _intent() -> IqaSubmissionIntent:
    variants = (IqaVariant("A", "Reference"), IqaVariant("B", "Candidate"))
    return IqaSubmissionIntent(
        "current_pair",
        variants,
        (
            IqaSubmissionScene(
                "scene_0001",
                (
                    IqaSubmissionSource("A", Path("a.png")),
                    IqaSubmissionSource("B", Path("b.png")),
                ),
            ),
        ),
    )


def test_public_identity_types_do_not_expose_provider_storage_topology() -> None:
    assert [item.name for item in fields(IqaResultReference)] == ["reference_id"]
    assert [item.name for item in fields(IqaSourceLocator)] == ["locator_id", "display_name"]
    assert [item.name for item in fields(IqaSubmissionSource)] == ["variant_id", "local_path"]

    locator = IqaSourceLocator("opaque-source", "source.png")
    source = IqaSource("source-1", locator, "0" * 64, 640, 480)
    assert source.relative_path == "source.png"
    assert not hasattr(source, "storage_root_id")


def test_submission_intent_requires_unique_identity_and_declared_variant_order() -> None:
    intent = _intent()
    assert tuple(item.variant_id for item in intent.variants) == ("A", "B")

    with pytest.raises(ValueError, match="variant IDs must be non-empty and unique"):
        IqaSubmissionIntent(
            "duplicate-variant",
            (IqaVariant("A", "A"), IqaVariant("A", "Again")),
            intent.scenes,
        )

    with pytest.raises(ValueError, match="declared variant order"):
        IqaSubmissionIntent(
            "wrong-order",
            intent.variants,
            (
                IqaSubmissionScene(
                    "scene_0001",
                    (
                        IqaSubmissionSource("B", Path("b.png")),
                        IqaSubmissionSource("A", Path("a.png")),
                    ),
                ),
            ),
        )

    with pytest.raises(ValueError, match="Scene IDs must be non-empty and unique"):
        IqaSubmissionIntent(
            "duplicate-scene",
            intent.variants,
            (intent.scenes[0], intent.scenes[0]),
        )


def test_job_progress_and_terminal_state_validation_are_provider_neutral() -> None:
    assert not IqaJobState.QUEUED.terminal
    assert not IqaJobState.RUNNING.terminal
    assert IqaJobState.COMPLETED.terminal
    assert IqaJobState.FAILED.terminal
    assert IqaJobState.CANCELLED.terminal

    assert IqaJobProgress(2, 3) == IqaJobProgress(completed=2, total=3)
    with pytest.raises(ValueError, match="non-negative"):
        IqaJobProgress(completed=-1)
    with pytest.raises(ValueError, match="non-negative"):
        IqaJobProgress(total=-1)
    with pytest.raises(ValueError, match="cannot exceed total"):
        IqaJobProgress(completed=4, total=3)


def test_provider_error_exposes_only_bounded_sanitized_public_message() -> None:
    error = IqaProviderError(
        IqaProviderErrorKind.AMBIGUOUS_SUBMIT,
        "  submit   outcome   is   unknown  ",
        retryable=False,
    )

    assert error.display_message == "submit outcome is unknown"
    assert error.submission_outcome_unknown
    assert not error.retryable
    assert str(error) == error.display_message

    bounded = IqaProviderError(IqaProviderErrorKind.OPERATION_FAILED, "x" * 400)
    assert len(bounded.display_message) == 256


def test_availability_outcomes_keep_missing_partial_and_failure_explicit(
    tmp_path: Path,
) -> None:
    missing = IqaMeasurementSummary.missing("metric_not_published")
    failed = IqaMeasurementSummary.failed("provider_failed")
    assert missing.availability is IqaAvailability.MISSING
    assert failed.availability is IqaAvailability.FAILED
    assert not missing.valid
    assert not failed.valid

    result_source = IqaResultSource(tmp_path)
    available_result = IqaResultSourceOutcome(IqaAvailability.AVAILABLE, result_source)
    partial_result = IqaResultSourceOutcome(IqaAvailability.PARTIAL, result_source)
    assert available_result.succeeded
    assert partial_result.succeeded
    assert not IqaResultSourceOutcome(IqaAvailability.MISSING).succeeded

    resolved = IqaResolvedSource(tmp_path / "source.png")
    assert IqaSourceResolutionOutcome(IqaAvailability.AVAILABLE, resolved).succeeded
    assert not IqaSourceResolutionOutcome(IqaAvailability.PARTIAL, resolved).succeeded
    assert not IqaSourceResolutionOutcome(IqaAvailability.MISSING).succeeded


def test_spatial_scene_data_projects_the_requested_variant_without_legacy_adapter() -> None:
    compact = CompactAttributeData(
        weight_sum=np.asarray([1.0, 2.0]),
        weighted_sum=np.asarray([3.0, 4.0]),
        weighted_square_sum=np.asarray([9.0, 16.0]),
        valid_count=np.asarray([5, 6]),
        valid_mask=np.asarray([True, False]),
    )
    spatial = IqaSpatialSceneData(
        "scene_0001",
        ("A", "B"),
        ("source-a", "source-b"),
        {"detail": compact},
    )

    projected = spatial.attribute_for_variant("B", "detail")
    assert float(np.asarray(projected.weight_sum).item()) == 2.0
    assert float(np.asarray(projected.weighted_sum).item()) == 4.0
    assert float(np.asarray(projected.weighted_square_sum).item()) == 16.0
    assert int(np.asarray(projected.valid_count).item()) == 6
    assert not bool(np.asarray(projected.valid_mask).item())
