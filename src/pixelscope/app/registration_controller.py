from __future__ import annotations

import logging
import weakref
from bisect import bisect_right
from collections import deque
from collections.abc import Callable, Sequence
from contextlib import ExitStack, nullcontext, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from PySide6.QtCore import QElapsedTimer, QEvent, QObject, QThreadPool, QTimer, Signal, Slot
from PySide6.QtWidgets import QFileDialog, QHeaderView, QProgressBar

from pixelscope.core import load_latency_trace
from pixelscope.core.cancellation import cancellation_checkpoint
from pixelscope.core.recent_entries import RecentEntryKind
from pixelscope.io.path_discovery import (
    RegistrationDiscovery,
    RegistrationInput,
    discover_registration_inputs,
    natural_sort_key,
)
from pixelscope.ui.lifecycle_hooks import OwnerCallback
from pixelscope.workers.task_worker import TaskError, TaskWorker

LOGGER = logging.getLogger(__name__)
REGISTRATION_CHUNK_SIZE = 16
REGISTRATION_SLICE_BUDGET_MS = 8


@dataclass(frozen=True)
class RegistrationProgress:
    """Observable lifecycle state for deterministic registration tests and UI."""

    phase: str
    completed: int
    total: int | None


@dataclass(frozen=True)
class _FolderRegistrationSummary:
    folder_count: int
    image_count: int
    empty_folder_count: int
    registered_folders: tuple[Path, ...]


DiscoveryFunction = Callable[..., RegistrationDiscovery]
DirectRegistrationCompletion = Callable[[list[str]], None]


@dataclass(frozen=True)
class _RegistrationRequest:
    paths: tuple[Path, ...]
    direct_completion: OwnerCallback | None = None


