"""W09b production composition and owner-terminal event contract tests."""

from __future__ import annotations

import pytest

from pixelscope.app.bootstrap import compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.ui.review_window_integration import NamedReviewCoordinator

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
    view = window._menu_map["View"]
    assert review.action in view.actions()
    assert review.action not in window.main_toolbar.actions()
    assert review.dock in window._contributed_docks
    assert review.dock.isHidden()
    assert review.panel.findings.count() == 0

    window.show()
    original_workspace = window.beta_workspace_hardening_controller.workspace_presets.preset
    assert review.action.isCheckable()
    assert not review.action.isChecked()
    review.action.trigger()
    assert not review.dock.isHidden()
    assert review.action.isChecked()
    # Opening notes is an explicit visibility action, not a layout preset switch.
    assert window.beta_workspace_hardening_controller.workspace_presets.preset is original_workspace

    review.action.trigger()
    assert review.dock.isHidden()
    assert not review.action.isChecked()

    # The native titlebar close action must also clear the View menu checkmark.
    review.action.trigger()
    assert review.action.isChecked()
    review.dock.close()
    assert not review.action.isChecked()
    assert review.dock.isHidden()

    # Memo is a View dock, not a second workspace mode.
    assert review.action.text() == "Memo"
    review.action.trigger()
    assert not review.dock.isHidden()
    review.action.trigger()
    assert review.dock.isHidden()
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


def test_memo_roi_png_export_no_roi_is_nonblocking(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from PySide6.QtWidgets import QFileDialog

    window, review = _window(qtbot)
    window.show()

    def forbid_dialog(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("No folder picker without an ROI")

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", forbid_dialog)
    assert review.panel.export_roi_button.text() == "Export ROI PNGs…"
    review.panel.export_roi_button.click()
    assert "ROI" in review.panel.status.text()
    window.close()


def test_memo_roi_png_export_selected_page_independent_of_review_save(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: object,
) -> None:
    from pathlib import Path

    import cv2
    import numpy as np
    from PySide6.QtWidgets import QFileDialog

    from pixelscope.core.roi import RoiBounds

    root = Path(str(tmp_path))
    target = root / "export"
    target.mkdir()
    images: list[Path] = []
    for index in (0, 1):
        path = root / f"rgb_{index}.png"
        source = np.full((12, 15, 3), (25 + index * 35, 80, 120), dtype=np.uint8)
        assert cv2.imwrite(str(path), source)
        images.append(path)
    window, review = _window(qtbot)
    window.resize(1400, 880)
    window.show()
    window.open_image_paths(images)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(window.current_comparison_documents()) == 2
        and all(
            document.loading_state == "ready" and document.preview is not None
            for document in window.current_comparison_documents()
        ),
        timeout=10000,
    )
    roi = RoiBounds(3, 4, 6, 5)
    assert window._apply_shared_roi(roi, allow_channel_split=False)
    monkeypatch.setattr(
        QFileDialog,
        "getExistingDirectory",
        lambda *_args, **_kwargs: str(target),
    )
    assert len(review.library.document.findings) == 0
    review.panel.export_roi_button.click()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(list(target.glob("*.png"))) == 2
        or review.panel.status.text().startswith("ROI PNG export failed"),
        timeout=10000,
    )
    assert review.panel.status.text().startswith("Exported 2 ROI PNG")
    assert len(review.library.document.findings) == 0
    for exported in target.glob("*.png"):
        pixels = cv2.imread(str(exported), cv2.IMREAD_UNCHANGED)
        assert pixels is not None and pixels.shape == (roi.height, roi.width, 3)
    window.close()


def test_single_rgb_memo_click_restores_roi_after_reopening(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: object,
) -> None:
    """Real default Single View: note selection restores image + precise ROI."""
    from pathlib import Path

    import cv2
    import numpy as np
    from PySide6.QtWidgets import QFileDialog

    from pixelscope.core.roi import RoiBounds

    root = Path(str(tmp_path))
    image = root / "inspection_rgb.png"
    assert cv2.imwrite(str(image), np.full((72, 96, 3), (15, 65, 155), dtype=np.uint8))
    memo_file = root / "inspection.pxreview"

    first_roi = RoiBounds(4, 5, 24, 18)
    second_roi = RoiBounds(38, 30, 26, 20)
    window, review = _window(qtbot)
    window.resize(1400, 880)
    window.show()
    window.open_image_paths([image])
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(window.current_comparison_documents()) == 1
        and window.viewer.document is not None
        and window.viewer.document.loading_state == "ready"
        and window.viewer.document.preview is not None
        and window.viewer.measure_physical_zoom().valid
        and not window.viewer._geometry_timer.isActive(),
        timeout=10000,
    )

    for title, roi in (("Halo", first_roi), ("Texture", second_roi)):
        assert window._apply_shared_roi(roi, allow_channel_split=False)
        review.panel.title_edit.setText(title)
        review.panel.note_edit.setPlainText("Measured at the exact selected ROI")
        review.add()
        expected = 1 if title == "Halo" else 2
        qtbot.waitUntil(  # type: ignore[attr-defined]
            lambda expected=expected: len(review.library.document.findings) == expected,
            timeout=15000,
        )
        qtbot.waitUntil(  # type: ignore[attr-defined]
            lambda: review._capture_worker is None,
            timeout=10000,
        )
    assert review.library.document.allow_local_paths
    assert all(
        source.locator.local_path == str(image.resolve())
        for source in review.library.document.sources
    )
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_args, **_kw: (str(memo_file), ""))
    review.save_dialog()
    assert memo_file.is_file()
    window.close()

    fresh, notes = _window(qtbot)
    fresh.resize(1400, 880)
    fresh.show()
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_args, **_kw: (str(memo_file), ""))
    notes.open_dialog()
    assert len(notes.library.document.findings) == 2
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: notes.restore.phase == "applied" and fresh._shared_roi == first_roi,
        timeout=15000,
    )
    assert fresh.viewer.document is not None
    assert fresh.viewer.document.source_path == image.resolve()

    notes.panel.findings.setCurrentRow(1)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: notes.restore.phase == "applied" and fresh._shared_roi == second_roi,
        timeout=15000,
    )
    assert notes.panel.title_edit.text() == "Texture"

    notes.panel.findings.setCurrentRow(0)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: notes.restore.phase == "applied" and fresh._shared_roi == first_roi,
        timeout=15000,
    )
    assert notes.panel.title_edit.text() == "Halo"
    fresh.close()
