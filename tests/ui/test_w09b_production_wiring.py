"""W09b production composition and owner-terminal event contract tests."""

from __future__ import annotations

import pytest

from pixelscope.app.bootstrap import compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.ui.review_window_integration import NamedReviewCoordinator
from pixelscope.ui.workspace_presets import WorkspacePreset

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _window(qtbot: object) -> tuple[MainWindow, NamedReviewCoordinator]:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    compose_main_window_presentation(window)
    owner = window.named_review_coordinator
    assert isinstance(owner, NamedReviewCoordinator)
    return window, owner


def test_production_composition_exposes_named_review_without_toolbar_overflow(
    qtbot: object,
) -> None:
    window, review = _window(qtbot)
    view = next(action.menu() for action in window.menuBar().actions() if action.text() == "&View")
    assert view is not None
    assert review.action in view.actions()
    assert review.action not in window.main_toolbar.actions()
    assert review.dock in window._contributed_docks
    assert review.dock.isHidden()
    assert review.panel.findings.count() == 0

    window.show()
    review.action.trigger()
    assert window.beta_workspace_hardening_controller.workspace_presets.preset is (
        WorkspacePreset.REVIEW
    )
    assert not review.dock.isHidden()
    window.close()
    assert review._closed


def test_owner_terminal_only_for_current_pending_epoch(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, review = _window(qtbot)
    notified: list[int] = []
    monkeypatch.setattr(review, "on_owner_terminal", lambda epoch: notified.append(epoch))
    review.restore._phase = "pending"
    review.restore._epoch = 17

    window._notify_named_review_terminal()
    window.viewer.geometry_settled.emit()
    window.multi_compare_view.viewers[0].display_preview_settled.emit()
    window.viewer.first_frame_painted.emit("test")
    assert notified == [17, 17, 17, 17]

    review.restore._phase = "verified"
    window._notify_named_review_terminal()
    assert len(notified) == 4

    review.restore._phase = "pending"
    window.viewer.view_box.user_navigation_started.emit()
    assert review.restore.phase == "idle"
    window._notify_named_review_terminal()
    assert len(notified) == 4
    window.close()


def test_review_shutdown_precedes_viewer_teardown(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, review = _window(qtbot)
    original = review.shutdown
    observed: list[bool] = []

    def shutdown_before_viewers() -> None:
        observed.append(not window.viewer._graphics_resources_disposed)
        original()

    monkeypatch.setattr(review, "shutdown", shutdown_before_viewers)
    window.close()
    assert observed == [True]
    assert review._closed