class RegistrationController(QObject):
    """Single-flight folder/direct registration orchestration for production UI paths.

    Filesystem discovery is the only worker-thread phase. Catalog and Qt tree mutation
    remain on this QObject's GUI thread and are split into bounded event-loop slices.
    Worker-computed canonical identities and sort keys are reused by the production
    async path so GUI registration does not repeat filesystem canonicalization.
    """

    progress_changed = Signal(str, int, object)

    def __init__(
        self,
        window: Any,
        *,
        discovery_function: DiscoveryFunction = discover_registration_inputs,
        chunk_size: int = REGISTRATION_CHUNK_SIZE,
        slice_budget_ms: int = REGISTRATION_SLICE_BUDGET_MS,
    ) -> None:
        super().__init__(window)
        if chunk_size < 1:
            raise ValueError("registration chunk size must be positive")
        if slice_budget_ms < 1:
            raise ValueError("registration slice budget must be positive")
        self._window_ref = weakref.ref(window)
        self.chunk_size = chunk_size
        self.slice_budget_ms = slice_budget_ms
        self._discovery_function = discovery_function
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._queue: deque[_RegistrationRequest] = deque()
        self._worker: TaskWorker | None = None
        self._discovery_task_id: str | None = None
        self._generation = 0
        self._active_generation: int | None = None
        self._active_discovery: RegistrationDiscovery | None = None
        self._registration_index = 0
        self._folder_registered_ids: set[str] = set()
        self._direct_document_ids: list[str] = []
        self._direct_document_id_set: set[str] = set()
        self._direct_paths: list[Path] = []
        self._deferred_recent: deque[tuple[tuple[Path, ...], tuple[Path, ...]]] = deque()
        self._deferred_recent_targets: set[str] = set()
        self._recent_flush_timer = QTimer(self)
        self._recent_flush_timer.setSingleShot(True)
        self._recent_flush_timer.timeout.connect(self._flush_deferred_recent)  # type: ignore[attr-defined]
        self._recent_fallback_timer = QTimer(self)
        self._recent_fallback_timer.setSingleShot(True)
        self._recent_fallback_timer.setInterval(10000)
        self._recent_fallback_timer.timeout.connect(self._flush_deferred_recent)  # type: ignore[attr-defined]
        self._closing = False
        self._stale_result_count = 0
        self._folder_sort_keys: dict[str, list[tuple[object, ...]]] = {}
        self._folder_document_ids: dict[str, set[str]] = {}
        self._current_record: RegistrationInput | None = None
        self._active_direct_completion: OwnerCallback | None = None
        self._type_column_resize_mode: QHeaderView.ResizeMode | None = None
        self._original_path_key = OwnerCallback(window._path_key)
        self._original_add_document_to_folder = OwnerCallback(window._add_document_to_folder)
        self._original_remove_document_from_folder = OwnerCallback(
            window._remove_document_from_folder
        )
        self._initialize_folder_caches()
        for viewer in (window.viewer, *window.multi_compare_view.viewers):
            viewer.first_frame_painted.connect(self._on_first_frame_painted)

        progress_parent = window.document_list.parentWidget() or window
        self._progress = QProgressBar(progress_parent)
        self._progress.setObjectName("registrationProgress")
        self._progress.setTextVisible(True)
        self._progress.setMinimumWidth(0)
        self._progress.hide()
        progress_layout = progress_parent.layout() if progress_parent is not window else None
        if progress_layout is not None:
            progress_layout.addWidget(self._progress)
        else:
            window.statusBar().addWidget(self._progress)
        self._progress_state = RegistrationProgress("idle", 0, None)

    @property
    def window(self) -> Any:
        window = self._window_ref()
        if window is None:
            raise RuntimeError("Registration window was destroyed")
        return window

    @property
    def progress(self) -> RegistrationProgress:
        return self._progress_state

    @property
    def is_idle(self) -> bool:
        return self._active_generation is None and not self._queue and self._worker is None

    @property
    def stale_result_count(self) -> int:
        return self._stale_result_count

    @property
    def is_shutdown_drained(self) -> bool:
        """Return whether shutdown has no physically running discovery worker."""

        return self._closing and self._pool.activeThreadCount() == 0

    @property
    def pool(self) -> QThreadPool:
        return self._pool

    @property
    def current_record(self) -> RegistrationInput | None:
        return self._current_record

    def install(self) -> None:
        """Redirect production Open Folder/drop ownership without changing MainWindow ABI."""

        self.window._path_key = self._path_key
        self.window._add_document_to_folder = self._add_document_to_folder
        self.window._remove_document_from_folder = self._remove_document_from_folder
        self.window._handle_dropped_paths = self.handle_dropped_paths
        self.window.open_folders = self.open_folders

        action = self.window.action_map.get("Open Folder...")
        if action is not None:
            with suppress(RuntimeError, TypeError):
                action.triggered.disconnect()
            action.triggered.connect(self.open_folders)

        with suppress(RuntimeError, TypeError):
            self.window.empty_workspace.open_folders_requested.disconnect()
        self.window.empty_workspace.open_folders_requested.connect(self.open_folders)

        with suppress(RuntimeError, TypeError):
            self.window.document_list.paths_dropped.disconnect()
        self.window.document_list.paths_dropped.connect(self.handle_dropped_paths)

    def open_folders(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self.window,
            "Open image folder",
            self.window._open_dialog_directory(),
        )
        if not path:
            return
        folder = Path(path)
        self.window._remember_directory(folder)
        self.enqueue((folder,))

    def handle_dropped_paths(self, paths: object) -> None:
        """Share one asynchronous discovery contract for folder and mixed drops."""

        if not isinstance(paths, list) or not all(isinstance(path, Path) for path in paths):
            return
        self.enqueue(paths)

    def enqueue(
        self,
        paths: Sequence[Path],
        *,
        direct_completion: DirectRegistrationCompletion | None = None,
    ) -> None:
        """Queue one logical input request without performing filesystem work on the GUI thread."""

        if self._closing:
            return
        normalized = tuple(Path(path) for path in paths)
        if not normalized:
            return
        completion_hook = (
            OwnerCallback(direct_completion) if direct_completion is not None else None
        )
        if len(normalized) == 1:
            load_latency_trace.begin("explicit_path_enqueued")
        self._queue.append(_RegistrationRequest(normalized, completion_hook))
        self._start_next_request()

    def cancel_active(self) -> None:
        """Cancel current discovery/chunk ownership and reject any later stale callbacks."""

        if self._active_generation is None:
            return
        self._generation += 1
        worker = self._worker
        if worker is not None:
            worker.cancel()
        self._clear_active_state()
        self._set_progress("idle", 0, None)
        if not self._closing:
            self._start_next_request()

    def shutdown(self) -> bool:
        """Revoke registration authority without blocking the GUI thread.

        Cancellation is advisory.  The close filter owns the continuation that keeps
        the window alive until this controller's dedicated pool is physically idle.
        """

        if not self._closing:
            self._closing = True
            self._recent_flush_timer.stop()
            self._recent_fallback_timer.stop()
            # Queue staged history in QSettings without blocking the close
            # path on a synchronous disk/registry flush.
            if self._deferred_recent:
                self._flush_recent_to_settings()
            self._deferred_recent.clear()
            self._deferred_recent_targets.clear()
            self._queue.clear()
            self._generation += 1
            if self._worker is not None:
                self._worker.cancel()
            self._clear_active_state()
            self._set_progress("idle", 0, None)
        return self.is_shutdown_drained

    def _initialize_folder_caches(self) -> None:
        for folder_key, document_ids in self.window._folder_documents.items():
            self._folder_sort_keys[folder_key] = [
                natural_sort_key(self.window.documents[document_id].source_path or Path(""))
                for document_id in document_ids
                if document_id in self.window.documents
            ]
            self._folder_document_ids[folder_key] = set(document_ids)

    def _path_key(self, path: Path) -> str:
        record = self._current_record
        if (
            record is not None
            and record.image_input.path == path
            and record.canonical_path_key is not None
        ):
            return record.canonical_path_key
        return cast(str, self._original_path_key(path))

    def _suspend_type_column_auto_resize(self) -> None:
        if self._type_column_resize_mode is not None:
            return
        header = self.window.document_list.header()
        mode = header.sectionResizeMode(1)
        self._type_column_resize_mode = mode
        if mode == QHeaderView.ResizeMode.ResizeToContents:
            width = header.sectionSize(1)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
            header.resizeSection(1, max(width, 48))

    def _restore_type_column_auto_resize(self) -> None:
        mode = self._type_column_resize_mode
        if mode is None:
            return
        self._type_column_resize_mode = None
        self.window.document_list.header().setSectionResizeMode(1, mode)

    def _start_next_request(self) -> None:
        if self._closing or self._active_generation is not None or not self._queue:
            return
        request = self._queue.popleft()
        paths = request.paths
        self._active_direct_completion = request.direct_completion
        self._generation += 1
        generation = self._generation
        self._active_generation = generation
        self._active_discovery = None
        self._registration_index = 0
        self._folder_registered_ids.clear()
        self._direct_document_ids.clear()
        self._direct_document_id_set.clear()
        self._direct_paths.clear()
        self._set_progress("scanning", 0, None)
        worker = TaskWorker(self._discover, paths, generation=generation)
        self._worker = worker
        self._discovery_task_id = worker.task_id
        worker.signals.succeeded.connect(self._discovery_succeeded)
        worker.signals.failed.connect(self._discovery_failed)
        worker.signals.cancelled.connect(self._discovery_cancelled)
        worker.signals.finished.connect(self._discovery_finished)
        self._pool.start(worker)

    def _discover(self, paths: Sequence[Path]) -> RegistrationDiscovery:
        return self._discovery_function(paths, checkpoint=cancellation_checkpoint)

    def _current_discovery_signal(self, task_id: str, generation: int) -> bool:
        return (
            not self._closing
            and self._active_generation == generation
            and self._discovery_task_id == task_id
        )

    @Slot(str, object, int, object)
    def _discovery_succeeded(
        self,
        task_id: str,
        _document_id: object,
        generation: int,
        result: object,
    ) -> None:
        if not self._current_discovery_signal(task_id, generation):
            self._stale_result_count += 1
            return
        if not isinstance(result, RegistrationDiscovery):
            self._finish_with_error("Registration discovery returned an invalid result")
            return
        self._discovery_task_id = None
        self._active_discovery = result
        total = len(result.items)
        if total == 1 and not result.items[0].from_folder:
            load_latency_trace.mark("discovery_worker_completed")
        self._suspend_type_column_auto_resize()
        self._set_progress("registering", 0, total)
        if total == 0:
            QTimer.singleShot(0, lambda token=generation: self._finish_registration(token))
            return
        if total == 1 and not result.items[0].from_folder:
            # Files row/catalog mutation is lightweight and belongs on the GUI
            # thread. Avoid an extra event-loop turn for one explicit image;
            # its actual decode remains delegated to ImageLoadWorker.
            self._register_chunk(generation)
            return
        QTimer.singleShot(0, lambda token=generation: self._register_chunk(token))

    @Slot(str, object, int, object)
    def _discovery_failed(
        self,
        task_id: str,
        _document_id: object,
        generation: int,
        error: object,
    ) -> None:
        if not self._current_discovery_signal(task_id, generation):
            self._stale_result_count += 1
            return
        message = error.message if isinstance(error, TaskError) else str(error)
        LOGGER.error("Folder registration discovery failed: %s", message)
        self._finish_with_error(f"Folder scan failed: {message}")

    @Slot(str, object, int)
    def _discovery_cancelled(
        self,
        task_id: str,
        _document_id: object,
        generation: int,
    ) -> None:
        if self._closing:
            return
        if not self._current_discovery_signal(task_id, generation):
            return
        self._clear_active_state()
        self._set_progress("idle", 0, None)
        self._start_next_request()

    @Slot(str)
    def _discovery_finished(self, task_id: str) -> None:
        if self._worker is not None and self._worker.task_id == task_id:
            self._worker = None

    def _register_chunk(self, generation: int) -> None:
        discovery = self._active_discovery
        if self._closing or generation != self._active_generation or discovery is None:
            return
        register_trace = load_latency_trace.PhaseTimer("register")
        total = len(discovery.items)
        start = self._registration_index
        hard_stop = min(start + self.chunk_size, total)
        completed = start
        timer = QElapsedTimer()
        timer.start()

        with ExitStack() as stack:
            stack.enter_context(self.window.document_list.bulk_update())
            tag_controller = getattr(self.window, "folder_display_tag_controller", None)
            tag_bulk = getattr(tag_controller, "bulk_registration", None)
            if callable(tag_bulk):
                stack.enter_context(tag_bulk())
            while completed < hard_stop:
                self._register_record(discovery.items[completed])
                completed += 1
                if completed < hard_stop and timer.elapsed() >= self.slice_budget_ms:
                    break

        self._registration_index = completed
        register_trace.checkpoint("document_record_and_tree_row")
        if start == 0 or completed == total:
            self.window._update_empty_workspace_state()
        self._set_progress("registering", completed, total)
        register_trace.checkpoint("empty_workspace_and_progress")
        if completed < total:
            QTimer.singleShot(0, lambda token=generation: self._register_chunk(token))
            return
        if total == 1 and not discovery.items[0].from_folder:
            # Start foreground selection/loading in the same GUI turn as row
            # registration; folder and multi-file batches stay sliced.
            self._finish_registration(generation)
            return
        QTimer.singleShot(0, lambda token=generation: self._finish_registration(token))

    def _register_record(self, record: RegistrationInput) -> None:
        self._current_record = record
        record_trace = load_latency_trace.PhaseTimer("register.record")
        if (
            record.canonical_folder_path is not None
            and record.canonical_folder_key is not None
            and record.sort_key is not None
        ):
            tree_context = self.window.document_list.registration_metadata(
                source_path=record.image_input.path,
                folder_path=record.canonical_folder_path,
                folder_key=record.canonical_folder_key,
                sort_key=record.sort_key,
            )
        else:
            tree_context = nullcontext()
        try:
            with tree_context:
                document_id = self.window._register_input(
                    record.image_input,
                    resolve_raw_profile=record.resolve_raw_profile,
                )
        finally:
            self._current_record = None
        record_trace.checkpoint("register_input_and_tree_mutation")
        if document_id is None:
            return
        if record.from_folder:
            self._folder_registered_ids.add(document_id)
        elif self._active_discovery is not None and len(self._active_discovery.items) == 1:
            load_latency_trace.target(document_id)
        if record.select_on_complete and document_id not in self._direct_document_id_set:
            self._direct_document_id_set.add(document_id)
            self._direct_document_ids.append(document_id)
            document = self.window.documents.get(document_id)
            if document is not None and document.source_path is not None:
                self._direct_paths.append(document.source_path)
        record_trace.checkpoint("record_identity_and_selection_metadata")

    def _finish_registration(self, generation: int) -> None:
        discovery = self._active_discovery
        if self._closing or generation != self._active_generation or discovery is None:
            return
        direct_ids = list(self._direct_document_ids)
        direct_paths = tuple(self._direct_paths)
        folder_ids = set(self._folder_registered_ids)
        summary = _FolderRegistrationSummary(
            folder_count=discovery.folder_count,
            image_count=len(folder_ids),
            empty_folder_count=discovery.empty_folder_count,
            registered_folders=discovery.registered_folders,
        )
        current_ids = [document.document_id for document in self.window.selected_documents]
        current_set = set(current_ids)
        additions = [document_id for document_id in direct_ids if document_id not in current_set]
        completion = self._active_direct_completion
        reloads: list[str] = []
        if direct_ids:
            load_latency_trace.mark("selection_start", document_id=direct_ids[0])
        if completion is not None and direct_ids:
            # Registration may outlive the presentation owner during teardown.
            # The request retains only a weak owner edge and a vanished owner
            # simply makes the presentation continuation stale.
            with suppress(RuntimeError):
                completion(direct_ids)
        elif direct_ids:
            if current_ids:
                if additions:
                    self.window._select_document_ids(
                        [*current_ids, *additions],
                        preserve_view=True,
                        reveal_document_id=additions[-1],
                    )
                reloads = self.window._refresh_reopened_selected_documents(
                    [document_id for document_id in direct_ids if document_id in current_set]
                )
            else:
                self.window._select_document_ids(direct_ids)
        else:
            self.window._update_empty_workspace_state()

        if direct_ids:
            load_latency_trace.mark("selection_returned", document_id=direct_ids[0])

        # QSettings.sync() can block the GUI even if decoding is running on a
        # worker. Only direct-file registration defers Recent history until the
        # image viewport has painted; folder-only registration keeps its
        # established synchronous persistence semantics.
        if direct_ids:
            load_latency_trace.mark("recent_entries_stage_begin", document_id=direct_ids[0])
            self._stage_recent_entries(summary.registered_folders, direct_paths)
            load_latency_trace.mark("recent_entries_stage_returned", document_id=direct_ids[0])
            self._deferred_recent.append((summary.registered_folders, direct_paths))
            self._deferred_recent_targets.update(direct_ids)
            if not self._recent_fallback_timer.isActive():
                self._recent_fallback_timer.start()
            load_latency_trace.mark("recent_entries_staged", document_id=direct_ids[0])
        else:
            self._record_recent_entries(summary.registered_folders, direct_paths)

        messages: list[str] = []
        if completion is None and direct_ids:
            if current_ids:
                if additions:
                    messages.append(f"Added {len(additions)} image(s)")
                elif reloads:
                    messages.append(f"Reloading {len(reloads)} image(s)")
                else:
                    messages.append("No new images added")
            else:
                messages.append(f"Opened {len(direct_ids)} image(s)")
        if summary.folder_count:
            messages.append(self.window._folder_registration_message(summary))
        if messages:
            self.window.statusBar().showMessage(" · ".join(messages), 5000)

        self._clear_active_state()
        self._set_progress("idle", 0, None)
        self._start_next_request()

    def _on_first_frame_painted(self, document_id: str) -> None:
        if self._closing or document_id not in self._deferred_recent_targets:
            return
        # Give Qt a paint/event-loop turn before expensive history I/O.
        # A pending one-shot timer also coalesces rapid sequential drops.
        if not self._recent_flush_timer.isActive():
            self._recent_flush_timer.start(100)

    def _flush_deferred_recent(self) -> None:
        if self._closing or not self._deferred_recent:
            return
        self._recent_flush_timer.stop()
        self._recent_fallback_timer.stop()
        self._deferred_recent.clear()
        self._deferred_recent_targets.clear()
        self._flush_recent_to_settings()
        load_latency_trace.mark("recent_entries_submitted_to_qsettings_after_paint")

    def _flush_recent_to_settings(self) -> None:
        controller = getattr(self.window, "recent_entries_controller", None)
        repository = getattr(controller, "repository", None)
        flush = getattr(repository, "flush_staged", None)
        if callable(flush):
            try:
                flush(sync=False)
            except Exception:  # noqa: BLE001 - optional history must not break runtime
                LOGGER.warning("Unable to queue staged Recent history", exc_info=True)

    def _stage_recent_entries(
        self,
        folders: Sequence[Path],
        direct_paths: Sequence[Path],
    ) -> None:
        controller = getattr(self.window, "recent_entries_controller", None)
        observe = getattr(controller, "_observe_history", None)
        if not callable(observe):
            return
        if folders:
            observe(RecentEntryKind.FOLDER, folders, canonical=True)
        if direct_paths:
            observe(RecentEntryKind.IMAGE, direct_paths, canonical=True)

    def _record_recent_entries(
        self,
        folders: Sequence[Path],
        direct_paths: Sequence[Path],
    ) -> None:
        controller = getattr(self.window, "recent_entries_controller", None)
        observe = getattr(controller, "_observe_history", None)
        if not callable(observe):
            return
        if folders:
            observe(RecentEntryKind.FOLDER, folders)
        if direct_paths:
            observe(RecentEntryKind.IMAGE, direct_paths)

    def _finish_with_error(self, message: str) -> None:
        if not self._closing:
            self.window.statusBar().showMessage(message, 5000)
        self._clear_active_state()
        self._set_progress("idle", 0, None)
        if not self._closing:
            self._start_next_request()

    def _clear_active_state(self) -> None:
        self._restore_type_column_auto_resize()
        self._active_generation = None
        self._active_discovery = None
        self._discovery_task_id = None
        self._registration_index = 0
        self._folder_registered_ids.clear()
        self._direct_document_ids.clear()
        self._direct_document_id_set.clear()
        self._direct_paths.clear()
        self._current_record = None
        self._active_direct_completion = None

    def _set_progress(self, phase: str, completed: int, total: int | None) -> None:
        self._progress_state = RegistrationProgress(phase, completed, total)
        if phase == "scanning":
            self._progress.setRange(0, 0)
            self._progress.setFormat("Scanning…")
            self._progress.show()
        elif phase == "registering":
            maximum = max(1, total or 0)
            self._progress.setRange(0, maximum)
            self._progress.setValue(min(completed, maximum))
            self._progress.setFormat(
                f"Registering {completed} / {total}" if total is not None else "Registering…"
            )
            self._progress.show()
        else:
            self._progress.hide()
        self.progress_changed.emit(phase, completed, total)

    def _record_metadata_for_path(
        self,
        path: Path,
    ) -> tuple[str, Path, tuple[object, ...]] | None:
        record = self._current_record
        if (
            record is None
            or record.image_input.path != path
            or record.canonical_folder_key is None
            or record.canonical_folder_path is None
            or record.sort_key is None
        ):
            return None
        return record.canonical_folder_key, record.canonical_folder_path, record.sort_key

    def _add_document_to_folder(self, document_id: str, path: Path) -> None:
        """Maintain natural folder order with O(1) membership and cached sort keys."""

        metadata = self._record_metadata_for_path(path)
        if metadata is None:
            folder_key = self.window._folder_key(path)
            folder_path = path.resolve().parent
            new_key = natural_sort_key(self.window.documents[document_id].source_path or Path(""))
        else:
            folder_key, folder_path, new_key = metadata

        folder_documents = self.window._folder_documents.setdefault(folder_key, [])
        folder_keys = self._folder_sort_keys.get(folder_key)
        if folder_keys is None:
            folder_keys = [
                natural_sort_key(self.window.documents[candidate_id].source_path or Path(""))
                for candidate_id in folder_documents
                if candidate_id in self.window.documents
            ]
            self._folder_sort_keys[folder_key] = folder_keys

        folder_ids = self._folder_document_ids.get(folder_key)
        if folder_ids is None:
            folder_ids = set(folder_documents)
            self._folder_document_ids[folder_key] = folder_ids

        current_index = self.window._folder_indices.get(folder_key)
        inserted_at: int | None = None
        if document_id not in folder_ids:
            inserted_at = bisect_right(folder_keys, new_key)
            folder_keys.insert(inserted_at, new_key)
            folder_documents.insert(inserted_at, document_id)
            folder_ids.add(document_id)
        self.window._folder_paths[folder_key] = folder_path
        self.window._document_folder_keys[document_id] = folder_key
        if current_index is None:
            self.window._folder_indices.setdefault(folder_key, 0)
        elif inserted_at is not None and inserted_at <= current_index:
            self.window._folder_indices[folder_key] = current_index + 1

    def _remove_document_from_folder(self, document_id: str, path: Path) -> None:
        """Keep binary-insertion caches consistent with canonical removal semantics."""

        folder_key = self.window._document_folder_keys.pop(document_id, None)
        if folder_key is None:
            folder_key = self.window._folder_key(path)
        folder_documents = self.window._folder_documents.get(folder_key)
        if folder_documents is None:
            return
        folder_ids = self._folder_document_ids.get(folder_key)
        current_index = self.window._folder_indices.get(folder_key, 0)
        if folder_ids is None or document_id in folder_ids:
            try:
                removed_index = folder_documents.index(document_id)
            except ValueError:
                removed_index = -1
            if removed_index >= 0:
                folder_documents.pop(removed_index)
                if folder_ids is not None:
                    folder_ids.discard(document_id)
                folder_keys = self._folder_sort_keys.get(folder_key)
                if folder_keys is not None and removed_index < len(folder_keys):
                    folder_keys.pop(removed_index)
                if removed_index < current_index:
                    current_index -= 1
        if folder_documents:
            self.window._folder_indices[folder_key] = min(current_index, len(folder_documents) - 1)
        else:
            self.window._folder_documents.pop(folder_key, None)
            self.window._folder_paths.pop(folder_key, None)
            self.window._folder_indices.pop(folder_key, None)
            self._folder_sort_keys.pop(folder_key, None)
            self._folder_document_ids.pop(folder_key, None)


