from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtWidgets import QDialog

from pixelscope.io.input_profile_batch import (
    ProfileBatchCandidate,
    preflight_input_profile_batch,
)
from pixelscope.io.raw_profile import RawProfile
from pixelscope.io.yuv_profile import YuvProfile
from pixelscope.ui.input_profile_batch import (
    BatchProfileApprovalDialog,
    BatchProfileController,
    CanonicalBatchProfileAdapter,
    InputProfileBatchDialog,
)
from pixelscope.ui.native_input_preview import (
    NativeInputPreview,
    NativeInputPreviewController,
    native_interpretation_preview,
)

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _raw() -> RawProfile:
    return RawProfile(
        name="W08b",
        width=8,
        height=4,
        stride_bytes=16,
        storage_format="unpacked",
        container_dtype="uint16",
        endianness="little",
        bit_depth=12,
        bit_alignment="lsb",
        channel_layout="GRAY",
        black_level=0,
        white_level=4095,
    )


def _files(tmp_path: Path, number: int) -> tuple[Path, ...]:
    paths = tuple(tmp_path / f"{i}.raw" for i in range(number))
    for path in paths:
        np.arange(32, dtype=np.uint16).tofile(path)
    return paths


def test_preflight_then_confirm_four_without_selection_authority(
    qtbot: object, tmp_path: Path
) -> None:
    paths = _files(tmp_path, 4)
    changes: list[Path] = []
    results: list[object] = []
    controller = BatchProfileController(
        lambda candidate: (changes.append(candidate.path) or f"doc-{len(changes)}")
    )
    controller.preflight_ready.connect(lambda _epoch, _value: None)
    controller.commit_finished.connect(results.append)
    epoch = controller.preflight(paths, _raw())
    assert changes == []
    qtbot.waitUntil(lambda: controller.phase == "ready", timeout=10000)  # type: ignore[attr-defined]
    candidates = preflight_input_profile_batch(paths, _raw())
    # Staged value-equivalent candidates are eligible; no mutation pre-approval.
    assert all(item.eligible for item in candidates)
    controller.approve(epoch, candidates)
    qtbot.waitUntil(lambda: len(results) == 1, timeout=10000)  # type: ignore[attr-defined]
    assert changes == list(paths)
    assert results[0].applied == 4
    assert not results[0].interrupted
    controller.shutdown()


def test_cancel_before_approval_drops_late_preflight(qtbot: object, tmp_path: Path) -> None:
    paths = _files(tmp_path, 2)
    commits: list[str] = []
    ready: list[int] = []
    controller = BatchProfileController(lambda _candidate: (commits.append("committed") or "doc"))
    controller.preflight_ready.connect(lambda epoch, _value: ready.append(epoch))
    epoch = controller.preflight(paths, _raw())
    controller.cancel()
    # An already queued signal must not resurrect an approved batch.
    controller._on_preflight_ready("stale-task", None, epoch, ())
    qtbot.wait(80)  # type: ignore[attr-defined]
    assert ready == [] and commits == []
    assert controller.phase == "idle"
    controller.shutdown()


def test_cancel_after_first_commit_reports_partial(qtbot: object, tmp_path: Path) -> None:
    paths = _files(tmp_path, 3)
    touched: list[Path] = []
    results: list[object] = []
    controller = BatchProfileController(
        lambda row: (touched.append(row.path) or f"doc{len(touched)}")
    )
    controller.commit_finished.connect(results.append)
    controller.commit_progress.connect(
        lambda _epoch, _row: controller.cancel() if len(touched) == 1 else None
    )
    epoch = controller.preflight(paths, _raw())
    qtbot.waitUntil(lambda: controller.phase == "ready", timeout=10000)  # type: ignore[attr-defined]
    controller.approve(epoch, preflight_input_profile_batch(paths, _raw()))
    qtbot.waitUntil(lambda: bool(results), timeout=10000)  # type: ignore[attr-defined]
    assert touched == [paths[0]]
    assert results[0].interrupted
    assert [row.status for row in results[0].outcomes] == ["applied", "interrupted", "interrupted"]
    controller.shutdown()


@pytest.mark.parametrize(
    "packing,bit_depth,row_bytes",
    (
        ("mipi_raw10", 10, 10),
        ("mipi_raw12", 12, 12),
        ("mipi_raw14", 14, 14),
    ),
)
def test_packed_native_preview_preserves_decoder(
    tmp_path: Path, packing: str, bit_depth: int, row_bytes: int
) -> None:
    profile = RawProfile(
        name="packed",
        width=8,
        height=4,
        stride_bytes=row_bytes,
        storage_format=packing,
        bit_depth=bit_depth,
        channel_layout="GRAY",
        black_level=0,
        white_level=(1 << bit_depth) - 1,
    )
    path = tmp_path / "image.raw"
    path.write_bytes(bytes(row_bytes * 4))
    preview = native_interpretation_preview(path, profile, 12)
    assert preview.pixels.shape == (4, 8)
    assert preview.pixels.dtype == np.uint8
    assert preview.source_generation == 12


