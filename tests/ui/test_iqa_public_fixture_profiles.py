from __future__ import annotations

from pathlib import Path

import pytest

from pixelscope.remote.iqa_domain import LoadStatus
from pixelscope.remote.iqa_explorer import IqaExplorerModel
from pixelscope.remote.iqa_public_contract import (
    IqaAvailability,
    IqaJobState,
    IqaSubmissionIntent,
    IqaSubmissionScene,
    IqaSubmissionSource,
    IqaVariant,
)
from pixelscope.remote.iqa_public_fixture import (
    FixtureIqaProvider,
    IqaFixtureProfile,
    build_profile_result,
)
from pixelscope.ui.iqa_workspace import IqaWorkspaceWidget

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _intent() -> IqaSubmissionIntent:
    return IqaSubmissionIntent(
        "fixture",
        (IqaVariant("A", "A"), IqaVariant("B", "B")),
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


def test_partial_public_fixture_renders_without_fabricating_missing_measurement(
    qtbot: object,
    tmp_path: Path,
) -> None:
    result = build_profile_result(tmp_path / "partial", IqaFixtureProfile.PARTIAL)
    model = IqaExplorerModel(result)
    widget = IqaWorkspaceWidget()
    qtbot.addWidget(widget)  # type: ignore[attr-defined]

    assert widget.set_model(model).status is LoadStatus.SUCCESS
    assert model.normalized_result is result
    assert widget.hierarchy.topLevelItemCount() == len(result.attributes)

    scene = result.scenes[-1]
    variant = result.variants[-1]
    attribute = result.attributes[-1]
    summary = scene.source_for_variant(variant.variant_id).summary(attribute.attribute_id)
    assert summary.availability is IqaAvailability.MISSING
    assert not model.absolute_scene_stat(
        scene.scene_id,
        variant.variant_id,
        attribute.attribute_id,
    ).valid

    last_attribute = widget.hierarchy.topLevelItem(len(result.attributes) - 1)
    assert last_attribute is not None
    last_attribute.setExpanded(True)
    assert last_attribute.childCount() == len(result.scenes)
    missing_row = last_attribute.child(len(result.scenes) - 1)
    assert missing_row is not None
    # Column 0 is the Scene label; each following column is one ordered variant.
    missing_text = missing_row.text(len(result.variants))
    assert missing_text
    assert missing_text != "0.0000"


def test_failure_fixture_state_is_presentable_without_network_or_model(
    qtbot: object,
    tmp_path: Path,
) -> None:
    provider = FixtureIqaProvider(tmp_path / "failure", IqaFixtureProfile.FAILURE)
    job = provider.submit(_intent())
    assert provider.advance(job).state is IqaJobState.RUNNING
    failed = provider.advance(job)
    assert failed.state is IqaJobState.FAILED
    assert failed.message is not None

    widget = IqaWorkspaceWidget()
    qtbot.addWidget(widget)  # type: ignore[attr-defined]
    widget.show_open_error(LoadStatus.CORRUPT, failed.message)

    assert widget.status_label.text() == f"CORRUPT: {failed.message}"
    assert widget.model is None
