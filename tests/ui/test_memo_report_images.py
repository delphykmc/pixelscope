import cv2
import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog
from test_memo_evidence import windows as memo_windows

from pixelscope.core.image_document import ImageDocument
from pixelscope.core.roi import RoiBounds
from pixelscope.io.memo_archive import load_memo_archive
from pixelscope.ui.image_viewer import ImageViewer

windows = memo_windows
pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def test_passive_memo_rectangles_do_not_change_analysis_roi_or_fit_range(qtbot):
    viewer = ImageViewer()
    qtbot.addWidget(viewer)
    viewer.resize(600, 480)
    viewer.show()
    viewer.set_document(ImageDocument.from_array(np.zeros((80, 120), np.uint8), "image"))
    qtbot.waitUntil(lambda: not viewer._geometry_timer.isActive())
    selected = RoiBounds(2, 3, 20, 15)
    viewer.set_roi_bounds(selected)
    before = viewer.view_box.viewRange()
    viewer.set_memo_regions(
        (("ROI 1 · sharpness", selected, True), ("ROI 2", RoiBounds(60, 40, 8, 9), False))
    )
    assert viewer.current_roi_bounds() == selected
    assert viewer.view_box.viewRange() == before
    for rectangle, label in viewer._memo_items:
        assert rectangle.acceptedMouseButtons() == Qt.MouseButton.NoButton
        assert label.acceptedMouseButtons() == Qt.MouseButton.NoButton
    viewer.set_memo_regions(())
    assert not viewer._memo_items and viewer.current_roi_bounds() == selected
    viewer.shutdown()
    viewer.shutdown()


@pytest.mark.parametrize("failure", ["folder", "renderer"])
def test_default_save_suggestion_and_atomic_folder_failure_retry(
    qtbot, monkeypatch, tmp_path, request, failure
):
    create = request.getfixturevalue("windows")
    source = tmp_path / "reference.png"
    assert cv2.imwrite(str(source), np.full((72, 96, 3), 80, np.uint8))
    window, memo = create()
    memo.show()
    window.open_image_paths([source])
    qtbot.waitUntil(
        lambda: window.viewer.document is not None
        and window.viewer.document.loading_state == "ready"
        and not window.viewer._geometry_timer.isActive(),
        timeout=10000,
    )
    assert window._shared_roi_changed(RoiBounds(2, 3, 16, 12))
    qtbot.waitUntil(lambda: memo._capture_worker is None, timeout=10000)
    target = tmp_path / "notes" / "notes.pxmemo"
    report = target.parent
    if failure == "folder":
        report.mkdir()
        (report / "user.txt").write_text("keep my file")
    else:
        from pixelscope.io import memo_folder as module

        original_render = module.write_memo_report

        def fail_render(*_args):
            raise RuntimeError("simulated rendering failure")

        monkeypatch.setattr(module, "write_memo_report", fail_render)
    chosen = []

    def choose(*args):
        chosen.append(args[2])
        return str(target), ""

    monkeypatch.setattr(QFileDialog, "getSaveFileName", choose)
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import QMessageBox

    opened, warnings = [], []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url) or True)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args))
    memo.save_dialog()
    qtbot.waitUntil(lambda: memo._io_worker is None, timeout=10000)
    assert chosen[0].startswith("Memo_reference_") and chosen[0].endswith(".pxmemo")
    assert "failed" in memo.panel.last_status
    assert not opened and warnings  # failures stay visible without a footer label
    assert not target.exists() and memo.library.path is None and memo.library.dirty
    if failure == "folder":
        assert (report / "user.txt").read_text() == "keep my file"
        (report / "user.txt").unlink()
        report.rmdir()
    else:
        monkeypatch.setattr(module, "write_memo_report", original_render)
    memo.save_dialog()
    qtbot.waitUntil(lambda: memo._io_worker is None, timeout=10000)
    _, revision = load_memo_archive(target)
    assert len(opened) == 1 and opened[0].toLocalFile().endswith("/index.html")
    assert memo.library.revision == revision and not memo.library.dirty
    memo.panel.note_edit.setPlainText("Another edit")
    memo.save_dialog()
    qtbot.waitUntil(lambda: memo._io_worker is None, timeout=10000)
    archive, new_revision = load_memo_archive(target)
    assert memo.library.revision == new_revision != revision
    assert archive.review.findings[0].note == "Another edit"
    assert len(chosen) == 2  # A failed initial save never attaches a destination.
    window.close()


