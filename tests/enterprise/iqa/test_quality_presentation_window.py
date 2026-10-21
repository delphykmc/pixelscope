"""Optional quality policy reaches every existing Analysis Window surface."""

from __future__ import annotations

from dataclasses import replace

from pixelscope_enterprise.iqa.analysis_window import AnalysisWindow
from pixelscope_enterprise.iqa.attribute_chart import (
    QUALITY_POLICY_ROLE,
    VISIBILITY_THRESHOLD_ROLE,
)
from pixelscope_enterprise.iqa.demo import make_synthetic_result
from pixelscope_enterprise.iqa.spatial_candidates import SpatialCandidate
from pixelscope_enterprise.iqa.spatial_dock import SpatialCandidatesPanel


def test_opt_in_quality_policy_preserves_values_roi_state_and_legacy_default(
    qtbot: object,
) -> None:
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    result = make_synthetic_result("quality-toggle")
    win.present_result(result)
    win._set_roi(0, 0, 256, 256)
    state_before = win.current_analysis_state()
    assert not win.quality_policy_action.isChecked()
    assert "A better" in win.top3_buttons[0].text()
    raw_values = [attr.official_value for attr in result.attributes]

    win.quality_policy_action.setChecked(True)
    assert win._quality_policy_enabled
    assert win.top3_buttons[0].property("insightTone") == "superior"
    assert "Superior" in win.top3_buttons[0].text()
    assert "A better" not in win.top3_buttons[0].text()
    assert win._group_tables["dB"].item(0, 1).data(QUALITY_POLICY_ROLE) is True
    assert win._group_tables["dB"].item(0, 1).data(VISIBILITY_THRESHOLD_ROLE) == 0.5
    win.top3_buttons[0].click()
    assert "Blue: Superior" in win.clamp_label.text()
    assert "display only" in win.official_label.text()
    assert win.current_roi == (0, 0, 256, 256)
    assert [attr.official_value for attr in result.attributes] == raw_values

    win.set_quality_presentation(True, threshold=7.0)
    assert win.top3_buttons[0].isEnabled()  # exactly 7.0 is now visible
    win.set_quality_presentation(True, threshold=7.5)
    assert not any(card.isEnabled() for card in win.top3_buttons)
    assert "Faint gray" in win.clamp_label.text()
    win.quality_policy_action.setChecked(False)
    assert "A better" in win.top3_buttons[0].text()
    assert win._group_tables["dB"].item(0, 1).data(QUALITY_POLICY_ROLE) is False
    assert win.current_roi == (0, 0, 256, 256)
    assert win.current_analysis_state()["ranges"] == state_before["ranges"]
    win.close()


def test_quality_policy_excludes_untrusted_first_insights(
    qtbot: object,
) -> None:
    original = make_synthetic_result("quality-untrusted")
    untrusted = replace(
        original,
        attributes=tuple(replace(attr, summary_signal_gate=None) for attr in original.attributes),
    )
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.present_result(untrusted)
    assert not any(card.isEnabled() for card in win.top3_buttons)
    win.set_quality_presentation(True)
    assert not any(card.isEnabled() for card in win.top3_buttons)
    assert not win._top3_attribute_ids
    win.close()


def test_local_hotspot_cards_show_directional_verdict_without_recomputing_scores(
    qtbot: object,
) -> None:
    panel = SpatialCandidatesPanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    source_attr = make_synthetic_result().attributes[5]  # lower is better
    candidate = SpatialCandidate(1, 0, 0, 512, 512, -2.0, 1.0, 262144.0, 2.0, "aligned")
    panel.populate((candidate,), (None, None), "dB")
    assert "Superior" not in panel.details[0].text()
    panel.populate(
        (candidate,),
        (None, None),
        "dB",
        quality_attribute=source_attr,
    )
    assert "Superior" in panel.details[0].text()
    assert panel.buttons[0].property("spatialVerdict") == "superior"
    panel.populate(
        (candidate,),
        (None, None),
        "dB",
        quality_attribute=source_attr,
        visibility_threshold=2.1,
    )
    assert "Not visible" in panel.details[0].text()
    assert panel.buttons[0].property("spatialVerdict") == "muted"
    assert candidate.mean == -2.0
    panel.populate((candidate,), (None, None), "dB")
    assert panel.buttons[0].property("spatialVerdict") is None
    panel.close()


def test_exploratory_hotspot_does_not_claim_superior_or_inferior(qtbot: object) -> None:
    panel = SpatialCandidatesPanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    attr = make_synthetic_result().attributes[5]
    exploratory = SpatialCandidate(1, 0, 0, 512, 512, -3.0, 1.0, 262144.0, 3.0, "exploratory_abs")
    panel.populate((exploratory,), (None, None), "dB", quality_attribute=attr)
    assert "Exploratory · No verified verdict" in panel.details[0].text()
    assert "Superior" not in panel.details[0].text()
    assert "Inferior" not in panel.details[0].text()
    assert panel.buttons[0].property("spatialVerdict") == "muted"
    assert "full-pair comparison sign unavailable" in panel.details[0].toolTip()
    assert exploratory.mean == -3.0
    panel.close()
