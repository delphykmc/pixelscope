import cv2
import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QPushButton
from test_memo_evidence import windows as memo_windows

from pixelscope.core.roi import RoiBounds
from pixelscope.io.memo_archive import MemoArchive, load_memo_archive

windows = memo_windows

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def test_roi_notes_edit_in_memory_save_and_reset(qtbot, monkeypatch, tmp_path, request):
    windows = request.getfixturevalue("windows")
    paths = []
    for i in range(2):
        path = tmp_path / f"source{i}.png"
        assert cv2.imwrite(str(path), np.full((72, 96, 3), 40 + i, np.uint8))
        paths.append(path)
    w, m = windows()
    m.show()
    w.open_image_paths(paths)
    w.set_layout_mode("Multi View")
    qtbot.waitUntil(
        lambda: len(w.multi_compare_view.occupied_viewers) == 2
        and all(
            v.document is not None
            and v.document.loading_state == "ready"
            and v.measure_physical_zoom().valid
            and not v._geometry_timer.isActive()
            for v in w.multi_compare_view.occupied_viewers
        ),
        timeout=15000,
    )
    first = RoiBounds(2, 3, 16, 12)
    second = RoiBounds(30, 20, 20, 16)
    assert w._shared_roi_changed(first)
    qtbot.waitUntil(lambda: m._capture_worker is None, timeout=15000)
    assert len(m.library.document.findings) == 1, m.panel.status.text()
    m.panel.note_edit.setPlainText("First ROI note")
    assert m.library.document.findings[0].note == "First ROI note"
    assert w._shared_roi_changed(second)
    assert not m.panel.note_edit.toPlainText()
    qtbot.waitUntil(lambda: m._capture_worker is None, timeout=15000)
    assert len(m.library.document.findings) == 2, m.panel.status.text()
    for viewer in w.multi_compare_view.occupied_viewers:
        assert len(viewer._memo_items) == 2
        assert [item[0] for item in viewer._memo_regions] == ["ROI 1", "ROI 2"]
    m.panel.note_edit.setPlainText("Second ROI note")
    m.panel.findings.setCurrentRow(0)
    qtbot.waitUntil(lambda: m.restore.phase == "applied", timeout=15000)
    assert w._shared_roi == first
    assert all(v._memo_regions[0][2] for v in w.multi_compare_view.occupied_viewers)
    assert m.panel.note_edit.toPlainText() == "First ROI note"
    from pixelscope.app.main_window import MainWindow

    generations = [(d.generation, id(d.source)) for d in w.current_comparison_documents()]

    def forbidden_reload(*_args, **_kwargs):
        raise AssertionError("Cached Memo selection must not rebuild or reload viewers")

    with monkeypatch.context() as patch:
        for method in ("_render_selection", "_register_input", "_mark_document_for_reload"):
            patch.setattr(MainWindow, method, forbidden_reload)
        for row in (1, 0, 1, 0):
            m.panel.findings.setCurrentRow(row)
            assert w._shared_roi == (first if row == 0 else second)
            roi = first if row == 0 else second
            for viewer in w.multi_compare_view.occupied_viewers:
                ranges = viewer.view_box.viewRange()
                np.testing.assert_allclose(
                    [sum(ranges[0]) / 2, sum(ranges[1]) / 2],
                    [roi.x + roi.width / 2, roi.y + roi.height / 2],
                )
    assert generations == [(d.generation, id(d.source)) for d in w.current_comparison_documents()]
    m.panel.note_edit.setPlainText("Edited immediately")
    target = tmp_path / "notes" / "notes.pxmemo"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), ""))
    m.save_dialog()
    qtbot.waitUntil(lambda: m._io_worker is None, timeout=10000)
    assert not m.library.dirty
    loaded, _ = load_memo_archive(target)
    assert loaded.review.findings[0].note == "Edited immediately"
    assert len(loaded.crops) == 4
    report_folder = target.parent
    assert (report_folder / "index.html").is_file()
    assert len(list((report_folder / "src/crops").glob("*.png"))) == 4
    assert report_folder.name in m.panel.status.text() and "Open report" in m.panel.status.text()
    assert str(report_folder / "index.html") == m.panel.status.toolTip()
    w.set_layout_mode("Single View")
    assert len(w.viewer._memo_items) == 2
    w.set_layout_mode("Multi View")
    assert all(len(v._memo_items) == 2 for v in w.multi_compare_view.occupied_viewers)
    report = (report_folder / "index.html").read_text(encoding="utf-8")
    assert "Edited immediately" in report
    assert str(tmp_path) not in report

    assert m.panel.header.text() == "● Saved"
    assert all(
        "Export" not in b.text() and "Update" not in b.text()
        for b in m.panel.findChildren(QPushButton)
    )
    ids = [d.document_id for d in w.current_comparison_documents()]
    old_snapshot = MemoArchive(m.library.document, m._crops)
    w._select_document_ids(list(reversed(ids)))
    assert not m.library.document.findings
    assert not any(v._memo_items for v in (w.viewer, *w.multi_compare_view.viewers))
    assert not m.panel.note_edit.toPlainText()
    # A late Open callback cannot repopulate notes after the user's file reset.
    reset_document = m.library.document
    m._io_path = target
    m._io_snapshot = old_snapshot
    m._io_operation = "open"
    m._io_task_id = "superseded-open"
    m._io_succeeded("superseded-open", None, 0, (loaded, None, {}))
    assert m.library.document is reset_document
    w._select_document_ids(ids)
    assert not m.library.document.findings
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(target), ""))
    m.open_dialog()
    qtbot.waitUntil(lambda: m._io_worker is None, timeout=10000)
    qtbot.waitUntil(lambda: m.restore.phase == "applied", timeout=15000)
    assert len(m.library.document.findings) == 2
    assert all(len(v._memo_items) == 2 for v in w.multi_compare_view.occupied_viewers)
    assert m.panel.note_edit.toPlainText() == "Edited immediately"
    m.panel.findings.setCurrentRow(1)
    qtbot.waitUntil(lambda: m.restore.phase == "applied", timeout=15000)
    assert w._shared_roi == second
    assert m.panel.note_edit.toPlainText() == "Second ROI note"
    m.panel.findings.setFocus()
    qtbot.keyClick(m.panel.findings, Qt.Key.Key_Delete)
    assert len(m.library.document.findings) == 1
    assert all(len(v._memo_items) == 1 for v in w.multi_compare_view.occupied_viewers)
    m.dock.hide()
    assert w._shared_roi_changed(RoiBounds(45, 40, 10, 10))
    assert m._capture_worker is None
    assert len(m.library.document.findings) == 1  # hidden Memo does no capture work
    m.show()
    qtbot.waitUntil(lambda: m._capture_worker is None, timeout=15000)
    assert len(m.library.document.findings) == 1  # reopening does not capture an old ROI
    assert m.panel.record_button.isChecked()
    assert w._shared_roi_changed(RoiBounds(46, 40, 10, 10))
    qtbot.waitUntil(lambda: m._capture_worker is None, timeout=15000)
    assert len(m.library.document.findings) == 2
    assert not m.panel.note_edit.toPlainText()
    for finding in tuple(m.library.document.findings):
        m.delete(finding.id)
    assert m.library.dirty and not m.library.document.findings
    m.save_dialog()
    qtbot.waitUntil(lambda: m._io_worker is None, timeout=10000)
    assert m.panel.header.text() == "● Saved"
    assert not load_memo_archive(target)[0].review.findings
    w.close()


