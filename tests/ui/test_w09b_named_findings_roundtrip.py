"""Real native files and production composition across a fresh Review window."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtWidgets import QDialog, QFileDialog

from pixelscope.app.bootstrap import compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.line_profile import LineSelection
from pixelscope.core.roi import RoiBounds
from pixelscope.io.raw_profile import RawProfile
from pixelscope.io.yuv_profile import YuvProfile
from pixelscope.ui.difference_panel import DifferencePanel
from pixelscope.ui.display_gain import display_gain_state
from pixelscope.ui.raw_open_dialog import RawOpenDialog
from pixelscope.ui.yuv_open_dialog import YuvOpenDialog

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _native_inputs(
    root: Path, *, create: bool = True
) -> tuple[list[Path], dict[Path, RawProfile | YuvProfile]]:
    paths: list[Path] = []
    profiles: dict[Path, RawProfile | YuvProfile] = {}
    for i in range(6):
        path = root / (f"source-{i}.raw" if i < 2 else f"source-{i}.yuv")
        if i < 2:
            profile = RawProfile(
                name="Review RAW12",
                width=64,
                height=48,
                stride_bytes=128,
                storage_format="unpacked",
                container_dtype="uint16",
                endianness="little",
                bit_depth=12,
                bit_alignment="lsb",
                channel_layout="GRAY",
                black_level=0,
                white_level=4095,
            )
            if create:
                np.full((48, 64), 1000 + i * 10, dtype="<u2").tofile(path)
        else:
            profile = YuvProfile(name="Review YUV420", width=64, height=48, channel_layout="YUV420")
            if create:
                path.write_bytes(bytes([40 + i]) * (64 * 48) + bytes([90, 160]) * (32 * 24))
        if create:
            profile.save_json(path.with_suffix(".json"))
        assert path.is_file()
        paths.append(path.resolve())
        profiles[path.resolve()] = profile
    return paths, profiles


def _window(qtbot: object) -> MainWindow:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    compose_main_window_presentation(window)
    window.resize(1480, 920)
    window.show()
    return window


def _settled(qtbot: object, window: MainWindow) -> None:
    def ready() -> bool:
        page = window.current_comparison_documents()
        return (
            bool(page)
            and all(d.source is not None and d.loading_state == "ready" for d in page)
            and (
                not window.multi_compare_view._layout_refit_active
                and all(
                    not v._geometry_timer.isActive()
                    and v._display_preview_worker is None
                    and v.measure_physical_zoom().valid
                    for v in window.multi_compare_view.occupied_viewers
                )
                and window.comparison_analysis_panel._worker is None
            )
        )

    qtbot.waitUntil(ready, timeout=10000)  # type: ignore[attr-defined]


def test_native_memo_resets_on_image_set_change_and_reopens_last_roi(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stage = os.environ.get("PIXELSCOPE_FINDING_TEST_STAGE")
    if stage is None:
        # Independent interpreters prove that no QObject, source registry or
        # in-memory ReviewLibrary survives the save/restart boundary.
        for phase in ("save", "restore"):
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    f"{__file__}::"
                    "test_native_memo_resets_on_image_set_change_and_reopens_last_roi",
                    "-q",
                    f"--basetemp={tmp_path / phase}",
                ],
                env={
                    **os.environ,
                    "PIXELSCOPE_FINDING_TEST_STAGE": phase,
                    "PIXELSCOPE_FINDING_TEST_ROOT": str(tmp_path),
                },
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            assert result.returncode == 0, result.stdout + result.stderr
        return
    tmp_path = Path(os.environ["PIXELSCOPE_FINDING_TEST_ROOT"])
    review_path = tmp_path / "three-findings.pxmemo"
    paths, profiles = _native_inputs(tmp_path, create=stage == "save")
    errors: list[str] = []
    if stage == "restore":
        _restore(qtbot, monkeypatch, paths, profiles, errors, review_path)
        return
    window = _window(qtbot)
    review = window.named_review_coordinator
    monkeypatch.setattr(review, "_error", errors.append)
    # Production input confirmation remains explicit; automate acceptance of
    # the concrete profiles loaded from these synthetic JSON sidecars.
    monkeypatch.setattr(RawOpenDialog, "exec", lambda _self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(YuvOpenDialog, "exec", lambda _self: QDialog.DialogCode.Accepted)
    window.open_image_paths(paths)
    _settled(qtbot, window)
    source_ids = [window._document_id_by_path[window._path_key(p)] for p in paths]
    for index, count in enumerate((2, 4, 6)):
        window._select_document_ids(source_ids[:count])
        _settled(qtbot, window)
        window._apply_shared_roi(
            RoiBounds(index + 1, index + 2, 16 + index * 4, 12 + index * 3),
            allow_channel_split=False,
        )
        window._shared_line_changed(LineSelection(1, 2, 30 + index, 20 + index))
        display_gain_state().set_gain(1.0 + index * 0.5)
        _settled(qtbot, window)
        window.sync_action.setChecked(index != 1)
        for slot, viewer in enumerate(window.multi_compare_view.occupied_viewers):
            viewer.set_physical_zoom(
                125 + index * 25 + (slot * 10 if index == 1 else 0),
                (30 + (slot if index == 1 else 0), 22),
            )
        review.panel.title_edit.setText(f"Finding {index + 1}")
        review.add()
        qtbot.waitUntil(
            lambda expected=1: bool(errors) or len(review.library.document.findings) == expected,
            timeout=10000,
        )  # type: ignore[attr-defined]
        assert not errors
        qtbot.waitUntil(lambda: review._capture_worker is None, timeout=10000)  # type: ignore[attr-defined]
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_a, **_kw: (str(review_path), ""))
    review.save_dialog()
    qtbot.waitUntil(lambda: review._io_worker is None, timeout=10000)
    assert review_path.is_file() and not review.library.dirty
    window.close()
    display_gain_state().set_gain(1.0)


def _restore(qtbot, monkeypatch, paths, profiles, errors, review_path):
    calls: list[bool] = []
    calculate_code = DifferencePanel.calculate_difference.__code__
    previous_profile = sys.getprofile()

    def observe(frame, event, _arg):
        if event == "call" and frame.f_code is calculate_code:
            calls.append(frame.f_locals.get("publish_result", True))

    # Observe the original code object, including W05's owned callback, without
    # replacing a QObject method or altering PySide's dynamic signal metadata.
    sys.setprofile(observe)
    try:
        _restore_library(qtbot, monkeypatch, paths, profiles, errors, review_path, calls)
    finally:
        sys.setprofile(previous_profile)


def _restore_library(qtbot, monkeypatch, paths, profiles, errors, review_path, calls):
    restored = _window(qtbot)
    fresh = restored.named_review_coordinator
    fresh.action.trigger()
    monkeypatch.setattr(fresh, "_error", errors.append)
    # Native input approval belongs to the existing File workflow, never Memo.
    monkeypatch.setattr(RawOpenDialog, "exec", lambda _self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(YuvOpenDialog, "exec", lambda _self: QDialog.DialogCode.Accepted)
    restored.open_image_paths(paths)
    _settled(qtbot, restored)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_a, **_kw: (str(review_path), ""))
    fresh.open_dialog()
    qtbot.waitUntil(lambda: fresh._io_worker is None, timeout=10000)
    assert len(fresh.library.document.findings) == 1
    recorded = fresh.library.document
    assert len(restored.current_comparison_documents()) == 6
    for finding_index, finding in enumerate(recorded.findings):
        row = next(
            i
            for i in range(fresh.panel.findings.count())
            if fresh.panel.findings.item(i).data(256) == finding.id
        )
        fresh.panel.findings.setCurrentRow(row)
        qtbot.waitUntil(
            lambda: fresh.restore.phase in ("applied", "unavailable", "interrupted")
            or bool(errors),
            timeout=10000,
        )  # type: ignore[attr-defined]
        assert not errors
        assert fresh.restore.phase == "applied", fresh.panel.status.text()
        assert len(restored.current_comparison_documents()) == len(finding.source_keys)
        assert restored._shared_roi == RoiBounds(*finding.roi_ref)
        assert restored._shared_line == LineSelection(*finding.line_ref)
        assert restored.multi_compare_view.layout_kind == finding.view_state.layout_kind
        assert restored.sync_action.isChecked() == finding.view_state.sync_enabled
        assert display_gain_state().gain == finding.display_gain
        pair = restored.difference_panel.selected_documents()
        assert pair is not None
        intent = finding.difference_intent
        assert intent is not None
        assert tuple(
            restored.comparison_analysis_panel.source_key_for_document(d.document_id) for d in pair
        ) == (intent.reference_key, intent.target_key)
        assert restored.difference_panel.channel.currentText() == intent.channel
        assert restored.difference_panel.mode.currentText() == intent.mode
        assert restored.difference_panel.region.currentText() == intent.region
        assert restored.difference_panel.gain.value() == intent.gain
        assert restored.difference_panel.threshold.value() == intent.threshold
        for viewer in restored.multi_compare_view.occupied_viewers:
            key = restored.comparison_analysis_panel.source_key_for_document(
                viewer.document.document_id
            )
            viewport = finding.view_state.per_source.get(key)
            expected_scale = (
                viewport.physical_scale if viewport else finding.view_state.physical_scale
            )
            assert viewer.measure_physical_zoom().percent == pytest.approx(100 * expected_scale)
        assert not restored.diff_action.isChecked()
        assert restored.difference_panel.get_presented_difference_token() is None
        assert restored.difference_panel.last_result is None
        assert restored.difference_panel._worker is None
        assert calls == []
        assert restored.grab().save(str(review_path.with_name(f"restored-{finding_index + 1}.png")))
    restored.close()
    display_gain_state().set_gain(1.0)
