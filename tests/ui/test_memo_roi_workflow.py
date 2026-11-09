import zipfile

import cv2
import numpy as np
import pytest
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
    m.panel.note_edit.setPlainText("Second ROI note")
    m.panel.findings.setCurrentRow(0)
    qtbot.waitUntil(lambda: m.restore.phase == "applied", timeout=15000)
    assert w._shared_roi == first
    assert m.panel.note_edit.toPlainText() == "First ROI note"
    m.panel.note_edit.setPlainText("Edited immediately")
    target = tmp_path / "notes.pxmemo"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), ""))
    m.save_dialog()
    qtbot.waitUntil(lambda: m._io_worker is None, timeout=10000)
    assert not m.library.dirty
    loaded, _ = load_memo_archive(target)
    assert loaded.review.findings[0].note == "Edited immediately"
    assert len(loaded.crops) == 4
    with zipfile.ZipFile(target) as saved:
        report = saved.read("index.html").decode("utf-8")
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
    assert m.panel.note_edit.toPlainText() == "Edited immediately"
    m.panel.findings.setCurrentRow(1)
    qtbot.waitUntil(lambda: m.restore.phase == "applied", timeout=15000)
    assert w._shared_roi == second
    assert m.panel.note_edit.toPlainText() == "Second ROI note"
    m.panel.delete_button.click()
    assert len(m.library.document.findings) == 1
    m.dock.hide()
    assert w._shared_roi_changed(RoiBounds(45, 40, 10, 10))
    assert m._capture_worker is None
    assert len(m.library.document.findings) == 1  # hidden Memo does no capture work
    m.show()
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
