"""W08b batch profile transaction controller; registration stays in MainWindow."""

from __future__ import annotations

import weakref
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pixelscope.io.input_profile_batch import (
    ExistingProfileBinding,
    InputProfile,
    ProfileBatchCandidate,
    candidate_file_is_current,
    preflight_input_profile_batch,
)
from pixelscope.io.path_discovery import ImageInput, raw_profile_sidecar_for_path
from pixelscope.io.raw_profile import RawProfile
from pixelscope.ui.input_profile_library import InputProfileLibrary
from pixelscope.ui.lifecycle_hooks import OwnerCallback
from pixelscope.ui.native_input_preview import (
    NativeInputPreview,
    NativeInputPreviewController,
)
from pixelscope.workers.task_worker import TaskWorker
from pixelscope.workers.thread_pools import analysis_thread_pool

BatchOutcomeStatus = Literal["applied", "skipped", "failed", "interrupted"]


@dataclass(frozen=True)
class BatchProfileOutcome:
    path: Path
    status: BatchOutcomeStatus
    reason: str
    document_id: str | None


@dataclass(frozen=True)
class ProfileBatchResult:
    epoch: int
    outcomes: tuple[BatchProfileOutcome, ...]
    interrupted: bool

    @property
    def applied(self) -> int:
        return sum(row.status == "applied" for row in self.outcomes)


