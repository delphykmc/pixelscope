"""UX-2A native Qt gates: verified first-insight cards and toolbar parity."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QToolBar, QToolButton

from pixelscope_enterprise.iqa.analysis_window import AnalysisWindow
from pixelscope_enterprise.iqa.demo import make_synthetic_result


def test_ux2a_top_cards_select_official_metric_without_destroying_views(
    qtbot: object,
) -> None:
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    result = make_synthetic_result("ux2a-overview")
    win.present_result(result)
    assert "VERIFIED" in win.top3_title.text()
    assert len(win.top3_buttons) == 3
    assert all(button.isEnabled() for button in win.top3_buttons)
    assert [button.property("insightTone") for button in win.top3_buttons] == [
        "a",
        "b",
        "b",
    ]
    assert all(not button.icon().isNull() for button in win.top3_buttons)
    assert all("border-left" in button.styleSheet() for button in win.top3_buttons)
    assert all(
        button.styleSheet().count("{") == button.styleSheet().count("}")
        for button in win.top3_buttons
    )
    assert win._top3_attribute_ids == [  # type: ignore[attr-defined]
        "synthetic_04",
        "synthetic_05",
        "synthetic_00",
    ]
    scenes = tuple(view.scene() for view in win._views)
    win._set_roi(200.0, 220.0, 512.0, 512.0)
    roi_before = win.current_roi
    state_before = win.current_analysis_state()
    win.top3_buttons[1].click()
    assert win._state().attribute_id == "synthetic_05"  # type: ignore[union-attr]
    assert win.top3_buttons[1].isChecked()
    assert win.current_roi == roi_before
    assert win.current_analysis_state()["viewport"] == state_before["viewport"]
    assert tuple(view.scene() for view in win._views) == scenes
    win.top3_buttons[0].click()
    assert win._state().attribute_id == "synthetic_04"  # type: ignore[union-attr]
    assert tuple(view.scene() for view in win._views) == scenes
    win.close()


def test_ux2a_unknown_signal_gate_does_not_claim_top_three(qtbot: object) -> None:
    original = make_synthetic_result("ux2a-no-signal-gate")
    unverified = replace(
        original,
        attributes=tuple(replace(item, summary_signal_gate=None) for item in original.attributes),
    )
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.present_result(unverified)
    assert "NOT YET VERIFIED" in win.top3_title.text()
    assert all(not card.isEnabled() for card in win.top3_buttons)
    assert win._top3_attribute_ids == []
    # Default Attribute/Map remain navigable, independent of absent Top-3.
    assert win._attribute() is not None
    win.close()


def test_ux2a_neutral_signed_and_selected_card_visuals(qtbot: object) -> None:
    original = make_synthetic_result("ux2a-neutral-visual")
    attributes = list(original.attributes)
    attributes[0] = replace(
        attributes[0], official_value=-12.0, quality_oriented=False
    )
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.present_result(replace(original, attributes=tuple(attributes)))
    assert win._top3_attribute_ids[0] == "synthetic_00"
    neutral = win.top3_buttons[0]
    assert neutral.property("insightTone") == "signed"
    assert "no winner" in neutral.text()
    assert not neutral.icon().isNull()
    neutral.click()
    assert neutral.isChecked()
    assert "QPushButton:checked" in neutral.styleSheet()
    assert win.current_analysis_state()["attribute_id"] == "synthetic_00"
    win.close()


def test_ux2a_toolbar_reuses_menu_actions_and_documented_shortcuts(qtbot: object) -> None:
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    assert isinstance(win.iqa_toolbar, QToolBar)
    assert isinstance(win.swap_button, QToolButton)
    assert win.swap_button.defaultAction() is win.swap_sources_action
    assert win.fit_button.defaultAction() is win.fit_action
    assert win.clear_roi_tool_button.defaultAction() is win.clear_roi_action
    assert win.fit_action.shortcut() == QKeySequence("Ctrl+0")
    assert win.swap_sources_action.shortcuts() == [QKeySequence("T"), QKeySequence("Alt+X")]
    assert win.fit_action.isEnabled() is False
    win.present_result(make_synthetic_result("ux2a-toolbar"))
    assert win.fit_button.isEnabled()
    order = win._sources_swapped
    win.swap_button.click()
    assert win._sources_swapped is not order
    assert win.swap_sources_action.isEnabled()
    win._set_roi(0.0, 0.0, 512.0, 512.0)
    assert win.clear_roi_tool_button.isEnabled()
    win.clear_roi_tool_button.click()
    assert win.current_roi is None
    win.close()