@pytest.mark.parametrize("layout", ["YUV444", "YUV422", "YUV420"])
def test_native_yuv_preview_is_presentation_only(tmp_path: Path, layout: str) -> None:
    profile = YuvProfile(width=8, height=4, channel_layout=layout)
    path = tmp_path / "image.yuv"
    path.write_bytes(bytes([120]) * profile.expected_file_size)
    preview = native_interpretation_preview(path, profile, 8)
    assert preview.pixels.shape == (4, 8, 3)
    assert preview.pixels.dtype == np.uint8


def test_preview_epoch_generation_close_and_late_callback(qtbot: object, tmp_path: Path) -> None:
    path = _files(tmp_path, 1)[0]
    preview = NativeInputPreviewController()
    accepted: list[NativeInputPreview] = []
    preview.preview_ready.connect(lambda _epoch, value: accepted.append(value))
    first = preview.request(path, _raw(), generation=1)
    changed_profile = _raw().copy(update={"black_level": 1})
    second = preview.request(path, changed_profile, generation=2)
    assert second > first
    qtbot.waitUntil(lambda: len(accepted) == 1, timeout=10000)  # type: ignore[attr-defined]
    assert accepted[0].source_generation == 2
    preview.shutdown()
    assert preview.epoch > second
    preview._succeeded("late-task", None, second, accepted[0])
    assert len(accepted) == 1


def test_adapter_register_and_reinterpret_preserves_existing_identity(
    qtbot: object, tmp_path: Path
) -> None:
    from pixelscope.app.main_window import MainWindow

    path = _files(tmp_path, 1)[0]
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    adapter = CanonicalBatchProfileAdapter(window)
    first = preflight_input_profile_batch((path,), _raw())[0]
    document_id = adapter.commit_one(first)
    assert document_id in window.documents
    assert window.documents[document_id].loading_state == "pending"
    assert window._raw_profiles[document_id].bit_depth == 12
    selected_before = [item.document_id for item in window.selected_documents]
    generation = window.documents[document_id].generation

    changed = _raw().copy(update={"name": "updated", "black_level": 3})
    second = preflight_input_profile_batch(
        (path,),
        changed,
        existing=adapter.existing((path,)),
        override_registered=True,
    )[0]
    assert isinstance(second, ProfileBatchCandidate)
    assert second.eligible
    assert adapter.commit_one(second) == document_id
    assert window.documents[document_id].generation == generation + 1
    assert [item.document_id for item in window.selected_documents] == selected_before
    assert window.documents[document_id].loading_state == "pending"


def test_adapter_reinterpret_offpage_defers_native_decode(tmp_path: Path) -> None:
    from pixelscope.core.image_document import ImageDocument

    path = _files(tmp_path, 1)[0]
    profile = _raw()
    document = ImageDocument.pending_document(path)
    document_id = document.document_id

    class StubCanonicalWindow:
        _closing = False

        def __init__(self) -> None:
            self.documents = {document_id: document}
            self._document_id_by_path = {str(path): document_id}
            self._raw_profiles = {document_id: profile}
            self._raw_profile_prompt_suppressed: set[str] = set()
            self._current_page: list[ImageDocument] = []
            self.reloads: list[str] = []
            self.refresh_calls: list[str] = []

        @staticmethod
        def _path_key(candidate: Path) -> str:
            return str(candidate)

        def _mark_document_for_reload(self, target_id: str, _profile: object) -> None:
            self.reloads.append(target_id)
            self.documents[target_id].generation += 1

        def current_comparison_documents(self) -> list[ImageDocument]:
            return self._current_page

        def _refresh_reopened_selected_documents(self, ids: list[str]) -> None:
            self.refresh_calls.extend(ids)

    owner = StubCanonicalWindow()
    adapter = CanonicalBatchProfileAdapter(owner)
    changed = profile.copy(update={"black_level": 2})
    candidates = preflight_input_profile_batch(
        (path,), changed, existing=adapter.existing((path,)), override_registered=True
    )
    assert candidates[0].eligible
    assert adapter.commit_one(candidates[0]) == document_id
    assert owner.reloads == [document_id]
    assert owner.refresh_calls == []
    assert owner.documents[document_id].generation == 1

    owner._current_page = [document]
    newer = profile.copy(update={"black_level": 4})
    next_candidate = preflight_input_profile_batch(
        (path,), newer, existing=adapter.existing((path,)), override_registered=True
    )[0]
    assert adapter.commit_one(next_candidate) == document_id
    assert owner.refresh_calls == [document_id]