class BatchProfileController(QObject):
    """Preflight/approval/commit: no mutation until explicit approval.

    A callback is invoked once for each eligible file on the GUI thread. It must
    use canonical registration/reload and must not alter selection/page roles.
    Cancellation after the first callback is explicitly non-atomic.
    """

    preflight_ready = Signal(int, object)
    preflight_failed = Signal(int, str)
    commit_progress = Signal(int, object)
    commit_finished = Signal(object)

    def __init__(
        self,
        commit_one: Callable[[ProfileBatchCandidate], str],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._commit_one = OwnerCallback(commit_one)
        self._epoch = 0
        self._worker: TaskWorker | None = None
        self._task_id: str | None = None
        self._candidates: tuple[ProfileBatchCandidate, ...] | None = None
        self._outcomes: list[BatchProfileOutcome] = []
        self._index = 0
        self._phase = "idle"
        self._closing = False

    @property
    def epoch(self) -> int:
        return self._epoch

    @property
    def phase(self) -> str:
        return self._phase

    def preflight(
        self,
        paths: tuple[Path, ...],
        profile: InputProfile,
        *,
        existing: Mapping[Path, ExistingProfileBinding] | None = None,
        override_sidecars: bool = False,
        override_registered: bool = False,
        require_exact_raw_size: bool = False,
    ) -> int:
        self.cancel()
        if self._closing:
            raise RuntimeError("Batch controller is shut down")
        self._phase = "preflight"
        epoch = self._epoch
        worker = TaskWorker(
            preflight_input_profile_batch,
            tuple(paths),
            profile.copy(deep=True),
            existing=dict(existing or {}),
            override_sidecars=override_sidecars,
            override_registered=override_registered,
            require_exact_raw_size=require_exact_raw_size,
            generation=epoch,
        )
        self._worker = worker
        self._task_id = worker.task_id
        worker.signals.succeeded.connect(self._on_preflight_ready)
        worker.signals.failed.connect(self._on_preflight_failed)
        worker.signals.finished.connect(self._on_worker_finished)
        analysis_thread_pool().start(worker)
        return epoch

    def approve(self, epoch: int, candidates: tuple[ProfileBatchCandidate, ...]) -> None:
        if self._closing or epoch != self._epoch or self._phase != "ready":
            raise RuntimeError("Batch preflight approval is stale or unavailable")
        if self._candidates is None or candidates != self._candidates:
            raise ValueError("Batch candidate list changed after preflight")
        self._phase = "committing"
        self._index = 0
        self._outcomes = []
        QTimer.singleShot(0, self._commit_next)

    def cancel(self) -> None:
        if self._phase == "committing":
            # Keep already committed sources; explicitly report the interrupted tail.
            self._finish(interrupted=True)
        self._epoch += 1
        if self._worker is not None:
            self._worker.cancel()
        self._worker = None
        self._task_id = None
        self._candidates = None
        self._phase = "idle"

    def shutdown(self) -> None:
        if not self._closing:
            self.cancel()
            self._closing = True

    @Slot(str, object, int, object)
    def _on_preflight_ready(
        self, task_id: str, _document_id: object, epoch: int, value: object
    ) -> None:
        if (self._closing or self._phase != "preflight"
                or epoch != self._epoch or task_id != self._task_id):
            return
        if not isinstance(value, tuple) or not all(
            isinstance(item, ProfileBatchCandidate) for item in value
        ):
            self.preflight_failed.emit(epoch, "Invalid preflight result")
            self._phase = "idle"
            return
        self._candidates = value
        self._phase = "ready"
        self.preflight_ready.emit(epoch, value)

    @Slot(str, object, int, object)
    def _on_preflight_failed(
        self, task_id: str, _document_id: object, epoch: int, error: object
    ) -> None:
        if (not self._closing and self._phase == "preflight"
                and epoch == self._epoch and task_id == self._task_id):
            self._phase = "idle"
            self.preflight_failed.emit(epoch, str(getattr(error, "message", error)))

    @Slot(str)
    def _on_worker_finished(self, task_id: str) -> None:
        if task_id == self._task_id:
            self._worker = None
            self._task_id = None

    def _commit_next(self) -> None:
        if self._closing or self._phase != "committing" or self._candidates is None:
            return
        if self._index >= len(self._candidates):
            self._finish(interrupted=False)
            return
        candidate = self._candidates[self._index]
        self._index += 1
        if not candidate.eligible:
            outcome = BatchProfileOutcome(
                candidate.path, "skipped", candidate.reason, candidate.document_id
            )
        elif not candidate_file_is_current(candidate):
            outcome = BatchProfileOutcome(
                candidate.path, "failed", "File changed since preflight", candidate.document_id
            )
        else:
            try:
                document_id = self._commit_one(candidate)
                outcome = BatchProfileOutcome(
                    candidate.path, "applied", "Canonical binding committed", document_id
                )
            except Exception as exc:  # noqa: BLE001 - preserve other sources and report error
                outcome = BatchProfileOutcome(
                    candidate.path, "failed", str(exc), candidate.document_id
                )
        self._outcomes.append(outcome)
        self.commit_progress.emit(self._epoch, outcome)
        if self._phase == "committing":
            QTimer.singleShot(0, self._commit_next)

    def _finish(self, *, interrupted: bool) -> None:
        candidates = self._candidates or ()
        for candidate in candidates[self._index:]:
            self._outcomes.append(
                BatchProfileOutcome(
                    candidate.path, "interrupted", "Not applied", candidate.document_id
                )
            )
        self._phase = "finished"
        self.commit_finished.emit(
            ProfileBatchResult(self._epoch, tuple(self._outcomes), interrupted)
        )


class CanonicalBatchProfileAdapter:
    """Typed narrow owner seam. Orchestrator wires this without method replacement."""

    def __init__(self, window: Any) -> None:
        self._window_ref = weakref.ref(window)

    @property
    def window(self) -> Any:
        window = self._window_ref()
        if window is None or bool(getattr(window, "_closing", False)):
            raise RuntimeError("MainWindow is closing")
        return window

    def existing(self, paths: tuple[Path, ...]) -> dict[Path, ExistingProfileBinding]:
        window = self.window
        bindings: dict[Path, ExistingProfileBinding] = {}
        for supplied in paths:
            path = Path(supplied).absolute()
            document_id = window._document_id_by_path.get(window._path_key(path))
            if document_id is None:
                continue
            document = window.documents[document_id]
            profile = window._raw_profiles.get(document_id) or document.raw_profile
            bindings[path] = ExistingProfileBinding(
                document_id, document.generation,
                profile if hasattr(profile, "dict") else None,
            )
        return bindings

    def commit_one(self, candidate: ProfileBatchCandidate) -> str:
        window = self.window
        if not candidate_file_is_current(candidate):
            raise RuntimeError("File changed before canonical registration")
        # Sidecar precedence may have changed during the approval dialog.
        if raw_profile_sidecar_for_path(candidate.path) != candidate.sidecar:
            raise RuntimeError("Sidecar changed since preflight; repeat approval")
        current_id = window._document_id_by_path.get(window._path_key(candidate.path))
        if current_id != candidate.document_id:
            raise RuntimeError("Source registration changed since preflight")
        if current_id is not None:
            document = window.documents.get(current_id)
            if document is None or document.generation != candidate.generation:
                raise RuntimeError("Source generation changed since preflight")
            window._mark_document_for_reload(current_id, candidate.profile)
            window._raw_profiles[current_id] = candidate.profile.copy(deep=True)
            window._raw_profile_prompt_suppressed.discard(current_id)
            page_ids = {
                item.document_id for item in window.current_comparison_documents()
            }
            if current_id in page_ids:
                window._refresh_reopened_selected_documents([current_id])
            return cast(str, current_id)
        registered = window._register_inputs(
            (ImageInput(candidate.path, None),), resolve_raw_profiles=False
        )
        if len(registered) != 1:
            raise RuntimeError("Canonical source registration did not return one document")
        document_id = registered[0]
        window._raw_profiles[document_id] = candidate.profile.copy(deep=True)
        document = window.documents[document_id]
        document.raw_profile = candidate.profile.copy(deep=True)
        document.channel_layout = candidate.profile.channel_layout
        document.bit_depth = candidate.profile.bit_depth
        return cast(str, document_id)


class InputProfileBatchDialog(QDialog):
    """Explicit profile choice, preflight, approval, outcomes and async preview."""

    def __init__(
        self,
        window: QWidget,
        paths: tuple[Path, ...],
        *,
        require_exact_raw_size: bool = False,
    ) -> None:
        super().__init__(window)
        self.setWindowTitle("Batch RAW/YUV profile application")
        self.resize(820, 560)
        self._paths = tuple(Path(path).absolute() for path in paths)
        self._adapter = CanonicalBatchProfileAdapter(window)
        self._batch = BatchProfileController(self._adapter.commit_one, self)
        self._preview = NativeInputPreviewController(self)
        self._require_exact_raw_size = require_exact_raw_size
        self._candidates: tuple[ProfileBatchCandidate, ...] = ()
        self._preflight_epoch: int | None = None
        self._profiles: list[InputProfile] = []
        self._library = InputProfileLibrary()
        self._setup_ui()
        self._batch.preflight_ready.connect(self._preflight_ready)
        self._batch.preflight_failed.connect(self._preflight_failed)
        self._batch.commit_progress.connect(self._commit_progress)
        self._batch.commit_finished.connect(self._commit_finished)
        self._preview.preview_ready.connect(self._preview_ready)
        self._preview.preview_failed.connect(self._preview_failed)

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.addWidget(QLabel(
            "Choose a saved native interpretation. File size alone cannot verify layout, "
            "packing, stride, endianness or CFA phase."
        ))
        self.profile_box = QComboBox(self)
        self.profile_box.addItem("Select a Recent or Favorite profile…")
        for kind in ("raw", "yuv"):
            for entry in (*self._library.favorites(kind), *self._library.recent(kind)):
                self._profiles.append(entry.profile)
                self.profile_box.addItem(
                    f"{kind.upper()} · {entry.label} ({entry.origin})"
                )
        self.profile_box.currentIndexChanged.connect(  # type: ignore[attr-defined]
            self._profile_changed
        )
        root.addWidget(self.profile_box)
        self.override_sidecars = QCheckBox(
            "Explicitly override JSON / imgprops sidecar interpretation", self
        )
        self.override_registered = QCheckBox(
            "Explicitly re-interpret already registered sources", self
        )
        root.addWidget(self.override_sidecars)
        root.addWidget(self.override_registered)
        self.override_sidecars.toggled.connect(self._profile_changed)  # type: ignore[attr-defined]
        self.override_registered.toggled.connect(  # type: ignore[attr-defined]
            self._profile_changed
        )
        self.table = QTableWidget(0, 6, self)
        self.table.setHorizontalHeaderLabels(
            ["Source", "Existing key", "Proposed native profile", "Bytes", "Status", "Reason"]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        root.addWidget(self.table)
        self.table.itemSelectionChanged.connect(  # type: ignore[attr-defined]
            self._preview_selection_changed
        )
        self.status = QLabel(f"{len(self._paths)} source(s) selected; no changes made", self)
        root.addWidget(self.status)
        self.preview_label = QLabel("Preview not requested", self)
        self.preview_label.setMinimumHeight(145)
        root.addWidget(self.preview_label)
        actions = QHBoxLayout()
        self.preflight_button = QPushButton("Preflight", self)
        self.apply_button = QPushButton("Approve and apply", self)
        self.apply_button.setEnabled(False)
        self.preview_button = QPushButton("Preview selected", self)
        self.preview_button.setEnabled(False)
        self.stop_button = QPushButton("Cancel pending", self)
        self.close_button = QPushButton("Close", self)
        for button in (
            self.preflight_button, self.apply_button, self.preview_button,
            self.stop_button, self.close_button,
        ):
            actions.addWidget(button)
        root.addLayout(actions)
        self.preflight_button.clicked.connect(self._start_preflight)  # type: ignore[attr-defined]
        self.apply_button.clicked.connect(self._approve)  # type: ignore[attr-defined]
        self.preview_button.clicked.connect(self._request_preview)  # type: ignore[attr-defined]
        self.stop_button.clicked.connect(self._cancel)  # type: ignore[attr-defined]
        self.close_button.clicked.connect(self.reject)  # type: ignore[attr-defined]

    @staticmethod
    def _profile_summary(profile: InputProfile) -> str:
        if isinstance(profile, RawProfile):
            return (
                f"{profile.name} · {profile.width}×{profile.height} · "
                f"{profile.storage_format} {profile.bit_depth}-bit, "
                f"stride {profile.stride_bytes}"
            )
        return (
            f"{profile.name} · {profile.width}×{profile.height} · "
            f"{profile.channel_layout} 8-bit Y+UV"
        )

    def _preview_selection_changed(self) -> None:
        self._preview.cancel()
        self.preview_label.setText("Preview invalidated by source selection")

    def _profile(self) -> InputProfile | None:
        index = self.profile_box.currentIndex() - 1
        return self._profiles[index] if 0 <= index < len(self._profiles) else None

    def _profile_changed(self, _index: int) -> None:
        self._batch.cancel()
        self._preview.cancel()
        self._preflight_epoch = None
        self._candidates = ()
        self.apply_button.setEnabled(False)
        self.preview_button.setEnabled(False)
        self.preview_label.setText("Preview invalidated by profile change")
        self.status.setText("Profile changed; run Preflight again")

    def _start_preflight(self) -> None:
        profile = self._profile()
        if profile is None:
            self.status.setText("Select a saved RAW or YUV profile first")
            return
        self._preview.cancel()
        self.apply_button.setEnabled(False)
        self.preview_button.setEnabled(False)
        self.status.setText("Checking source sizes and registered interpretations…")
        epoch = self._batch.preflight(
            self._paths, profile,
            existing=self._adapter.existing(self._paths),
            override_sidecars=self.override_sidecars.isChecked(),
            override_registered=self.override_registered.isChecked(),
            require_exact_raw_size=self._require_exact_raw_size,
        )
        self._preflight_epoch = epoch

    def _preflight_ready(self, epoch: int, value: object) -> None:
        if epoch != self._preflight_epoch or not isinstance(value, tuple):
            return
        self._candidates = value
        self.table.setRowCount(len(value))
        eligible = 0
        for row, item in enumerate(value):
            if not isinstance(item, ProfileBatchCandidate):
                continue
            eligible += int(item.eligible)
            previous = (
                item.previous_interpretation[:12]
                if item.previous_interpretation is not None
                else "None"
            )
            actual_size = item.revision.size if item.revision is not None else "?"
            for column, label in enumerate((
                str(item.path),
                previous,
                self._profile_summary(item.profile),
                f"{actual_size} / {item.required_size}",
                item.status,
                item.reason,
            )):
                self.table.setItem(row, column, QTableWidgetItem(label))
        self.apply_button.setEnabled(eligible > 0)
        self.preview_button.setEnabled(eligible > 0)
        self.status.setText(
            f"Preflight: {eligible} eligible / {len(value)} total. "
            "Approval is required before changes."
        )

    def _preflight_failed(self, epoch: int, error: str) -> None:
        if epoch == self._preflight_epoch:
            self.status.setText(f"Preflight failed: {error}")

    def _approve(self) -> None:
        if self._preflight_epoch is None or not self._candidates:
            return
        eligible = sum(candidate.eligible for candidate in self._candidates)
        choice = QMessageBox.question(
            self, "Confirm batch profile override",
            f"Apply the selected profile to {eligible} source(s)? "
            "Approved registered sources will be reloaded. "
            "The operation is not atomic after it starts.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        self._preview.cancel()
        self.apply_button.setEnabled(False)
        self.preflight_button.setEnabled(False)
        self.profile_box.setEnabled(False)
        self.override_sidecars.setEnabled(False)
        self.override_registered.setEnabled(False)
        self._batch.approve(self._preflight_epoch, self._candidates)

    def _commit_progress(self, epoch: int, value: object) -> None:
        if epoch != self._preflight_epoch or not isinstance(value, BatchProfileOutcome):
            return
        for row, candidate in enumerate(self._candidates):
            if candidate.path == value.path:
                self.table.setItem(row, 4, QTableWidgetItem(value.status))
                self.table.setItem(row, 5, QTableWidgetItem(value.reason))
                break

    def _commit_finished(self, result: object) -> None:
        if not isinstance(result, ProfileBatchResult):
            return
        self.preflight_button.setEnabled(True)
        self.profile_box.setEnabled(True)
        self.override_sidecars.setEnabled(True)
        self.override_registered.setEnabled(True)
        for outcome in result.outcomes:
            self._commit_progress(result.epoch, outcome)
        failures = sum(item.status == "failed" for item in result.outcomes)
        self.status.setText(
            f"Batch result: {result.applied} applied, {failures} failed, "
            f"{len(result.outcomes) - result.applied - failures} skipped/interrupted"
            + (" · partial commit interrupted" if result.interrupted else "")
        )

    def _request_preview(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._candidates):
            self.preview_label.setText("Select a source row for preview")
            return
        candidate = self._candidates[row]
        if not candidate.eligible:
            self.preview_label.setText("Cannot preview a rejected/unchanged source")
            return
        generation = candidate.generation if candidate.generation is not None else 0
        self._preview.request(candidate.path, candidate.profile, generation=generation)
        self.preview_label.setText(f"Reading native preview: {candidate.path.name}")

    def _preview_ready(self, epoch: int, value: object) -> None:
        if epoch != self._preview.epoch or not isinstance(value, NativeInputPreview):
            return
        try:
            registered = self._adapter.existing((value.source_path,)).get(value.source_path)
        except RuntimeError:
            return
        generation = registered.generation if registered is not None else 0
        if generation != value.source_generation:
            self.preview_label.setText("Preview discarded: source generation changed")
            return
        pixels = value.pixels
        if pixels.ndim == 2:
            fmt = QImage.Format.Format_Grayscale8
        elif pixels.ndim == 3 and pixels.shape[2] == 3:
            fmt = QImage.Format.Format_RGB888
        else:
            self.preview_label.setText("Unsupported preview shape")
            return
        image = QImage(
            pixels.data, value.width, value.height, pixels.strides[0], fmt
        ).copy()
        self.preview_label.setPixmap(QPixmap.fromImage(image))

    def _preview_failed(self, epoch: int, error: str) -> None:
        if epoch == self._preview.epoch:
            self.preview_label.setText(f"Preview unavailable: {error}")

    def _cancel(self) -> None:
        was_committing = self._batch.phase == "committing"
        self._batch.cancel()
        self._preview.cancel()
        self.apply_button.setEnabled(False)
        self.preflight_button.setEnabled(True)
        self.preview_button.setEnabled(False)
        if not was_committing:
            self.status.setText("Pending work cancelled; no batch changes made")

    def reject(self) -> None:
        self._batch.shutdown()
        self._preview.shutdown()
        super().reject()

    def closeEvent(self, event: Any) -> None:
        self._batch.shutdown()
        self._preview.shutdown()
        super().closeEvent(event)
