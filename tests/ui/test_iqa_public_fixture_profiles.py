from __future__ import annotations

from pathlib import Path

import pytest

from pixelscope.remote.iqa_domain import LoadStatus
from pixelscope.remote.iqa_explorer import IqaExplorerModel
from pixelscope.remote.iqa_public_contract import IqaAvailability
from pixelscope.remote.iqa_public_fixture import IqaFixtureProfile, build_profile_result
from pixelscope.ui.iqa_workspace import IqaWorkspaceWidget

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def test_partial_public_fixture_renders_without_fabricating_missing_measurement(
    qtbot: object,
    tmp_path: Path,
) -> None:
    result = build_profile_result(tmp_path / "partial", IqaFixtureProfile.PARTIAL)
    model = IqaExplorerModel(result)
    widget = IqaWorkspaceWidget()
    qtbot.addWidget(widget)  # type: ignore[attr-defined]

    outcome = widget.set_model(model)
    assert outcome.status is LoadStatus.SUCCESS
    assert outcome.result is None
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
