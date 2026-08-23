"""P5-E historical IQA Result coordinator and passive provenance UI."""

from __future__ import annotations

import logging
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from types import MethodType
from typing import Any

from PySide6.QtCore import QObject, QSettings, Slot
from PySide6.QtWidgets import (
    QLabel,
    QMenu,
    QMessageBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pixelscope.app.iqa_history import RecentIqaResultsRepository
from pixelscope.app.settings import QSettingsAdapter
from pixelscope.remote.iqa_domain import LoadStatus, Result
from pixelscope.remote.iqa_history import (
    IqaResultIdentity,
    IqaResultLocator,
    LocalIqaResultLocator,
    LogicalIqaResultLocator,
    RecentIqaResultEntry,
    locator_for_manual_result,
    locator_leaf,
)
from pixelscope.remote.iqa_settings import RemoteIqaSettings
from pixelscope.remote.iqa_storage import StorageResolutionError, resolve_result_reference
from pixelscope.remote.iqa_submission import JobState
from pixelscope.remote.iqa_v2_domain import ResultV2, VersionedResultLoadOutcome
from pixelscope.remote.iqa_v2_partial import PartialResultV2
from pixelscope.ui.design_tokens import TOKENS, menu_style
from pixelscope.workers.task_worker import TaskWorker
from pixelscope.workers.thread_pools import analysis_thread_pool

LOGGER = logging.getLogger(__name__)
_MAPPING_CHANGED = "storage mapping changed while opening"


@dataclass(frozen=True)
class _PendingOpen:
    root: Path
    locator: IqaResultLocator | None
    expected: IqaResultIdentity | None
    mapping_revision: int | None
    from_recent: bool
    previous: IqaResultIdentity | None


@dataclass(frozen=True)
class _ResolvedRecent:
    entry: RecentIqaResultEntry
    revision: int
    path: Path | None
    error: str | None


class IqaProvenancePanel(QWidget):
    """Display published metadata only; never load native pixels or recompute IQA."""

    def __init__(self, workspace: Any) -> None:
        super().__init__(workspace.pages)
        self.workspace = workspace
        self.result: Result | ResultV2 | None = None
        self.locator: IqaResultLocator | None = None
        self.settings = RemoteIqaSettings()
        self.native_status = "not yet verified"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, TOKENS.spacing_sm, 0, 0)
        layout.setSpacing(TOKENS.spacing_sm)
        self.status = QLabel("No IQA result is open.", self)
        self.status.setObjectName("iqaHistoricalAvailability")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.tree = QTreeWidget(self)
        self.tree.setObjectName("iqaProvenanceTree")
        self.tree.setHeaderLabels(["Field", "Published value"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(True)
        self.tree.header().setStretchLastSection(True)
        layout.addWidget(self.tree, 1)

    def set_context(
        self,
        result: Result | ResultV2,
        locator: IqaResultLocator,
        settings: RemoteIqaSettings,
    ) -> None:
        self.result = result
        self.locator = locator
        self.settings = settings
        self.refresh()

    def set_native_status(self, text: str) -> None:
        self.native_status = text
        self.refresh()

    def refresh_settings(self, settings: RemoteIqaSettings) -> None:
        self.settings = settings
        self.refresh()

    def refresh(self) -> None:
        self.tree.clear()
        if isinstance(self.result, ResultV2):
            self._populate_v2(self.result)
        elif isinstance(self.result, Result):
            self._populate_v1(self.result)
        else:
            self.status.setText("No IQA result is open.")

    def _populate_v2(self, result: ResultV2) -> None:
        publication = "PARTIAL" if isinstance(result, PartialResultV2) else "COMPLETE"
        result_group = self._group("Result")
        self._fields(
            result_group,
            (
                ("result_id", result.result_id),
                ("schema_version", str(result.schema_version)),
                ("publication_state", publication),
                ("historical_locator", self.locator.display_location if self.locator else ""),
                ("variant_count", str(len(result.variants))),
                ("scene_count", str(len(result.scenes))),
                ("attribute_count", str(len(result.attributes))),
            ),
        )
        if isinstance(result, PartialResultV2):
            self._fields(
                result_group,
                (
                    ("requested_scene_count", str(result.requested_scene_count)),
                    ("successful_scene_count", str(result.successful_scene_count)),
                ),
            )
        scene_id = self.workspace.selected_scene_id
        if scene_id is None:
            self.status.setText(
                "Result available · Native source verification is lazy and runs only on Inspect."
            )
            return
        try:
            scene = result.scene(scene_id)
        except StopIteration:
            self.status.setText("Result available · Select a Scene to inspect provenance.")
            return
        provenance = scene.context_provenance
        scene_group = self._group("Selected Scene")
        self._fields(
            scene_group,
            (
                ("scene_id", scene.scene_id),
                ("measurement_context_id", scene.measurement_context_id),
                ("representative_id", provenance.representative_id),
                ("preprocessing_id", provenance.preprocessing_id),
                ("model_id", provenance.model_id),
                ("weighting_id", provenance.weighting_id),
                ("geometry_id", provenance.geometry_id),
                ("local_native_status", self.native_status),
            ),
        )
        configured = {item.storage_root_id for item in self.settings.storage_roots}
        unavailable = False
        for measurement in scene.sources:
            source = measurement.source
            group = self._group(f"Source · {measurement.variant_id}")
            rows: list[tuple[str, str]] = [
                ("variant_id", measurement.variant_id),
                ("source_id", source.source_id),
            ]
            if source.storage_root_id is not None:
                rows.append(("storage_root_id", source.storage_root_id))
            rows.extend(
                (
                    ("relative_path", source.relative_path),
                    ("sha256", source.sha256),
                    ("width", str(source.width)),
                    ("height", str(source.height)),
                )
            )
            if source.storage_root_id is None:
                verification = "portable locator not published"
                unavailable = True
            elif source.storage_root_id not in configured:
                verification = "storage root not configured"
                unavailable = True
            else:
                verification = "Inspect performs existence/dimension/SHA verification"
            rows.append(("native_verification", verification))
            self._fields(group, tuple(rows))
        self.status.setText(
            "Result available · Native source inspection unavailable for the selected Scene."
            if unavailable
            else "Result available · Native source verification is explicit via Inspect."
        )

    def _populate_v1(self, result: Result) -> None:
        self.status.setText(
            "Result available · Historical schema v1 read-only · Native source inspection unavailable."
        )
        group = self._group("Result · historical schema v1 / read-only")
        self._fields(
            group,
            (
                ("result_id", result.result_id),
                ("schema_version", str(result.schema_version)),
                ("historical_locator", self.locator.display_location if self.locator else ""),
                ("scene_count", str(len(result.scenes))),
                ("attribute_count", str(len(result.attributes))),
            ),
        )
        scene_id = self.workspace.selected_scene_id
        if scene_id is None:
            return
        try:
            scene = result.scene(scene_id)
        except StopIteration:
            return
        self._fields(self._group("Selected Scene"), (("scene_id", scene.scene_id),))
        for source in scene.sources:
            self._fields(
                self._group(f"Source · {source.source_id}"),
                (
                    ("source_id", source.source_id),
                    ("relative_path", source.relative_path),
                    ("sha256", source.sha256),
                    ("width", str(source.width)),
                    ("height", str(source.height)),
                ),
            )

    def _group(self, title: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem(self.tree)
        item.setText(0, title)
        font = item.font(0)
        font.setBold(True)
        item.setFont(0, font)
        item.setExpanded(True)
        return item

    @staticmethod
    def _fields(parent: QTreeWidgetItem, rows: tuple[tuple[str, str], ...]) -> None:
        for name, value in rows:
            item = QTreeWidgetItem(parent)
            item.setText(0, name)
            item.setText(1, value)
            item.setToolTip(1, value)


class HistoricalIqaResultsController(QObject):
    """Put logical/local history ahead of P5-B while consuming P5-D teardown."""

    def __init__(self, window: Any, repository: RecentIqaResultsRepository) -> None:
        super().__init__(window)
        self.window = window
        self.repository = repository
        self.result_controller = window.iqa_controller
        self.workspace = window.iqa_workspace
        self.remote_controller = window.remote_iqa_controller
        self._pool = analysis_thread_pool()
        self._active = True
        self._pending: dict[int, _PendingOpen] = {}
        self._resolve_generation = 0
        self._resolver: TaskWorker | None = None
        self._resolver_entry: RecentIqaResultEntry | None = None

        self.provenance = IqaProvenancePanel(self.workspace)
        self.workspace.pages.addTab(self.provenance, "Provenance")
        self.workspace.scene_requested.connect(self._scene_requested)
        recent = getattr(window, "recent_entries_controller", None)
        self.file_menu = getattr(recent, "file_menu", None)
        if not isinstance(self.file_menu, QMenu):
            raise RuntimeError("Historical IQA Results requires the existing File menu")
        self.recent_menu = QMenu("Open Recent IQA Results", self.file_menu)
        self.recent_menu.setStyleSheet(menu_style())
        self._install_menu()

        self._original_present = self.result_controller._present_loaded_value
        self._original_open = self.result_controller.open_result
        self._original_shutdown = self.result_controller.shutdown
        self._install_open_guard()
        self._install_job_observer()
        self._install_inspect_observer()
        self.result_controller.outcome_ready.connect(self._result_outcome)
        self.refresh_menu()

    def _install_open_guard(self) -> None:
        def present(_controller: Any, value: object) -> VersionedResultLoadOutcome:
            generation = int(getattr(self.result_controller, "_generation", -1))
            pending = self._pending.get(generation)
            result = _loaded_result(value)
            if pending is not None and result is not None:
                observed = IqaResultIdentity(str(result.result_id), int(result.schema_version))
                if pending.expected is not None and observed != pending.expected:
                    return VersionedResultLoadOutcome(
                        LoadStatus.INVALID,
                        reason=(
                            "historical identity mismatch: expected "
                            f"{pending.expected.result_id}/schema-v{pending.expected.schema_version}, "
                            f"found {observed.result_id}/schema-v{observed.schema_version}"
                        ),
                    )
                if (
                    pending.mapping_revision is not None
                    and pending.mapping_revision != self._mapping_revision()
                ):
                    return VersionedResultLoadOutcome(
                        LoadStatus.INVALID,
                        reason=f"{_MAPPING_CHANGED}; reopen uses current mapping",
                    )
            return self._original_present(value)

        def open_result(_controller: Any, root: Path | str) -> int:
            return self._start_open(Path(root))

        def shutdown(_controller: Any) -> None:
            self.shutdown()
            self._original_shutdown()

        self.result_controller._present_loaded_value = MethodType(present, self.result_controller)
        self.result_controller.open_result = MethodType(open_result, self.result_controller)
        self.result_controller.shutdown = MethodType(shutdown, self.result_controller)

    def _install_job_observer(self) -> None:
        original = self.remote_controller.open_result

        def open_job(_controller: Any, job_id: str) -> None:
            job = self.remote_controller._jobs.get(job_id)
            if (
                job is None
                or job.state not in {JobState.SUCCEEDED, JobState.PARTIAL}
                or job.result_path is None
                or job.result_reference is None
            ):
                original(job_id)
                return
            reference = job.result_reference
            self._start_open(
                job.result_path,
                locator=LogicalIqaResultLocator(
                    reference.storage_root_id,
                    reference.relative_path,
                ),
            )
            self.remote_controller.workspace.tabs.setCurrentWidget(
                self.remote_controller.workspace.results_page
            )

        signal = self.remote_controller.workspace.open_result_requested
        with suppress(RuntimeError, TypeError):
            signal.disconnect(original)
        self.remote_controller.open_result = MethodType(open_job, self.remote_controller)
        signal.connect(self.remote_controller.open_result)

    def _install_inspect_observer(self) -> None:
        inspection = getattr(self.window, "iqa_scene_inspection_controller", None)
        original = getattr(inspection, "_set_status", None)
        if not callable(original):
            return

        def status(_inspection: Any, text: str) -> None:
            original(text)
            self.provenance.set_native_status(text)

        inspection._set_status = MethodType(status, inspection)

    def _install_menu(self) -> None:
        actions = self.file_menu.actions()
        anchor = next(
            (item for item in actions if item.text().startswith("Open IQA Result")),
            None,
        )
        if anchor is None:
            self.file_menu.addMenu(self.recent_menu)
            return
        index = actions.index(anchor)
        before = actions[index + 1] if index + 1 < len(actions) else None
        if before is None:
            self.file_menu.addMenu(self.recent_menu)
        else:
            self.file_menu.insertMenu(before, self.recent_menu)

    def refresh_menu(self) -> None:
        self.recent_menu.clear()
        entries = self.repository.load()
        if not entries:
            item = self.recent_menu.addAction("(None)")
            item.setEnabled(False)
        for entry in entries:
            action = self.recent_menu.addAction(self._display_label(entry))
            action.setToolTip(entry.locator.display_location)
            action.setStatusTip(entry.locator.display_location)
            action.triggered.connect(  # type: ignore[attr-defined]
                lambda _checked=False, current=entry: self.open_recent(current)
            )
        self.recent_menu.addSeparator()
        clear_action = self.recent_menu.addAction("Clear Recent IQA Results")
        clear_action.setEnabled(bool(entries))
        clear_action.triggered.connect(self.clear_recent)  # type: ignore[attr-defined]

    def open_recent(self, entry: RecentIqaResultEntry) -> None:
        if not self._active:
            return
        self._cancel_resolver()
        if isinstance(entry.locator, LocalIqaResultLocator):
            self._start_open(
                Path(entry.locator.absolute_path),
                locator=entry.locator,
                expected=entry.identity,
                from_recent=True,
            )
            return
        self._resolve_generation += 1
        generation = self._resolve_generation
        revision = self._mapping_revision()
        settings = self.window.application_settings.remote_iqa
        locator = entry.locator

        def resolve() -> _ResolvedRecent:
            try:
                path = resolve_result_reference(
                    locator.storage_root_id,
                    locator.relative_path,
                    settings,
                )
            except StorageResolutionError as exc:
                return _ResolvedRecent(entry, revision, None, str(exc))
            return _ResolvedRecent(entry, revision, path, None)

        worker = TaskWorker(resolve, generation=generation)
        worker.signals.succeeded.connect(self._recent_resolved)
        worker.signals.failed.connect(self._recent_resolve_failed)
        worker.signals.finished.connect(self._resolver_finished)
        self._resolver = worker
        self._resolver_entry = entry
        self._pool.start(worker)
        self.window.statusBar().showMessage("Resolving historical IQA Result…", 3000)

    @Slot(str, object, int, object)
    def _recent_resolved(
        self,
        _task_id: str,
        _document_id: object,
        generation: int,
        value: object,
    ) -> None:
        if (
            not self._active
            or generation != self._resolve_generation
            or not isinstance(value, _ResolvedRecent)
        ):
            return
        if value.revision != self._mapping_revision():
            self.open_recent(value.entry)
        elif value.path is None:
            self._offer_remove_keep(
                value.entry,
                value.error or "historical result is unavailable",
            )
        else:
            self._start_open(
                value.path,
                locator=value.entry.locator,
                expected=value.entry.identity,
                mapping_revision=value.revision,
                from_recent=True,
            )

    @Slot(str, object, int, object)
    def _recent_resolve_failed(
        self,
        _task_id: str,
        _document_id: object,
        generation: int,
        _value: object,
    ) -> None:
        if (
            self._active
            and generation == self._resolve_generation
            and self._resolver_entry is not None
        ):
            self._offer_remove_keep(
                self._resolver_entry,
                "historical result location could not be resolved",
            )

    @Slot(str)
    def _resolver_finished(self, task_id: str) -> None:
        if self._resolver is not None and self._resolver.task_id == task_id:
            self._resolver = None

    def _start_open(
        self,
        root: Path,
        *,
        locator: IqaResultLocator | None = None,
        expected: IqaResultIdentity | None = None,
        mapping_revision: int | None = None,
        from_recent: bool = False,
    ) -> int:
        previous = self._current_identity()
        predicted = int(getattr(self.result_controller, "_generation", 0)) + 1
        if isinstance(locator, LogicalIqaResultLocator) and mapping_revision is None:
            mapping_revision = self._mapping_revision()
        self._pending.clear()
        self._pending[predicted] = _PendingOpen(
            root,
            locator,
            expected,
            mapping_revision,
            from_recent,
            previous,
        )
        try:
            actual = int(self._original_open(root))
        except Exception:
            self._pending.pop(predicted, None)
            raise
        if actual != predicted:
            pending = self._pending.pop(predicted)
            self._pending[actual] = pending
        return actual

    @Slot(object)
    def _result_outcome(self, outcome: object) -> None:
        generation = int(getattr(self.result_controller, "_generation", -1))
        pending = self._pending.pop(generation, None)
        if pending is None or not isinstance(outcome, VersionedResultLoadOutcome):
            return
        if outcome.status is not LoadStatus.SUCCESS or outcome.result is None:
            if (
                pending.from_recent
                and pending.locator is not None
                and pending.expected is not None
            ):
                entry = RecentIqaResultEntry(pending.locator, pending.expected)
                if (outcome.reason or "").startswith(_MAPPING_CHANGED):
                    self.open_recent(entry)
                else:
                    self._offer_remove_keep(entry, outcome.reason or "open failed")
            return
        result = outcome.result
        identity = IqaResultIdentity(str(result.result_id), int(result.schema_version))
        locator = pending.locator or locator_for_manual_result(
            pending.root,
            self.window.application_settings.remote_iqa,
            schema_version=identity.schema_version,
        )
        entry = RecentIqaResultEntry(locator, identity)
        self._record(entry)
        self.provenance.native_status = "not yet verified"
        self.provenance.set_context(
            result,
            locator,
            self.window.application_settings.remote_iqa,
        )
        if pending.previous is not None and pending.previous != identity:
            self._clear_scene()
        self.window.statusBar().showMessage(
            f"Opened IQA Result {identity.result_id} · schema v{identity.schema_version}",
            4000,
        )

    @Slot(str)
    def _scene_requested(self, _scene_id: str) -> None:
        self.provenance.refresh_settings(self.window.application_settings.remote_iqa)

    def _clear_scene(self) -> None:
        if getattr(self.workspace, "_selected_scene_id", None) is None:
            return
        self.workspace._selected_scene_id = None
        self.workspace._populate_scene_trend()
        self.workspace._populate_scene_preview()
        inspection = getattr(self.window, "iqa_scene_inspection_controller", None)
        sync = getattr(inspection, "_sync_controls", None)
        if callable(sync):
            sync()
        self.provenance.refresh()

    def _record(self, entry: RecentIqaResultEntry) -> None:
        try:
            self.repository.record(entry)
            self.refresh_menu()
        except Exception:  # noqa: BLE001 - history is best-effort observer state
            LOGGER.warning("Unable to update Recent IQA Results", exc_info=True)

    @Slot()
    def clear_recent(self) -> None:
        try:
            self.repository.clear()
            self.refresh_menu()
        except Exception as exc:  # noqa: BLE001 - explicit cleanup reports the failure
            QMessageBox.warning(
                self.window,
                "Cannot clear Recent IQA Results",
                str(exc),
            )
            return
        self.window.statusBar().showMessage("Recent IQA Results cleared", 3000)

    def _offer_remove_keep(self, entry: RecentIqaResultEntry, reason: str) -> None:
        dialog = QMessageBox(self.window)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle("Historical IQA Result unavailable")
        dialog.setText(reason)
        dialog.setInformativeText(
            "The Recent entry was kept. Remove it from Recent IQA Results?\n\n"
            f"{entry.locator.display_location}"
        )
        remove = dialog.addButton(
            "Remove",
            QMessageBox.ButtonRole.DestructiveRole,
        )
        keep = dialog.addButton("Keep", QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(keep)
        dialog.exec()
        if dialog.clickedButton() is not remove:
            return
        try:
            self.repository.remove(entry.locator)
            self.refresh_menu()
        except Exception:  # noqa: BLE001 - cleanup remains non-authoritative
            LOGGER.warning("Unable to remove Recent IQA Result", exc_info=True)

    def shutdown(self) -> None:
        if not self._active:
            return
        self._active = False
        self._resolve_generation += 1
        self._cancel_resolver()
        self._pending.clear()

    def _cancel_resolver(self) -> None:
        if self._resolver is not None:
            self._resolver.cancel()
        self._resolver = None
        self._resolver_entry = None

    def _mapping_revision(self) -> int:
        guard = getattr(self.window, "remote_iqa_result_mapping", None)
        return int(getattr(guard, "revision", 0))

    def _current_identity(self) -> IqaResultIdentity | None:
        result = self.workspace.result
        if result is None:
            return None
        try:
            return IqaResultIdentity(str(result.result_id), int(result.schema_version))
        except (AttributeError, TypeError, ValueError):
            return None

    @staticmethod
    def _display_label(entry: RecentIqaResultEntry) -> str:
        leaf = locator_leaf(entry.locator)
        location = (
            f"{entry.locator.storage_root_id}/{leaf}"
            if isinstance(entry.locator, LogicalIqaResultLocator)
            else leaf
        )
        return f"{entry.result_id} — {location}"


def _loaded_result(value: object) -> Result | ResultV2 | None:
    outcome = getattr(value, "outcome", None)
    if isinstance(outcome, VersionedResultLoadOutcome):
        return outcome.result if outcome.status is LoadStatus.SUCCESS else None
    if isinstance(value, VersionedResultLoadOutcome):
        return value.result if value.status is LoadStatus.SUCCESS else None
    return None


def install_historical_iqa_results(
    window: Any,
    repository: RecentIqaResultsRepository | None = None,
) -> HistoricalIqaResultsController:
    """Install after P5-D so every historical open consumes canonical teardown."""

    existing = getattr(window, "historical_iqa_results_controller", None)
    if isinstance(existing, HistoricalIqaResultsController):
        return existing
    if getattr(window, "iqa_scene_inspection_controller", None) is None:
        raise RuntimeError("P5-D Scene inspection must be installed before P5-E history")
    settings = getattr(window, "settings", None)
    qsettings = settings if isinstance(settings, QSettings) else QSettings()
    repo = repository or RecentIqaResultsRepository(QSettingsAdapter(qsettings))
    controller = HistoricalIqaResultsController(window, repo)
    window.historical_iqa_results_controller = controller
    return controller
