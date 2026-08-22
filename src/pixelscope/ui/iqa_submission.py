"""P5-C Setup/Jobs shell and asynchronous Remote IQA lifecycle integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QEvent, QObject, QThreadPool, QTimer, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pixelscope.remote.iqa_client import HttpIqaJobClient, IqaJobClient
from pixelscope.remote.iqa_settings import RemoteIqaSettings
from pixelscope.remote.iqa_storage import StorageResolutionError, resolve_result_reference
from pixelscope.remote.iqa_submission import (
    FolderPairEntry,
    IqaJobCreated,
    IqaJobRequest,
    IqaJobStatus,
    IqaResultReference,
    JobState,
    PreflightError,
    build_request,
    is_remote_eligible_path,
    pair_current_paths,
    pair_folders,
)
from pixelscope.remote.iqa_v2_domain import VersionedResultLoadOutcome
from pixelscope.remote.iqa_v2_partial import PartialResultV2
from pixelscope.ui.iqa_remote_settings import install_remote_iqa_settings_dialog
from pixelscope.ui.iqa_workspace import IqaWorkspaceController, IqaWorkspaceWidget
from pixelscope.workers.task_worker import TaskError, TaskWorker

POLL_INTERVAL_MS = 1200
REMOTE_WORKER_LIMIT = 2


@dataclass
class RemoteJobRecord:
    job_id: str
    submission_kind: str
    server_base_url: str
    state: JobState
    completed_scenes: int | None = None
    total_scenes: int | None = None
    message: str | None = None
    result_reference: IqaResultReference | None = None
    result_path: Path | None = None
    result_resolution_error: str | None = None

    @property
    def progress_text(self) -> str:
        if self.completed_scenes is None or self.total_scenes is None:
            return "—"
        return f"{self.completed_scenes} / {self.total_scenes}"


@dataclass(frozen=True)
class _SubmissionPayload:
    created: IqaJobCreated
    submission_kind: str
    server_base_url: str
    scene_count: int


@dataclass(frozen=True)
class _FolderPreviewPayload:
    folder_a: str
    folder_b: str
    entries: tuple[FolderPairEntry, ...]


@dataclass(frozen=True)
class _ResultResolutionPayload:
    job_id: str
    path: Path | None
    error: str | None


class RemoteIqaWorkspace(QWidget):
    """One IQA dock shell containing Setup, Jobs, and the existing P5-B Results UI."""

    preview_requested = Signal(str, str)
    folder_submit_requested = Signal(str, str)
    current_submit_requested = Signal()
    cancel_requested = Signal(str)
    open_result_requested = Signal(str)
    settings_requested = Signal()

    def __init__(
        self,
        results_workspace: IqaWorkspaceWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("remoteIqaWorkspace")
        self._jobs: dict[str, RemoteJobRecord] = {}
        self._job_items: dict[str, QTreeWidgetItem] = {}
        self._preview_identity: tuple[str, str] | None = None
        self._preview_entries: tuple[FolderPairEntry, ...] = ()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 0)
        layout.setSpacing(6)
        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("iqaWorkflowTabs")
        layout.addWidget(self.tabs, 1)

        self.setup_page = QWidget(self.tabs)
        self.jobs_page = QWidget(self.tabs)
        self.results_page = QWidget(self.tabs)
        self.tabs.addTab(self.setup_page, "Setup")
        self.tabs.addTab(self.jobs_page, "Jobs")
        self.tabs.addTab(self.results_page, "Results")
        self._build_setup_page()
        self._build_jobs_page()
        self._build_results_page(results_workspace)

    def _build_setup_page(self) -> None:
        layout = QVBoxLayout(self.setup_page)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(8)
        settings_row = QHBoxLayout()
        self.configuration_label = QLabel(
            "Remote IQA is not configured.",
            self.setup_page,
        )
        self.configuration_label.setObjectName("remoteIqaConfigurationStatus")
        self.configure_button = QPushButton("Settings...", self.setup_page)
        self.configure_button.setObjectName("remoteIqaSettings")
        self.configure_button.clicked.connect(  # type: ignore[attr-defined]
            self.settings_requested.emit
        )
        settings_row.addWidget(self.configuration_label, 1)
        settings_row.addWidget(self.configure_button)
        layout.addLayout(settings_row)

        current_heading = QLabel("Current Pair", self.setup_page)
        current_font = current_heading.font()
        current_font.setBold(True)
        current_heading.setFont(current_font)
        layout.addWidget(current_heading)
        self.current_pair_label = QLabel(
            "Current Comparison Page is not an eligible pair.",
            self.setup_page,
        )
        self.current_pair_label.setObjectName("remoteIqaCurrentPairSummary")
        self.current_pair_label.setWordWrap(True)
        layout.addWidget(self.current_pair_label)
        self.current_submit = QPushButton("Submit Current Pair", self.setup_page)
        self.current_submit.setObjectName("remoteIqaSubmitCurrentPair")
        self.current_submit.clicked.connect(  # type: ignore[attr-defined]
            self.current_submit_requested.emit
        )
        layout.addWidget(self.current_submit)

        folder_heading = QLabel("Folder Pair", self.setup_page)
        folder_font = folder_heading.font()
        folder_font.setBold(True)
        folder_heading.setFont(folder_font)
        layout.addWidget(folder_heading)
        self.folder_a = QLineEdit(self.setup_page)
        self.folder_a.setObjectName("remoteIqaFolderA")
        self.folder_b = QLineEdit(self.setup_page)
        self.folder_b.setObjectName("remoteIqaFolderB")
        self.folder_a.setPlaceholderText("Folder A")
        self.folder_b.setPlaceholderText("Folder B")
        self.folder_a_browse = QPushButton("Browse A...", self.setup_page)
        self.folder_b_browse = QPushButton("Browse B...", self.setup_page)
        for editor, button, title in (
            (self.folder_a, self.folder_a_browse, "Select Remote IQA Folder A"),
            (self.folder_b, self.folder_b_browse, "Select Remote IQA Folder B"),
        ):
            row = QHBoxLayout()
            row.addWidget(editor, 1)
            row.addWidget(button)
            layout.addLayout(row)
            button.clicked.connect(  # type: ignore[attr-defined]
                lambda _checked=False, target=editor, caption=title: self._browse_folder(
                    target,
                    caption,
                )
            )
        self.folder_a.textChanged.connect(  # type: ignore[attr-defined]
            self._folder_inputs_changed
        )
        self.folder_b.textChanged.connect(  # type: ignore[attr-defined]
            self._folder_inputs_changed
        )

        folder_actions = QHBoxLayout()
        self.preview_button = QPushButton("Validate / Preview", self.setup_page)
        self.preview_button.setObjectName("remoteIqaPreviewFolderPair")
        self.folder_submit = QPushButton("Submit Folder Pair", self.setup_page)
        self.folder_submit.setObjectName("remoteIqaSubmitFolderPair")
        self.preview_button.clicked.connect(  # type: ignore[attr-defined]
            self._request_preview
        )
        self.folder_submit.clicked.connect(  # type: ignore[attr-defined]
            self._request_folder_submit
        )
        folder_actions.addWidget(self.preview_button)
        folder_actions.addWidget(self.folder_submit)
        folder_actions.addStretch(1)
        layout.addLayout(folder_actions)

        self.preview_status = QLabel(
            "Choose Folder A and Folder B, then validate the full pair.",
            self.setup_page,
        )
        self.preview_status.setObjectName("remoteIqaPairPreviewStatus")
        self.preview_status.setWordWrap(True)
        layout.addWidget(self.preview_status)
        self.preview_table = QTableWidget(0, 5, self.setup_page)
        self.preview_table.setObjectName("remoteIqaPairPreview")
        self.preview_table.setHorizontalHeaderLabels(
            ("Scene", "A", "B", "Width", "Height")
        )
        self.preview_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.preview_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.preview_table.verticalHeader().setVisible(False)
        header = self.preview_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.preview_table, 1)
        self.folder_submit.setEnabled(False)
        self.current_submit.setEnabled(False)

    def _build_jobs_page(self) -> None:
        layout = QVBoxLayout(self.jobs_page)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(6)
        self.jobs_tree = QTreeWidget(self.jobs_page)
        self.jobs_tree.setObjectName("remoteIqaJobs")
        self.jobs_tree.setColumnCount(5)
        self.jobs_tree.setHeaderLabels(
            ("Job ID", "Kind", "State", "Progress", "Message")
        )
        self.jobs_tree.setRootIsDecorated(False)
        self.jobs_tree.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.jobs_tree.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        header = self.jobs_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.jobs_tree, 1)
        buttons = QHBoxLayout()
        self.cancel_button = QPushButton("Cancel", self.jobs_page)
        self.cancel_button.setObjectName("remoteIqaCancelJob")
        self.open_button = QPushButton("Open Result", self.jobs_page)
        self.open_button.setObjectName("remoteIqaOpenResult")
        self.cancel_button.setEnabled(False)
        self.open_button.setEnabled(False)
        self.cancel_button.clicked.connect(  # type: ignore[attr-defined]
            self._cancel_selected
        )
        self.open_button.clicked.connect(  # type: ignore[attr-defined]
            self._open_selected
        )
        self.jobs_tree.itemSelectionChanged.connect(  # type: ignore[attr-defined]
            self._job_selection_changed
        )
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.open_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.jobs_status = QLabel(
            "No Remote IQA jobs in this PixelScope process.",
            self.jobs_page,
        )
        self.jobs_status.setObjectName("remoteIqaJobsStatus")
        self.jobs_status.setWordWrap(True)
        layout.addWidget(self.jobs_status)

    def _build_results_page(self, results_workspace: IqaWorkspaceWidget) -> None:
        layout = QVBoxLayout(self.results_page)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(6)
        self.partial_status = QLabel("", self.results_page)
        self.partial_status.setObjectName("remoteIqaPartialStatus")
        self.partial_status.setWordWrap(True)
        self.partial_status.hide()
        layout.addWidget(self.partial_status)
        self.partial_diagnostics = QTreeWidget(self.results_page)
        self.partial_diagnostics.setObjectName("remoteIqaPartialDiagnostics")
        self.partial_diagnostics.setColumnCount(5)
        self.partial_diagnostics.setHeaderLabels(
            ("Scene", "Status", "Code", "Retryable", "Message")
        )
        self.partial_diagnostics.setRootIsDecorated(False)
        self.partial_diagnostics.setMaximumHeight(160)
        self.partial_diagnostics.hide()
        layout.addWidget(self.partial_diagnostics)
        layout.addWidget(results_workspace, 1)

    def set_configuration_state(self, settings: RemoteIqaSettings) -> None:
        if settings.submission_configured:
            staging = settings.staging_root_id or "none"
            self.configuration_label.setText(
                f"Configured · {len(settings.storage_roots)} storage root(s) · "
                f"staging: {staging}"
            )
        else:
            self.configuration_label.setText(
                "Remote IQA submission unavailable · configure server URL and "
                "storage roots."
            )
        self.folder_submit.setEnabled(
            settings.submission_configured and self._preview_identity is not None
        )

    def set_current_pair_state(
        self,
        summary: str,
        eligible: bool,
        reason: str | None,
    ) -> None:
        self.current_pair_label.setText(
            summary if eligible else f"Unavailable · {reason or summary}"
        )
        self.current_pair_label.setToolTip("" if eligible else (reason or summary))
        self.current_submit.setEnabled(eligible)

    def show_preview_loading(self) -> None:
        self.preview_status.setText("Validating Folder Pair...")
        self.preview_button.setEnabled(False)
        self.folder_submit.setEnabled(False)

    def set_folder_preview(self, payload: _FolderPreviewPayload) -> None:
        self._preview_identity = (payload.folder_a, payload.folder_b)
        self._preview_entries = payload.entries
        self.preview_table.setRowCount(len(payload.entries))
        for row, entry in enumerate(payload.entries):
            values = (
                entry.scene_id,
                entry.source_a.path.name,
                entry.source_b.path.name,
                str(entry.source_a.width),
                str(entry.source_a.height),
            )
            for column, value in enumerate(values):
                self.preview_table.setItem(row, column, QTableWidgetItem(value))
        self.preview_status.setText(
            f"Validated full Pair Preview · {len(payload.entries)} Scenes"
        )
        self.preview_button.setEnabled(True)

    def show_preview_error(self, message: str) -> None:
        self._preview_identity = None
        self._preview_entries = ()
        self.preview_table.setRowCount(0)
        self.preview_status.setText(f"Blocked · {message}")
        self.preview_button.setEnabled(True)
        self.folder_submit.setEnabled(False)

    @property
    def preview_identity(self) -> tuple[str, str] | None:
        return self._preview_identity

    @property
    def preview_entries(self) -> tuple[FolderPairEntry, ...]:
        return self._preview_entries

    def upsert_job(self, job: RemoteJobRecord) -> None:
        self._jobs[job.job_id] = job
        item = self._job_items.get(job.job_id)
        if item is None:
            item = QTreeWidgetItem(self.jobs_tree)
            item.setData(0, Qt.ItemDataRole.UserRole, job.job_id)
            self._job_items[job.job_id] = item
        item.setText(0, job.job_id)
        item.setText(1, job.submission_kind)
        item.setText(2, job.state.value)
        item.setText(3, job.progress_text)
        message = job.message or ""
        if job.result_resolution_error:
            message = job.result_resolution_error
        item.setText(4, message)
        if self.jobs_tree.currentItem() is None:
            self.jobs_tree.setCurrentItem(item)
        self.jobs_status.setText(
            f"{len(self._jobs)} job(s) tracked locally · remote jobs remain durable "
            "on close"
        )
        self._job_selection_changed()

    def show_submission_error(self, message: str) -> None:
        self.jobs_status.setText(f"Submission blocked/failed · {message}")
        self.tabs.setCurrentWidget(self.jobs_page)

    def show_job_operation_error(self, job_id: str, message: str) -> None:
        job = self._jobs.get(job_id)
        if job is not None:
            job.message = message
            self.upsert_job(job)
        self.jobs_status.setText(f"{job_id} · {message}")

    def present_result_outcome(self, outcome: VersionedResultLoadOutcome) -> None:
        result = outcome.result
        self.partial_diagnostics.clear()
        if outcome.succeeded and isinstance(result, PartialResultV2):
            self.partial_status.setText(
                f"Partial result · {result.successful_scene_count} / "
                f"{result.requested_scene_count} Scenes succeeded"
            )
            self.partial_status.show()
            for scene in result.unsuccessful_scene_outcomes:
                item = QTreeWidgetItem(self.partial_diagnostics)
                item.setText(0, scene.scene_id)
                item.setText(1, scene.status)
                item.setText(2, scene.error_code or "")
                retryable = (
                    "—" if scene.retryable is None else str(scene.retryable).lower()
                )
                item.setText(3, retryable)
                item.setText(4, scene.error_message or "")
            self.partial_diagnostics.setVisible(
                bool(result.unsuccessful_scene_outcomes)
            )
        else:
            self.partial_status.hide()
            self.partial_diagnostics.hide()
        if outcome.succeeded:
            self.tabs.setCurrentWidget(self.results_page)

    def _folder_inputs_changed(self, _text: str) -> None:
        identity = (self.folder_a.text().strip(), self.folder_b.text().strip())
        if identity != self._preview_identity:
            self._preview_identity = None
            self._preview_entries = ()
            self.preview_table.setRowCount(0)
            self.preview_status.setText(
                "Folder inputs changed · validate the full pair again."
            )
            self.folder_submit.setEnabled(False)

    def _request_preview(self) -> None:
        folder_a = self.folder_a.text().strip()
        folder_b = self.folder_b.text().strip()
        if not folder_a or not folder_b:
            self.show_preview_error("choose both folders")
            return
        self.preview_requested.emit(folder_a, folder_b)

    def _request_folder_submit(self) -> None:
        identity = (self.folder_a.text().strip(), self.folder_b.text().strip())
        if identity != self._preview_identity:
            self.show_preview_error("validate the current folder inputs before submit")
            return
        self.folder_submit_requested.emit(*identity)

    def _browse_folder(self, target: QLineEdit, caption: str) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            caption,
            target.text().strip(),
        )
        if selected:
            target.setText(selected)

    def _selected_job_id(self) -> str | None:
        item = self.jobs_tree.currentItem()
        if item is None:
            return None
        value = item.data(0, Qt.ItemDataRole.UserRole)
        return str(value) if isinstance(value, str) else None

    def _job_selection_changed(self) -> None:
        job_id = self._selected_job_id()
        job = self._jobs.get(job_id) if job_id is not None else None
        self.cancel_button.setEnabled(job is not None and not job.state.terminal)
        self.open_button.setEnabled(
            job is not None
            and job.state in {JobState.SUCCEEDED, JobState.PARTIAL}
            and job.result_path is not None
        )
        if job is not None and job.result_resolution_error:
            self.open_button.setToolTip(job.result_resolution_error)
        else:
            self.open_button.setToolTip("")

    def _cancel_selected(self) -> None:
        job_id = self._selected_job_id()
        if job_id is not None:
            self.cancel_requested.emit(job_id)

    def _open_selected(self) -> None:
        job_id = self._selected_job_id()
        if job_id is not None:
            self.open_result_requested.emit(job_id)


class RemoteIqaController(QObject):
    """Bounded worker/polling owner; remote job state never owns local image authority."""

    def __init__(
        self,
        window: Any,
        workspace: RemoteIqaWorkspace,
        result_controller: IqaWorkspaceController,
        *,
        client_factory: Callable[[str], IqaJobClient] | None = None,
    ) -> None:
        super().__init__(window)
        self.window = window
        self.workspace = workspace
        self.result_controller = result_controller
        self._client_factory = client_factory or (lambda url: HttpIqaJobClient(url))
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(REMOTE_WORKER_LIMIT)
        self._workers: dict[str, TaskWorker] = {}
        self._jobs: dict[str, RemoteJobRecord] = {}
        self._polling_jobs: set[str] = set()
        self._result_fetch_jobs: set[str] = set()
        self._result_resolve_jobs: set[str] = set()
        self._generation = 0
        self._active = True
        self._last_pair_identity: tuple[object, ...] | None = None

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(  # type: ignore[attr-defined]
            self._poll_due
        )
        self._poll_timer.start()
        self._state_timer = QTimer(self)
        self._state_timer.setInterval(400)
        self._state_timer.timeout.connect(  # type: ignore[attr-defined]
            self.refresh_setup_state
        )
        self._state_timer.start()

        workspace.preview_requested.connect(self.preview_folders)
        workspace.folder_submit_requested.connect(self.submit_folders)
        workspace.current_submit_requested.connect(self.submit_current_pair)
        workspace.cancel_requested.connect(self.cancel_job)
        workspace.open_result_requested.connect(self.open_result)
        workspace.settings_requested.connect(self.open_settings)
        result_controller.outcome_ready.connect(workspace.present_result_outcome)
        self.refresh_setup_state()

    def settings_changed(self) -> None:
        if not self._active:
            return
        self.refresh_setup_state()
        for job in self._jobs.values():
            if job.result_reference is not None and job.state in {
                JobState.SUCCEEDED,
                JobState.PARTIAL,
            }:
                self._resolve_result_path(job)

    def refresh_setup_state(self) -> None:
        if not self._active:
            return
        settings = self.window.application_settings.remote_iqa
        self.workspace.set_configuration_state(settings)
        documents = list(self.window.current_comparison_documents())
        identity = tuple(getattr(item, "document_id", None) for item in documents)
        identity += (settings.submission_configured,)
        if identity == self._last_pair_identity:
            return
        self._last_pair_identity = identity
        if not settings.submission_configured:
            self.workspace.set_current_pair_state(
                "Remote IQA is not configured.",
                False,
                "configure the Remote IQA server and storage roots",
            )
            return
        if len(documents) != 2:
            self.workspace.set_current_pair_state(
                "Current Pair requires exactly two native sources.",
                False,
                "Current Comparison Page must contain exactly two images",
            )
            return
        paths: list[Path] = []
        for document in documents:
            path = getattr(document, "source_path", None)
            if not isinstance(path, Path):
                self.workspace.set_current_pair_state(
                    "Current Pair is not backed by two native source paths.",
                    False,
                    "derived Split/Difference documents are not Remote IQA inputs",
                )
                return
            if not is_remote_eligible_path(path):
                reason = (
                    "RAW is not eligible for Remote IQA"
                    if path.suffix.casefold() == ".raw"
                    else "unsupported Remote IQA extension"
                )
                self.workspace.set_current_pair_state(
                    "Current Pair is not eligible.",
                    False,
                    reason,
                )
                return
            paths.append(path)
        self.workspace.set_current_pair_state(
            f"A: {paths[0].name}  ·  B: {paths[1].name}",
            True,
            None,
        )

    @Slot()
    def submit_current_pair(self) -> None:
        if not self._active:
            return
        settings = self.window.application_settings.remote_iqa
        documents = list(self.window.current_comparison_documents())
        if len(documents) != 2:
            self.workspace.show_submission_error(
                "Current Comparison Page is no longer exactly two images"
            )
            return
        path_a = getattr(documents[0], "source_path", None)
        path_b = getattr(documents[1], "source_path", None)
        if not isinstance(path_a, Path) or not isinstance(path_b, Path):
            self.workspace.show_submission_error(
                "Current Pair is not two native source paths"
            )
            return
        self._start_submission(
            "current_pair",
            lambda: pair_current_paths(path_a, path_b),
            settings,
        )

    @Slot(str, str)
    def preview_folders(self, folder_a: str, folder_b: str) -> None:
        if not self._active:
            return
        self.workspace.show_preview_loading()
        worker = TaskWorker(
            lambda: _FolderPreviewPayload(
                folder_a,
                folder_b,
                pair_folders(folder_a, folder_b),
            ),
            generation=self._generation,
        )
        worker.signals.succeeded.connect(self._preview_ready)
        worker.signals.failed.connect(self._preview_failed)
        self._track_worker(worker)

    @Slot(str, str)
    def submit_folders(self, folder_a: str, folder_b: str) -> None:
        if not self._active:
            return
        preview = self.workspace.preview_entries
        preview_identity = self.workspace.preview_identity
        if preview_identity != (folder_a, folder_b) or not preview:
            self.workspace.show_submission_error(
                "validate the full Folder Pair before submit"
            )
            return
        settings = self.window.application_settings.remote_iqa

        def entries() -> tuple[FolderPairEntry, ...]:
            current = pair_folders(folder_a, folder_b)
            if _preview_signature(current) != _preview_signature(preview):
                raise PreflightError(
                    "Folder Pair changed after preview; validate again before submit"
                )
            return current

        self._start_submission("folder_pair", entries, settings)

    def _start_submission(
        self,
        submission_kind: str,
        entries_factory: Callable[[], tuple[FolderPairEntry, ...]],
        settings: RemoteIqaSettings,
    ) -> None:
        if not settings.submission_configured:
            self.workspace.show_submission_error("Remote IQA is not configured")
            return
        server_url = settings.server_base_url

        def prepare_create() -> _SubmissionPayload:
            entries = entries_factory()
            request = build_request(
                entries,
                settings,
                submission_kind=submission_kind,
            )
            created = _create_job(self._client_factory(server_url), request)
            return _SubmissionPayload(
                created,
                submission_kind,
                server_url,
                len(entries),
            )

        worker = TaskWorker(prepare_create, generation=self._generation)
        worker.signals.succeeded.connect(self._submission_ready)
        worker.signals.failed.connect(self._submission_failed)
        self._track_worker(worker)
        self.workspace.jobs_status.setText(
            "Preparing/staging and submitting Remote IQA job..."
        )
        self.workspace.tabs.setCurrentWidget(self.workspace.jobs_page)

    @Slot(str, object, int, object)
    def _submission_ready(
        self,
        _task_id: str,
        _document_id: object,
        generation: int,
        value: object,
    ) -> None:
        if not self._accept_generation(generation) or not isinstance(
            value,
            _SubmissionPayload,
        ):
            return
        created = value.created
        job = RemoteJobRecord(
            created.job_id,
            value.submission_kind,
            value.server_base_url,
            created.state,
            0,
            value.scene_count,
            "queued",
        )
        self._jobs[job.job_id] = job
        self.workspace.upsert_job(job)
        self.workspace.tabs.setCurrentWidget(self.workspace.jobs_page)

    @Slot(str, object, int, object)
    def _submission_failed(
        self,
        _task_id: str,
        _document_id: object,
        generation: int,
        value: object,
    ) -> None:
        if not self._accept_generation(generation):
            return
        self.workspace.show_submission_error(_task_error_message(value))

    @Slot(str, object, int, object)
    def _preview_ready(
        self,
        _task_id: str,
        _document_id: object,
        generation: int,
        value: object,
    ) -> None:
        if not self._accept_generation(generation) or not isinstance(
            value,
            _FolderPreviewPayload,
        ):
            return
        current_identity = (
            self.workspace.folder_a.text().strip(),
            self.workspace.folder_b.text().strip(),
        )
        if current_identity != (value.folder_a, value.folder_b):
            return
        self.workspace.set_folder_preview(value)
        self.workspace.set_configuration_state(
            self.window.application_settings.remote_iqa
        )

    @Slot(str, object, int, object)
    def _preview_failed(
        self,
        _task_id: str,
        _document_id: object,
        generation: int,
        value: object,
    ) -> None:
        if self._accept_generation(generation):
            self.workspace.show_preview_error(_task_error_message(value))

    @Slot()
    def _poll_due(self) -> None:
        if not self._active:
            return
        for job in tuple(self._jobs.values()):
            if job.state.terminal or job.job_id in self._polling_jobs:
                continue
            self._polling_jobs.add(job.job_id)
            worker = TaskWorker(
                _get_status,
                self._client_factory(job.server_base_url),
                job.job_id,
                document_id=job.job_id,
                generation=self._generation,
            )
            worker.signals.succeeded.connect(self._status_ready)
            worker.signals.failed.connect(self._status_failed)
            worker.signals.finished.connect(self._poll_finished)
            self._track_worker(worker)

    @Slot(str, object, int, object)
    def _status_ready(
        self,
        _task_id: str,
        document_id: object,
        generation: int,
        value: object,
    ) -> None:
        if (
            not self._accept_generation(generation)
            or not isinstance(document_id, str)
            or not isinstance(value, IqaJobStatus)
        ):
            return
        job = self._jobs.get(document_id)
        if job is None or job.state.terminal:
            return
        job.state = value.state
        job.completed_scenes = value.completed_scenes
        job.total_scenes = value.total_scenes
        job.message = value.message
        self.workspace.upsert_job(job)
        if value.state in {JobState.SUCCEEDED, JobState.PARTIAL}:
            self._fetch_result_reference(job)

    @Slot(str, object, int, object)
    def _status_failed(
        self,
        _task_id: str,
        document_id: object,
        generation: int,
        value: object,
    ) -> None:
        if self._accept_generation(generation) and isinstance(document_id, str):
            self.workspace.show_job_operation_error(
                document_id,
                f"status unavailable · {_task_error_message(value)}",
            )

    @Slot(str)
    def _poll_finished(self, task_id: str) -> None:
        worker = self._workers.get(task_id)
        if worker is not None and worker.document_id is not None:
            self._polling_jobs.discard(worker.document_id)

    def _fetch_result_reference(self, job: RemoteJobRecord) -> None:
        if job.result_reference is not None or job.job_id in self._result_fetch_jobs:
            return
        self._result_fetch_jobs.add(job.job_id)
        worker = TaskWorker(
            _get_result,
            self._client_factory(job.server_base_url),
            job.job_id,
            document_id=job.job_id,
            generation=self._generation,
        )
        worker.signals.succeeded.connect(self._result_reference_ready)
        worker.signals.failed.connect(self._result_reference_failed)
        worker.signals.finished.connect(self._result_fetch_finished)
        self._track_worker(worker)

    @Slot(str, object, int, object)
    def _result_reference_ready(
        self,
        _task_id: str,
        document_id: object,
        generation: int,
        value: object,
    ) -> None:
        if (
            not self._accept_generation(generation)
            or not isinstance(document_id, str)
            or not isinstance(value, IqaResultReference)
        ):
            return
        job = self._jobs.get(document_id)
        if job is None or job.state not in {JobState.SUCCEEDED, JobState.PARTIAL}:
            return
        expected_state = (
            "complete" if job.state is JobState.SUCCEEDED else "partial"
        )
        if value.publication_state != expected_state:
            self.workspace.show_job_operation_error(
                job.job_id,
                "terminal state/result publication mismatch",
            )
            return
        job.result_reference = value
        job.message = "result published"
        self.workspace.upsert_job(job)
        self._resolve_result_path(job)

    @Slot(str, object, int, object)
    def _result_reference_failed(
        self,
        _task_id: str,
        document_id: object,
        generation: int,
        value: object,
    ) -> None:
        if self._accept_generation(generation) and isinstance(document_id, str):
            self.workspace.show_job_operation_error(
                document_id,
                f"result reference unavailable · {_task_error_message(value)}",
            )

    @Slot(str)
    def _result_fetch_finished(self, task_id: str) -> None:
        worker = self._workers.get(task_id)
        if worker is not None and worker.document_id is not None:
            self._result_fetch_jobs.discard(worker.document_id)

    def _resolve_result_path(self, job: RemoteJobRecord) -> None:
        reference = job.result_reference
        if reference is None or job.job_id in self._result_resolve_jobs:
            return
        self._result_resolve_jobs.add(job.job_id)
        settings = self.window.application_settings.remote_iqa

        def resolve() -> _ResultResolutionPayload:
            try:
                path = resolve_result_reference(
                    reference.storage_root_id,
                    reference.relative_path,
                    settings,
                )
            except StorageResolutionError as exc:
                return _ResultResolutionPayload(job.job_id, None, str(exc))
            return _ResultResolutionPayload(job.job_id, path, None)

        worker = TaskWorker(
            resolve,
            document_id=job.job_id,
            generation=self._generation,
        )
        worker.signals.succeeded.connect(self._result_path_ready)
        worker.signals.finished.connect(self._result_resolve_finished)
        self._track_worker(worker)

    @Slot(str, object, int, object)
    def _result_path_ready(
        self,
        _task_id: str,
        document_id: object,
        generation: int,
        value: object,
    ) -> None:
        if (
            not self._accept_generation(generation)
            or not isinstance(document_id, str)
            or not isinstance(value, _ResultResolutionPayload)
        ):
            return
        job = self._jobs.get(document_id)
        if job is None:
            return
        job.result_path = value.path
        job.result_resolution_error = value.error
        self.workspace.upsert_job(job)

    @Slot(str)
    def _result_resolve_finished(self, task_id: str) -> None:
        worker = self._workers.get(task_id)
        if worker is not None and worker.document_id is not None:
            self._result_resolve_jobs.discard(worker.document_id)

    @Slot(str)
    def cancel_job(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        if not self._active or job is None or job.state.terminal:
            return
        worker = TaskWorker(
            _cancel_job,
            self._client_factory(job.server_base_url),
            job_id,
            document_id=job_id,
            generation=self._generation,
        )
        worker.signals.succeeded.connect(self._status_ready)
        worker.signals.failed.connect(self._status_failed)
        self._track_worker(worker)

    @Slot(str)
    def open_result(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        if job is None or job.state not in {JobState.SUCCEEDED, JobState.PARTIAL}:
            return
        if job.result_path is None:
            self.workspace.show_job_operation_error(
                job_id,
                job.result_resolution_error
                or "result root is not resolvable with current settings",
            )
            return
        self.result_controller.open_result(job.result_path)
        self.workspace.tabs.setCurrentWidget(self.workspace.results_page)

    @Slot()
    def open_settings(self) -> None:
        dialog = self.window.create_settings_dialog()
        matches = dialog.category_list.findItems(
            "Remote IQA",
            Qt.MatchFlag.MatchExactly,
        )
        if matches:
            dialog.category_list.setCurrentItem(matches[0])
        dialog.exec()

    def shutdown(self) -> None:
        if not self._active:
            return
        self._active = False
        self._generation += 1
        self._poll_timer.stop()
        self._state_timer.stop()
        for worker in tuple(self._workers.values()):
            worker.cancel()
        self._workers.clear()
        self._polling_jobs.clear()
        self._result_fetch_jobs.clear()
        self._result_resolve_jobs.clear()
        self._pool.clear()
        # Deliberately no remote cancel: server jobs are durable across PixelScope close.

    def _track_worker(self, worker: TaskWorker) -> None:
        if not self._active:
            worker.cancel()
            return
        self._workers[worker.task_id] = worker
        worker.signals.finished.connect(self._worker_finished)
        self._pool.start(worker)

    @Slot(str)
    def _worker_finished(self, task_id: str) -> None:
        self._workers.pop(task_id, None)

    def _accept_generation(self, generation: int) -> bool:
        return self._active and generation == self._generation


class _RemoteIqaCloseFilter(QObject):
    def __init__(self, controller: RemoteIqaController, parent: QObject) -> None:
        super().__init__(parent)
        self.controller = controller

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() is QEvent.Type.Close:
            self.controller.shutdown()
        return super().eventFilter(watched, event)


def install_remote_iqa(
    window: Any,
    *,
    client_factory: Callable[[str], IqaJobClient] | None = None,
) -> RemoteIqaController:
    """Extend the one IQA dock; never create a second result parser/controller path."""

    install_remote_iqa_settings_dialog(window)
    existing_results = window.iqa_workspace
    shell = RemoteIqaWorkspace(existing_results)
    window.iqa_dock.setWidget(shell)
    controller = RemoteIqaController(
        window,
        shell,
        window.iqa_controller,
        client_factory=client_factory,
    )
    window.remote_iqa_workspace = shell
    window.remote_iqa_controller = controller
    close_filter = _RemoteIqaCloseFilter(controller, window)
    window.installEventFilter(close_filter)
    window._remote_iqa_close_filter = close_filter
    return controller


def _preview_signature(
    entries: tuple[FolderPairEntry, ...],
) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            item.scene_id,
            str(item.source_a.path.resolve(strict=False)),
            item.source_a.width,
            item.source_a.height,
            str(item.source_b.path.resolve(strict=False)),
            item.source_b.width,
            item.source_b.height,
        )
        for item in entries
    )


def _create_job(client: IqaJobClient, request: IqaJobRequest) -> IqaJobCreated:
    try:
        return client.create_job(request)
    finally:
        client.close()


def _get_status(client: IqaJobClient, job_id: str) -> IqaJobStatus:
    try:
        return client.get_status(job_id)
    finally:
        client.close()


def _get_result(client: IqaJobClient, job_id: str) -> IqaResultReference:
    try:
        return client.get_result(job_id)
    finally:
        client.close()


def _cancel_job(client: IqaJobClient, job_id: str) -> IqaJobStatus:
    try:
        return client.cancel_job(job_id)
    finally:
        client.close()


def _task_error_message(value: object) -> str:
    if isinstance(value, TaskError):
        clean = " ".join(value.message.split())
        return (clean or value.exception_type)[:512]
    clean = " ".join(str(value).split())
    return (clean or "unexpected Remote IQA error")[:512]