@pytest.mark.parametrize(
    "changed_key,new_value,before_fragment,after_fragment",
    (
        ("endianness", "big", "endianness=little", "endianness=big"),
        ("bayer_pattern", "BGGR", "bayer_pattern=RGGB", "bayer_pattern=BGGR"),
    ),
)
def test_dialog_discloses_full_native_before_after_and_sidecar_override(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: object,
    changed_key: str,
    new_value: str,
    before_fragment: str,
    after_fragment: str,
) -> None:
    from pixelscope.app.main_window import MainWindow

    path = _files(tmp_path, 1)[0]
    old = _raw().copy(update={"channel_layout": "BAYER", "bayer_pattern": "RGGB"})
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    adapter = CanonicalBatchProfileAdapter(window)
    source_id = adapter.commit_one(preflight_input_profile_batch((path,), old)[0])
    previous_generation = window.documents[source_id].generation
    (tmp_path / "0.json").write_text("{}", encoding="utf-8")
    proposed = old.copy(update={changed_key: new_value})
    dialog = InputProfileBatchDialog(window, (path,))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog._profiles.append(proposed)
    dialog.profile_box.addItem("W08b changed native interpretation")
    dialog.profile_box.setCurrentIndex(dialog.profile_box.count() - 1)
    dialog.override_registered.setChecked(True)
    dialog.override_sidecars.setChecked(True)
    dialog._start_preflight()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: dialog._batch.phase == "ready" and len(dialog._candidates) == 1,
        timeout=10000,
    )
    candidate = dialog._candidates[0]
    assert candidate.previous_profile == old
    assert candidate.previous_profile is not old
    assert candidate.sidecar_override
    assert candidate.eligible
    details = dialog.details_panel.toPlainText()
    assert before_fragment in details and after_fragment in details
    assert str(path) in details
    assert str(path.with_suffix(".json")) in details
    assert "Sidecar interpretation override: YES" in details
    assert before_fragment in dialog.table.item(0, 1).text()
    assert after_fragment in dialog.table.item(0, 2).text()
    assert "OVERRIDE REQUESTED" in dialog.table.item(0, 3).text()

    captured: list[str] = []

    def confirm(approval: BatchProfileApprovalDialog) -> QDialog.DialogCode:
        captured.append(approval.details.toPlainText())
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(BatchProfileApprovalDialog, "exec", confirm)  # type: ignore[attr-defined]
    dialog._approve()
    assert len(captured) == 1
    assert before_fragment in captured[0] and after_fragment in captured[0]
    assert "Sidecar interpretation override: YES" in captured[0]
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: dialog._last_batch_result is not None,
        timeout=10000,
    )
    assert dialog._last_batch_result is not None
    assert dialog._last_batch_result.applied == 1
    assert window.documents[source_id].generation == previous_generation + 1
    assert getattr(window._raw_profiles[source_id], changed_key) == new_value
    assert "1 applied" in dialog.status.text()
    dialog.reject()


def test_dialog_four_applied_remains_truthful_after_cancel_pending(
    qtbot: object, tmp_path: Path, monkeypatch: object
) -> None:
    from pixelscope.app.main_window import MainWindow

    paths = _files(tmp_path, 4)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    dialog = InputProfileBatchDialog(window, paths)
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog._profiles.append(_raw())
    dialog.profile_box.addItem("W08b RAW profile")
    dialog.profile_box.setCurrentIndex(dialog.profile_box.count() - 1)
    dialog._start_preflight()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: dialog._batch.phase == "ready" and len(dialog._candidates) == 4,
        timeout=10000,
    )
    approvals: list[str] = []

    def confirm(approval: BatchProfileApprovalDialog) -> QDialog.DialogCode:
        approvals.append(approval.details.toPlainText())
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(BatchProfileApprovalDialog, "exec", confirm)  # type: ignore[attr-defined]
    dialog._approve()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: dialog._last_batch_result is not None,
        timeout=10000,
    )
    assert dialog._last_batch_result is not None
    assert dialog._last_batch_result.applied == 4
    assert len(approvals) == 1
    assert all(str(path) in approvals[0] for path in paths)
    assert dialog._batch.phase == "finished"
    assert not dialog.stop_button.isEnabled()
    before = dialog.status.text()
    assert "4 applied" in before
    ids = dict(window._document_id_by_path)
    dialog.stop_button.click()
    dialog._cancel()
    assert dialog.status.text() == before
    assert dialog._last_batch_result.applied == 4
    assert window._document_id_by_path == ids
    dialog.reject()