def test_legacy_zip_save_creates_folder_without_replacing_legacy_file(
    qtbot, monkeypatch, tmp_path, request
):
    from pixelscope.io.memo_archive import MemoArchive, save_memo_archive

    window, memo = request.getfixturevalue("windows")()
    source = tmp_path / "source.png"
    assert cv2.imwrite(str(source), np.full((48, 64, 3), 90, np.uint8))
    window.open_image_paths([source])
    qtbot.waitUntil(
        lambda: window.viewer.document is not None
        and window.viewer.document.loading_state == "ready"
        and not window.viewer._geometry_timer.isActive(),
        timeout=10000,
    )
    window._shared_roi_changed(RoiBounds(2, 3, 12, 10))
    qtbot.waitUntil(lambda: memo._capture_worker is None, timeout=10000)
    legacy = tmp_path / "legacy.pxmemo"
    save_memo_archive(legacy, MemoArchive(memo.library.document, memo._crops))
    original = legacy.read_bytes()
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_a: (str(legacy), ""))
    memo.open_dialog()
    qtbot.waitUntil(
        lambda: memo._io_worker is None and memo.restore.phase == "applied", timeout=15000
    )
    memo.save_dialog()
    qtbot.waitUntil(lambda: memo._io_worker is None, timeout=10000)
    assert memo.library.path == tmp_path / "legacy" / "legacy.pxmemo"
    assert memo.library.path.is_file() and not memo.library.dirty
    assert legacy.read_bytes() == original
    assert not memo.library.path.read_bytes().startswith(b"PK")
    window.close()


def test_committed_folder_cleanup_warning_preserves_ui_revision(
    qtbot, monkeypatch, tmp_path, request
):
    from pixelscope.io import memo_folder

    window, memo = request.getfixturevalue("windows")()
    source = tmp_path / "source.png"
    assert cv2.imwrite(str(source), np.full((48, 64, 3), 70, np.uint8))
    window.open_image_paths([source])
    qtbot.waitUntil(
        lambda: window.viewer.document is not None
        and window.viewer.document.loading_state == "ready"
        and not window.viewer._geometry_timer.isActive(),
        timeout=10000,
    )
    window._shared_roi_changed(RoiBounds(2, 3, 12, 10))
    qtbot.waitUntil(lambda: memo._capture_worker is None, timeout=10000)
    target = tmp_path / "notes" / "notes.pxmemo"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_a: (str(target), ""))

    def fail_cleanup(*_args):
        raise PermissionError("backup in use")

    with monkeypatch.context() as patch:
        patch.setattr(memo_folder, "_remove_staging", fail_cleanup)
        memo.save_dialog()
        qtbot.waitUntil(lambda: memo._io_worker is None, timeout=10000)
    assert "cleanup pending" in memo.panel.last_status
    assert memo.panel.header.text() == "● Saved" and not memo.library.dirty
    assert memo.library.revision == load_memo_archive(target)[1]
    memo.panel.note_edit.setPlainText("saved after cleanup warning")
    memo.save_dialog()
    qtbot.waitUntil(lambda: memo._io_worker is None, timeout=10000)
    loaded, revision = load_memo_archive(target)
    assert memo.library.revision == revision and not memo.library.dirty
    assert loaded.review.findings[0].note == "saved after cleanup warning"
    window.close()


def test_existing_destination_refusal_is_visible_without_footer(
    qtbot, monkeypatch, tmp_path, windows
):
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import QMessageBox

    window, memo = windows()
    target = tmp_path / "occupied" / "occupied.pxmemo"
    target.parent.mkdir()
    target.write_bytes(b"owner data")
    warnings, opened = [], []
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_a: (str(target), ""))
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args))
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url) or True)
    memo.save_dialog()
    assert warnings and "Destination exists" in warnings[0][2]
    assert not opened and memo._io_worker is None and memo.library.path is None
    assert target.read_bytes() == b"owner data"
    window.close()
