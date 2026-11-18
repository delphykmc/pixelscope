"""A retired preset must not keep hidden controls, owners or settings alive."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QWidget

from pixelscope.app.bootstrap import compose_main_window_presentation
from pixelscope.app.main_window import MainWindow

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def test_w05_w06_retirement_has_no_hidden_runtime_widgets(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    compose_main_window_presentation(window)
    assert not hasattr(window.quick_compare_controller, "comparison_presets")
    assert not hasattr(window.beta_workspace_hardening_controller, "workspace_presets")
    assert window.findChild(QWidget, "comparisonPresetControl") is None
    assert window.findChild(QWidget, "workspacePresetControl") is None
    assert not hasattr(window, "_comparison_plan")
    assert window.action_map["Open Images..."] in window._menu_map["File"].actions()
    assert window.action_map["Reset Workspace Layout"] in window._menu_map["View"].actions()
    assert window.bottom_dock is not None
    window.close()


def test_retired_w06_settings_are_migrated_without_touching_native_splitter(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    settings = window.settings
    settings.setValue("ui/workspace_preset", "Analyze")
    settings.setValue("ui/workspace_layouts/v1/Analyze/example", "obsolete")
    before = settings.value("ui/main_splitter")
    compose_main_window_presentation(window)
    assert not settings.contains("ui/workspace_preset")
    assert not settings.contains("ui/workspace_layouts/v1/Analyze/example")
    assert settings.value("ui/main_splitter") == before
    window.close()


def test_original_layout_actions_and_quick_compare_survive(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    compose_main_window_presentation(window)
    window.set_layout_mode("Multi View")
    window.action_map["Reset Workspace Layout"].trigger()
    assert window._layout_mode == "Auto"
    assert hasattr(window.quick_compare_controller, "three_view_group")
    assert window.bottom_dock is not None
    window.close()