class _RegistrationCloseFilter(QObject):
    def __init__(self, controller: RegistrationController, parent: QObject) -> None:
        super().__init__(parent)
        self._controller_ref = weakref.ref(controller)
        self._close_state = "open"
        self._drain_timer = QTimer(self)
        self._drain_timer.setSingleShot(True)
        self._drain_timer.timeout.connect(self._continue_close)  # type: ignore[attr-defined]

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() is not QEvent.Type.Close:
            return super().eventFilter(watched, event)

        if self._close_state == "safe":
            self._close_state = "closed"
            return super().eventFilter(watched, event)
        if self._close_state == "closed":
            return super().eventFilter(watched, event)

        controller = self._controller_ref()
        if controller is None:
            return super().eventFilter(watched, event)
        if self._close_state == "open" and controller.shutdown():
            self._close_state = "closed"
            return super().eventFilter(watched, event)

        self._close_state = "draining"
        event.ignore()
        if not self._drain_timer.isActive():
            self._drain_timer.start(0)
        return True

    def _continue_close(self) -> None:
        if self._close_state != "draining":
            return
        controller = self._controller_ref()
        if controller is None:
            return
        if not controller.is_shutdown_drained:
            self._drain_timer.start(0)
            return
        window = self.parent()
        if window is None:
            return
        self._close_state = "safe"
        close = getattr(window, "close", None)
        if callable(close):
            close()


def install_large_folder_registration(
    window: Any,
    *,
    discovery_function: DiscoveryFunction = discover_registration_inputs,
    chunk_size: int = REGISTRATION_CHUNK_SIZE,
    slice_budget_ms: int = REGISTRATION_SLICE_BUDGET_MS,
) -> RegistrationController:
    """Install WP-A production registration ownership once for a MainWindow instance."""

    existing = getattr(window, "large_folder_registration_controller", None)
    if isinstance(existing, RegistrationController):
        return existing
    controller = RegistrationController(
        window,
        discovery_function=discovery_function,
        chunk_size=chunk_size,
        slice_budget_ms=slice_budget_ms,
    )
    controller.install()
    close_filter = _RegistrationCloseFilter(controller, window)
    window.installEventFilter(close_filter)
    window.large_folder_registration_controller = controller
    window._large_folder_registration_close_filter = close_filter
    return controller
