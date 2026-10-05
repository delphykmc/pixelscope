from __future__ import annotations

from pathlib import Path

import pyqtgraph as pg
import pytest

from pixelscope.remote.iqa_domain import LoadStatus
from pixelscope.remote.iqa_explorer import IqaExplorerModel
from pixelscope.remote.iqa_public_contract import IqaResult
from pixelscope.remote.iqa_public_fixture import SyntheticIqaProfile, build_synthetic_iqa_result
from pixelscope.ui.iqa_workspace import IqaWorkspaceWidget

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


class _PublicFixtureExplorerModel(IqaExplorerModel):
    """Expose the normalized fixture through the existing presentation accessor.

    Slice 2 intentionally kept ``IqaExplorerModel.result`` legacy/schema-v2-only while
    adding ``normalized_result``.  Slice 3 is proving the public data shape against the
    current Client UI without pulling forward Slice 4 composition work.
    """

    @property
    def result(self) -> IqaResult:  # type: ignore[override]
        result = self.normalized_result
        assert result is not None
        return result


def _model(root: Path, profile: SyntheticIqaProfile) -> _PublicFixtureExplorerModel:
    result = build_synthetic_iqa_result(root, profile)
    assert result is not None
    return _PublicFixtureExplorerModel(result)


def _curve_count(widget: IqaWorkspaceWidget) -> int:
    return sum(isinstance(item, pg.PlotDataItem) for item in widget.scene_trend_plot.plotItem.items)


@pytest.mark.parametrize(
    ("profile", "expected_attributes", "expected_variants", "expected_scenes"),
    [
        (SyntheticIqaProfile.MINIMAL, 2, 2, 3),
        (SyntheticIqaProfile.NORMAL, 10, 3, 12),
        (SyntheticIqaProfile.LARGE, 32, 16, 128),
    ],
)
def test_public_synthetic_profiles_drive_existing_iqa_workspace(
    qtbot: object,
    tmp_path: Path,
    profile: SyntheticIqaProfile,
    expected_attributes: int,
    expected_variants: int,
    expected_scenes: int,
) -> None:
    widget = IqaWorkspaceWidget()
    qtbot.addWidget(widget)  # type: ignore[attr-defined]
    model = _model(tmp_path / profile.value, profile)

    assert widget.set_model(model).status is LoadStatus.SUCCESS
    assert widget.hierarchy.topLevelItemCount() == expected_attributes
    assert len(widget.scene_variant_legend.items) == expected_variants
    assert len(widget._scene_hover_texts) == expected_scenes

    expected_enabled_attributes = min(expected_attributes, max(1, 32 // expected_variants))
    assert len(widget.enabled_attribute_ids) == expected_enabled_attributes
    assert _curve_count(widget) == expected_enabled_attributes * expected_variants


def test_partial_public_fixture_keeps_missing_measurement_visible_without_ui_failure(
    qtbot: object,
    tmp_path: Path,
) -> None:
    widget = IqaWorkspaceWidget()
    qtbot.addWidget(widget)  # type: ignore[attr-defined]
    model = _model(tmp_path / "partial", SyntheticIqaProfile.PARTIAL)

    assert widget.set_model(model).status is LoadStatus.SUCCESS
    assert model.normalized_result is not None
    assert model.normalized_result.diagnostics[0].code == "synthetic_partial_result"
    last_scene = model.normalized_result.scenes[-1].scene_id
    last_variant = model.normalized_result.variants[-1].variant_id
    last_attribute = model.normalized_result.attributes[-1].attribute_id
    assert not model.absolute_scene_stat(last_scene, last_variant, last_attribute).valid
