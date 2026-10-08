"""Company-neutral Reference Lite IQA integration canary.

All job/UI ownership stays inside this optional contribution. The synthetic provider
and fixture clock are not a production scheduler, persistent file reader, or IQA UX.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast
from weakref import ReferenceType, ref

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDockWidget,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pixelscope.app.window_contribution import MenuActionFactory, WindowHostAccess
from pixelscope.remote.iqa_public_contract import (
    IqaJobReference,
    IqaJobSnapshot,
    IqaJobState,
    IqaProviderError,
    IqaResult,
    IqaSubmissionIntent,
    IqaSubmissionScene,
    IqaSubmissionSource,
    IqaVariant,
)
from pixelscope.remote.iqa_public_fixture import FixtureIqaProvider, IqaFixtureProfile


class ReferenceIqaAnalysisWindow(QMainWindow):
    """Non-modal extension-owned window; NOT a production A/B/Map result viewer."""

    def __init__(self, parent: QMainWindow) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setObjectName("referenceIqaAnalysisCanary")
        self.setWindowTitle("IQA Analysis Canary (Synthetic)")
        self.resize(520, 260)
        self._result: IqaResult | None = None

        central = QWidget(self)
        layout = QVBoxLayout(central)
        self.result_label = QLabel(central)
        self.result_label.setObjectName("referenceIqaCanaryResult")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)
        self.note_label = QLabel(
            "Synthetic integration test only. No saved-file reader, A/B/Map, or ROI UI.",
            central,
        )
        self.note_label.setWordWrap(True)
        layout.addWidget(self.note_label)
        layout.addStretch()
        self.setCentralWidget(central)
        self.clear_result()

    @property
    def result(self) -> IqaResult | None:
        return self._result

    def clear_result(self) -> None:
        self._result = None
        self.result_label.setText("Empty analysis window. Run a mock job or view a completed one.")

    def present_result(self, result: IqaResult) -> None:
        self._result = result
        self.result_label.setText(
            f"Synthetic published result: {result.result_id}\n"
            f"{len(result.attributes)} attributes · {len(result.variants)} variants · "
            f"{len(result.scenes)} scenes · {result.completeness.value}"
        )


class ReferenceIqaWidget(QWidget):
    """Compact contributed job controls, with no model-specific result presentation."""

    submit_requested = Signal()
    advance_requested = Signal()
    view_result_requested = Signal()
    open_empty_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("referenceIqaWorkspace")
        layout = QVBoxLayout(self)

        self.status_label = QLabel("Synthetic IQA ready.", self)
        self.status_label.setObjectName("referenceIqaStatus")
        layout.addWidget(self.status_label)

        self.selection_label = QLabel(
            "Uses exactly two native comparison slots; otherwise a labeled synthetic pair.",
            self,
        )
        self.selection_label.setObjectName("referenceIqaSelection")
        self.selection_label.setWordWrap(True)
        layout.addWidget(self.selection_label)

        self.submit_button = QPushButton("Run Mock IQA", self)
        self.submit_button.setObjectName("referenceIqaSubmit")
        layout.addWidget(self.submit_button)

        self.jobs_list = QListWidget(self)
        self.jobs_list.setObjectName("referenceIqaJobs")
        self.jobs_list.setMinimumHeight(110)
        layout.addWidget(self.jobs_list)

        self.job_label = QLabel("No mock job.", self)
        self.job_label.setObjectName("referenceIqaJob")
        self.job_label.setWordWrap(True)
        layout.addWidget(self.job_label)

        self.advance_button = QPushButton("Advance Selected Mock Job", self)
        self.advance_button.setObjectName("referenceIqaAdvance")
        self.advance_button.setEnabled(False)
        layout.addWidget(self.advance_button)

        self.view_button = QPushButton("View Selected Result", self)
        self.view_button.setObjectName("referenceIqaViewResult")
        self.view_button.setEnabled(False)
        layout.addWidget(self.view_button)

        self.empty_button = QPushButton("Open Empty Analysis Canary", self)
        self.empty_button.setObjectName("referenceIqaOpenEmpty")
        layout.addWidget(self.empty_button)
        layout.addStretch(1)

        self.submit_button.clicked.connect(self.submit_requested.emit)  # type: ignore[attr-defined]
        self.advance_button.clicked.connect(  # type: ignore[attr-defined]
            self.advance_requested.emit
        )
        self.view_button.clicked.connect(  # type: ignore[attr-defined]
            self.view_result_requested.emit
        )
        self.empty_button.clicked.connect(  # type: ignore[attr-defined]
            self.open_empty_requested.emit
        )

    def selected_job_id(self) -> str | None:
        item = self.jobs_list.currentItem()
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return value if isinstance(value, str) else None

    def upsert_job(self, snapshot: IqaJobSnapshot, *, select: bool = False) -> None:
        job_id = snapshot.reference.job_id
        item = next(
            (
                self.jobs_list.item(index)
                for index in range(self.jobs_list.count())
                if self.jobs_list.item(index).data(Qt.ItemDataRole.UserRole) == job_id
            ),
            None,
        )
        if item is None:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, job_id)
            self.jobs_list.addItem(item)
        item.setText(f"{job_id} · {snapshot.state.value}")
        if select:
            self.jobs_list.setCurrentItem(item)

    def present_selected_job(
        self,
        snapshot: IqaJobSnapshot | None,
        paths: tuple[Path, Path] | None = None,
        *,
        synthetic: bool = True,
    ) -> None:
        if snapshot is None:
            self.job_label.setText("No mock job selected.")
            self.advance_button.setEnabled(False)
            self.view_button.setEnabled(False)
            return
        progress = ""
        if snapshot.progress.completed is not None and snapshot.progress.total is not None:
            progress = f" · {snapshot.progress.completed}/{snapshot.progress.total}"
        message = f" · {snapshot.message}" if snapshot.message else ""
        self.job_label.setText(
            f"{snapshot.reference.job_id} · {snapshot.state.value}{progress}{message}"
        )
        self.advance_button.setEnabled(
            snapshot.state in {IqaJobState.QUEUED, IqaJobState.RUNNING}
        )
        self.view_button.setEnabled(snapshot.state is IqaJobState.COMPLETED)
        if paths is not None:
            label = "Synthetic pair" if synthetic else "Current pair"
            self.selection_label.setText(f"{label}: {paths[0].name} ↔ {paths[1].name}")

    def show_error(self, message: str) -> None:
        self.status_label.setText(f"Synthetic IQA error: {message}")


class ReferenceIqaExtension:
    """Optional peer extension; job registry and child window are NOT Base-owned."""

    def __init__(self, provider: FixtureIqaProvider | None = None) -> None:
        self.provider = provider or FixtureIqaProvider(
            Path("synthetic-iqa-reference"), IqaFixtureProfile.MINIMAL
        )
        self._window_ref: ReferenceType[QMainWindow] | None = None
        self._active = False
        self._jobs: dict[str, IqaJobSnapshot] = {}
        self._job_sources: dict[str, tuple[tuple[Path, Path], bool]] = {}
        self._analysis_window: ReferenceIqaAnalysisWindow | None = None
        self.widget: ReferenceIqaWidget | None = None
        self.dock: QDockWidget | None = None
        self.action: QAction | None = None
        self._run_action: QAction | None = None
        self._synthetic_result_action: QAction | None = None
        self._empty_window_action: QAction | None = None

    @property
    def active(self) -> bool:
        return self._active

    @property
    def analysis_window(self) -> ReferenceIqaAnalysisWindow | None:
        return self._analysis_window

    @property
    def jobs(self) -> dict[str, IqaJobSnapshot]:
        return dict(self._jobs)

    def prepare(self, window: QMainWindow) -> None:
        self._window_ref = ref(window)
        self._active = True
        widget = ReferenceIqaWidget()
        widget.submit_requested.connect(self.submit_mock)
        widget.advance_requested.connect(self.advance_mock)
        widget.view_result_requested.connect(self.open_current_result)
        widget.open_empty_requested.connect(self.open_empty_window)
        widget.jobs_list.currentRowChanged.connect(self._refresh_selected_job)
        self.widget = widget

    def install_dock(self, window: QMainWindow) -> None:
        if self.widget is None:
            raise RuntimeError("Reference IQA contribution must be prepared before dock install")
        dock = QDockWidget("IQA Mock Jobs", window)
        dock.setObjectName("referenceIqaWorkspaceDock")
        dock.setWidget(self.widget)
        window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        dock.hide()
        cast(WindowHostAccess, window).register_contributed_dock(dock)
        self.dock = dock

    def install_actions(
        self,
        window: QMainWindow,
        menu_name: str,
        add_action: MenuActionFactory,
    ) -> None:
        del window
        if menu_name == "File":
            self._run_action = add_action("File", "Run IQA (Synthetic)", self.submit_mock, None)
            self._synthetic_result_action = add_action(
                "File",
                "Open Published Synthetic IQA Result (Demo)",
                self.open_reference_result,
                None,
            )
            self._empty_window_action = add_action(
                "File", "Open Empty IQA Analysis Canary", self.open_empty_window, None
            )
            return
        if menu_name != "View":
            return
        if self.dock is None:
            raise RuntimeError("Reference IQA dock must exist before actions are installed")
        action = add_action("View", "Show IQA Mock Jobs", self.toggle_workspace, None)
        action.setCheckable(True)
        self.dock.visibilityChanged.connect(action.setChecked)  # type: ignore[attr-defined]
        self.action = action

    def submit_mock(self) -> None:
        if not self._active or self.widget is None:
            return
        try:
            intent, paths, synthetic = self._submission_intent()
            job = self.provider.submit(intent)
            snapshot = self.provider.get_status(job)
            self._jobs[job.job_id] = snapshot
            self._job_sources[job.job_id] = (paths, synthetic)
            self.widget.upsert_job(snapshot, select=True)
            self._refresh_selected_job()
            self._show_dock()
            self._notify(f"Mock IQA {job.job_id}: queued")
        except IqaProviderError as exc:
            self.widget.show_error(exc.display_message)

    def advance_mock(self) -> None:
        if not self._active or self.widget is None:
            return
        job_id = self.widget.selected_job_id()
        if job_id is None:
            return
        try:
            snapshot = self.provider.advance(IqaJobReference(job_id))
            self._jobs[job_id] = snapshot
            self.widget.upsert_job(snapshot)
            self._refresh_selected_job()
            self._notify(f"Mock IQA {job_id}: {snapshot.state.value}")
        except IqaProviderError as exc:
            self.widget.show_error(exc.display_message)

    def open_current_result(self) -> None:
        if not self._active or self.widget is None:
            return
        job_id = self.widget.selected_job_id()
        if job_id is None or self._jobs[job_id].state is not IqaJobState.COMPLETED:
            return
        try:
            reference = self.provider.get_result_reference(IqaJobReference(job_id))
            source = self.provider.materialize(reference)
            if not source.succeeded or source.source is None:
                self.widget.show_error("Synthetic published result is not available.")
                return
            opened = self.provider.open_result(source.source)
            if not opened.succeeded or opened.result is None:
                self.widget.show_error("Synthetic published result could not be opened.")
                return
            analysis = self._get_analysis_window()
            analysis.present_result(opened.result)
            self._show_analysis_window(analysis)
            self._notify(f"Mock IQA {job_id}: result opened")
        except IqaProviderError as exc:
            self.widget.show_error(exc.display_message)

    def open_reference_result(self) -> None:
        """Publish a deterministic demo job; this does NOT read any file from disk."""
        if not self._active:
            return
        self.submit_mock()
        self.advance_mock()
        self.advance_mock()
        self.open_current_result()

    def open_empty_window(self) -> None:
        if not self._active:
            return
        analysis = self._get_analysis_window()
        analysis.clear_result()
        self._show_analysis_window(analysis)

    def toggle_workspace(self) -> None:
        if not self._active or self.dock is None or self.action is None:
            return
        self.dock.setVisible(self.action.isChecked())
        if self.dock.isVisible():
            self.dock.raise_()

    def shutdown(self) -> None:
        if not self._active:
            return
        self._active = False
        if self.widget is not None:
            self.widget.submit_requested.disconnect(self.submit_mock)
            self.widget.advance_requested.disconnect(self.advance_mock)
            self.widget.view_result_requested.disconnect(self.open_current_result)
            self.widget.open_empty_requested.disconnect(self.open_empty_window)
            self.widget.jobs_list.currentRowChanged.disconnect(self._refresh_selected_job)
        for action, handler in (
            (self._run_action, self.submit_mock),
            (self._synthetic_result_action, self.open_reference_result),
            (self._empty_window_action, self.open_empty_window),
            (self.action, self.toggle_workspace),
        ):
            if action is not None:
                action.triggered.disconnect(handler)
        if self._analysis_window is not None:
            self._analysis_window.close()
            self._analysis_window.deleteLater()
            self._analysis_window = None
        self._jobs.clear()
        self._job_sources.clear()
        self._window_ref = None
        self.widget = None
        self.dock = None
        self.action = None
        self._run_action = None
        self._synthetic_result_action = None
        self._empty_window_action = None

    def _refresh_selected_job(self, _row: int = -1) -> None:
        if not self._active or self.widget is None:
            return
        job_id = self.widget.selected_job_id()
        snapshot = self._jobs.get(job_id) if job_id is not None else None
        source = self._job_sources.get(job_id) if job_id is not None else None
        self.widget.present_selected_job(
            snapshot,
            source[0] if source is not None else None,
            synthetic=source[1] if source is not None else True,
        )
        if snapshot is not None:
            self.widget.status_label.setText(f"Selected job: {snapshot.state.value}")

    def _get_analysis_window(self) -> ReferenceIqaAnalysisWindow:
        if self._analysis_window is None:
            parent = self._window_ref() if self._window_ref is not None else None
            if parent is None:
                raise RuntimeError("Reference IQA contribution has no active host")
            self._analysis_window = ReferenceIqaAnalysisWindow(parent)
        return self._analysis_window

    @staticmethod
    def _show_analysis_window(analysis: ReferenceIqaAnalysisWindow) -> None:
        analysis.show()
        analysis.raise_()

    def _notify(self, message: str) -> None:
        window = self._window_ref() if self._window_ref is not None else None
        if self._active and window is not None:
            window.statusBar().showMessage(message, 5000)

    def _show_dock(self) -> None:
        if self.dock is not None:
            self.dock.show()
            self.dock.raise_()

    def _submission_intent(self) -> tuple[IqaSubmissionIntent, tuple[Path, Path], bool]:
        window = self._window_ref() if self._window_ref is not None else None
        if window is None:
            raise RuntimeError("Reference IQA contribution is not prepared")
        slots = cast(WindowHostAccess, window).current_comparison_source_paths()
        if len(slots) == 2 and all(isinstance(slot, Path) for slot in slots):
            paths: tuple[Path, Path] = cast(tuple[Path, Path], slots)
            synthetic = False
        else:
            paths = (Path("reference-a.synthetic"), Path("reference-b.synthetic"))
            synthetic = True
        variants = (IqaVariant("reference", "Reference"), IqaVariant("candidate", "Candidate"))
        scene = IqaSubmissionScene(
            "reference_scene_0001",
            (
                IqaSubmissionSource(variants[0].variant_id, paths[0]),
                IqaSubmissionSource(variants[1].variant_id, paths[1]),
            ),
        )
        return IqaSubmissionIntent("reference_mock", variants, (scene,)), paths, synthetic