def test_roi_statistics_waits_for_existing_analysis_without_extra_user_command(
    qtbot,
    tmp_path,
    request,
):
    create = request.getfixturevalue("windows")
    path = tmp_path / "stats.png"
    assert cv2.imwrite(str(path), np.full((72, 96, 3), (15, 40, 80), np.uint8))
    w, memo = create()
    w.open_image_paths([path])
    qtbot.waitUntil(
        lambda: w.viewer.document is not None
        and w.viewer.document.loading_state == "ready"
        and w.viewer.measure_physical_zoom().valid
        and not w.viewer._geometry_timer.isActive(),
        timeout=10000,
    )
    memo.panel.include_statistics.setChecked(True)
    assert w._shared_roi_changed(RoiBounds(3, 4, 16, 12))
    qtbot.waitUntil(
        lambda: len(memo.library.document.findings) == 1 and memo._capture_worker is None,
        timeout=15000,
    )
    assert not memo._pending_statistics
    assert memo.library.document.findings[0].analysis[0].status == "captured"
    assert memo.panel.note_edit.isEnabled()
    memo.panel.note_edit.setPlainText("ROI statistics are stored with this note")
    assert memo.library.document.findings[0].note == "ROI statistics are stored with this note"
    w.close()


@pytest.mark.parametrize("floating", [False, True])
def test_recording_toggle_escape_and_delete_are_independent(
    qtbot, monkeypatch, tmp_path, windows, floating
):
    from PySide6.QtWidgets import QApplication

    path = tmp_path / "record.png"
    assert cv2.imwrite(str(path), np.full((72, 96, 3), 80, np.uint8))
    w, m = windows()
    m.dock.setFloating(floating)
    m.show()
    w.open_image_paths([path])
    qtbot.waitUntil(
        lambda: w.viewer.document is not None
        and w.viewer.document.loading_state == "ready"
        and w.viewer.measure_physical_zoom().valid
        and not w.viewer._geometry_timer.isActive(),
        timeout=15000,
    )
    assert m.panel.record_button.isChecked()
    assert not any(b.text() in ("Add ROI", "Delete") for b in m.panel.findChildren(QPushButton))
    assert w._shared_roi_changed(RoiBounds(2, 3, 16, 12))
    qtbot.waitUntil(lambda: m._capture_worker is None, timeout=15000)
    assert len(m.library.document.findings) == 1, m.panel.status.text()
    m.panel.note_edit.setPlainText("Keep this note")
    m._wait_for_statistics("Waiting for ROI Statistics")
    m.panel.record_button.click()
    assert not m.panel.record_button.isChecked()
    assert not m._pending_statistics and not m._pending_roi
    epoch = m._capture_epoch
    assert w._shared_roi_changed(RoiBounds(30, 20, 20, 16))
    assert m._capture_epoch == epoch and m._capture_worker is None
    assert len(m.library.document.findings) == 1
    # Viewing/editing old notes is independent of recording new ROIs.
    m.panel.findings.setCurrentRow(-1)
    m.panel.findings.setCurrentRow(0)
    assert w._shared_roi == RoiBounds(2, 3, 16, 12)
    assert m.panel.note_edit.toPlainText() == "Keep this note"
    m.panel.record_button.click()
    assert len(m.library.document.findings) == 1  # enabling does not recapture
    m._wait_for_statistics("Waiting for ROI Statistics")
    m._pending_roi = True
    epoch = m._capture_epoch
    restore_epoch = m.restore.epoch
    w.action_map["Clear ROI"].trigger()  # the canonical Esc command
    assert w._shared_roi is None
    assert not m._pending_statistics and not m._pending_roi
    assert m._capture_worker is None and m._capture_epoch > epoch
    assert m.restore.epoch > restore_epoch and m.restore.phase == "idle"
    assert m.panel.selected_finding_id is None and not m.panel.note_edit.toPlainText()
    assert len(m.library.document.findings) == 1
    with monkeypatch.context() as patch:
        patch.setattr(m, "add", lambda: pytest.fail("cancelled work must not restart"))
        m._resume_statistics()
    m.panel.findings.setCurrentRow(0)
    QApplication.setActiveWindow(m.dock if floating else w)
    m.panel.note_edit.setFocus()
    qtbot.keyClick(m.panel.note_edit, Qt.Key.Key_Delete)
    assert len(m.library.document.findings) == 1  # text Delete never deletes an ROI
    m.panel.findings.setFocus()
    qtbot.keyClick(m.panel.findings, Qt.Key.Key_Delete)
    assert not m.library.document.findings and m.library.dirty
    assert not w.viewer._memo_items
    qtbot.keyClick(m.panel.findings, Qt.Key.Key_Delete)  # empty list is harmless
    w.close()
