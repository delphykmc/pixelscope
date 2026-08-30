from __future__ import annotations

from PySide6.QtWidgets import QSizePolicy

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.ui.beta_workspace_hardening import install_beta_workspace_hardening
from pixelscope.ui.iqa_growth_policy import install_iqa_preferred_growth_policy


def test_production_iqa_keeps_zero_minimum_with_preferred_horizontal_policy(
    qtbot: object,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    window.show()

    assert window.iqa_workspace.minimumWidth() == 0
    horizontal_policy = window.iqa_workspace.sizePolicy().horizontalPolicy()
    assert horizontal_policy == QSizePolicy.Policy.Preferred
    # Keep the dock itself free to compress; only the child advertises a preferred
    # recovery size to QMainWindow.
    assert window.iqa_dock.minimumWidth() == 0

    window.close()


def test_preferred_growth_policy_only_overrides_outer_iqa_horizontal_preference(
    qtbot: object,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    install_beta_workspace_hardening(window)

    hardened_policy = window.iqa_workspace.sizePolicy().horizontalPolicy()
    assert hardened_policy == QSizePolicy.Policy.Ignored

    install_iqa_preferred_growth_policy(window)

    assert window.iqa_workspace.minimumWidth() == 0
    preferred_policy = window.iqa_workspace.sizePolicy().horizontalPolicy()
    assert preferred_policy == QSizePolicy.Policy.Preferred
    assert window.iqa_dock.minimumWidth() == 0

    window.close()
