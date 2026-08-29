from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QLabel, QDockWidget, QWidget

from pixelscope.app.main_window import MainWindow
from pixelscope.ui.beta_workspace_hardening import install_beta_workspace_hardening
from pixelscope.ui.design_tokens import TOKENS, WORKSPACE_CHROME_HEIGHT
from pixelscope.ui.plots_dock_title import PlotsDockTitleBar
from pixelscope.ui.presentation_controls import polish_presentation_controls

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _sidebar_heading(window: MainWindow, index: int) -> QLabel:
    container = window.sidebar_splitter.widget(index)
    layout = container.layout()
    assert layout is not None
    heading = layout.itemAt(0).widget()
    assert isinstance(heading, QLabel)
    return heading


def _bottom_y(widget: QWidget, window: MainWindow) -> int:
    return widget.mapTo(window, QPoint(0, widget.height())).y()


def test_docked_workspace_chrome_has_one_shared_baseline(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    polish_presentation_controls(window)
    install_beta_workspace_hardening(window)
    window.show()
    window.iqa_workspace_action.trigger()
    qtbot.waitUntil(window.iqa_dock.isVisible)  # type: ignore[attr-defined]
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: isinstance(window.iqa_dock.titleBarWidget(), PlotsDockTitleBar)
    )

    files = _sidebar_heading(window, 0)
    analysis = _sidebar_heading(window, 1)
    iqa_title = window.iqa_dock.titleBarWidget()
    assert isinstance(iqa_title, PlotsDockTitleBar)

    for heading in (files, analysis, window.presentation_controls, iqa_title):
        assert heading.minimumHeight() == WORKSPACE_CHROME_HEIGHT
        assert heading.maximumHeight() == WORKSPACE_CHROME_HEIGHT

    assert f"background: {TOKENS.title_background}" in files.styleSheet()
    assert f"border-bottom: 1px solid {TOKENS.border}" in files.styleSheet()
    assert f"background: {TOKENS.title_background}" in analysis.styleSheet()
    assert f"border-bottom: 1px solid {TOKENS.border}" in analysis.styleSheet()
    assert f"border-bottom: 1px solid {TOKENS.border}" in window.presentation_controls.styleSheet()
    assert f"background: {TOKENS.title_background}" in iqa_title.styleSheet()
    assert f"border-bottom: 1px solid {TOKENS.border}" in iqa_title.styleSheet()

    files_bottom = _bottom_y(files, window)
    presentation_bottom = _bottom_y(window.presentation_controls, window)
    iqa_bottom = _bottom_y(iqa_title, window)
    assert files_bottom == presentation_bottom == iqa_bottom

    window.close()


@pytest.mark.parametrize("workspace", ["plots", "iqa"])
def test_floating_workspace_has_explicit_outer_frame(
    qtbot: object,
    workspace: str,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    install_beta_workspace_hardening(window)
    window.show()

    if workspace == "plots":
        window._set_plots_visible(True)
        dock = window.bottom_dock
    else:
        window.iqa_workspace_action.trigger()
        dock = window.iqa_dock

    assert isinstance(dock, QDockWidget)
    qtbot.waitUntil(dock.isVisible)  # type: ignore[attr-defined]
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: isinstance(dock.titleBarWidget(), PlotsDockTitleBar)
    )

    dock.setFloating(True)
    qtbot.waitUntil(dock.isFloating)  # type: ignore[attr-defined]
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: f"border: 1px solid {TOKENS.border}" in dock.styleSheet()
    )

    title = dock.titleBarWidget()
    assert isinstance(title, PlotsDockTitleBar)
    assert title.height() == WORKSPACE_CHROME_HEIGHT

    dock.setFloating(False)
    qtbot.waitUntil(lambda: not dock.isFloating())  # type: ignore[attr-defined]
    assert "border: 0px" in dock.styleSheet()

    window.close()
