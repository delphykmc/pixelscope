"""Host-contributed IQA presentation defaults and native signed-value wording."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest
from PySide6.QtGui import QColor, QImage

from pixelscope_enterprise.iqa.analysis_model import (
    AnalysisResult,
    AttributeDisplay,
    SpatialMap,
    map_polarity_legend,
)
from pixelscope_enterprise.iqa.analysis_window import (
    AnalysisWindow,
    IqaPresentationDefaults,
)
from pixelscope_enterprise.iqa.composition import IqaWindowContribution


def _result(tmp_path: object, *, with_images: bool = True) -> AnalysisResult:
    attribute = AttributeDisplay(
        attribute_id="detail",
        label="Detail",
        unit="dB",
        group="Detail",
        official_value=0.5,
        official_availability="available",
        quality_oriented=True,
        fixed_range=4.0,
        chart_axis_range=4.0,
        summary_signal_gate=True,
        quality_direction="higher_is_better",
        spatial=SpatialMap(
            np.array([[0.5]], dtype=np.float64),
            np.array([[True]], dtype=np.bool_),
            image_width=64,
            image_height=64,
            block_width=64.0,
            block_height=64.0,
        ),
    )
    result = AnalysisResult(
        result_id="present-defaults",
        image_width=64,
        image_height=64,
        source_a_label="target",
        source_b_label="reference",
        attributes=(attribute,),
        source_a_role="Target",
        source_b_role="Reference",
    )
    if not with_images:
        return result
    paths = []
    for filename, gray in (("target.png", 24), ("reference.png", 210)):
        path = tmp_path / filename  # type: ignore[operator]
        image = QImage(64, 64, QImage.Format.Format_RGB32)
        image.fill(QColor(gray, gray, gray))
        assert image.save(str(path))
        paths.append(path)
    return replace(result, source_a=paths[0], source_b=paths[1])


def test_default_legacy_presentation_is_signed_not_a_b_winner(qtbot: object, tmp_path: object) -> None:
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    assert not win.quality_policy_action.isChecked()
    assert not win.map_reference_action.isChecked()
    result = _result(tmp_path, with_images=False)
    win.present_result(result)
    assert "positive signed" in win.top3_buttons[0].text()
    assert "A better" not in win.top3_buttons[0].text()
    assert "Signed positive" in win.official_label.text()
    assert "no quality verdict" in map_polarity_legend(result.attributes[0])
    assert result.attributes[0].official_value == 0.5
    win.close()


def test_private_contribution_supplies_initial_quality_and_reference_tint(
    qtbot: object, tmp_path: object
) -> None:
    defaults = IqaPresentationDefaults(
        quality_enabled=True,
        tint_reference_enabled=True,
        visibility_threshold=0.5,
    )
    contribution = IqaWindowContribution(presentation_defaults=defaults)
    result = _result(tmp_path)
    win = contribution.manager.show(result)
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    assert win.quality_policy_action.isChecked()
    assert win.map_reference_action.isChecked()
    assert win.map_reference_action.isEnabled()
    assert "Reference B" in win.map_reference_action.text()
    assert "Superior" in win.top3_buttons[0].text()  # Inclusive boundary == 0.5.
    assert win._map_reference_item is not None
    pixel = win._map_reference_item.pixmap().toImage().pixelColor(4, 4)
    assert pixel.red() > 190

    # Host defaults do not lock the user controls or rewrite signed results.
    win.set_quality_presentation(False)
    assert "positive signed" in win.top3_buttons[0].text()
    win.map_reference_action.setChecked(False)
    assert not win.map_reference_action.isChecked()
    assert result.attributes[0].official_value == 0.5
    assert defaults.quality_enabled and defaults.tint_reference_enabled
    contribution.manager.shutdown()


@pytest.mark.parametrize("threshold", [-0.1, float("nan"), float("inf")])
def test_contributed_visibility_threshold_is_validated(threshold: float) -> None:
    with pytest.raises(ValueError, match="visibility threshold"):
        IqaPresentationDefaults(visibility_threshold=threshold)


@pytest.mark.parametrize(
    "kwargs",
    [{"quality_enabled": 1}, {"tint_reference_enabled": "yes"}],
)
def test_contributed_toggle_defaults_must_be_bool(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="must be bool"):
        IqaPresentationDefaults(**kwargs)  # type: ignore[arg-type]
