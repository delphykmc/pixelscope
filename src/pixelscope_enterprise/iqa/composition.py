"""Public-safe, explicit IQA contribution for a PRIVATE SUB composition root.

This is not a service adapter or a plugin registry. PRIVATE SUB supplies its
own authorized job starter, reader/writer and settings factory; Handoff owns
only the presentation lifecycle and job/status-to-window routing.
"""

from __future__ import annotations

import weakref
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pixelscope.app.window_contribution import MenuActionFactory
from pixelscope_enterprise.iqa.analysis_model import AnalysisResult
from pixelscope_enterprise.iqa.analysis_window import (
    AnalysisWindow,
    AnalysisWindowManager,
    IqaSettingsFactory,
    ResultLoader,
    ResultSaver,
)

IqaJobStarter = Callable[[tuple[Path | None, ...]], None]
JOB_STATUSES = frozenset({"queued", "running", "completed", "failed", "cancelled"})


@dataclass(frozen=True)
class IqaJobSnapshot:
    """Nonsecret UI state; computation, cancellation and auth remain SUB-owned."""

    job_id: str
    label: str
    status: str
    result: AnalysisResult | None = None

    def __post_init__(self) -> None:
        if not self.job_id or not self.label or self.status not in JOB_STATUSES:
            raise ValueError("invalid IQA job snapshot")
        if self.result is not None and self.status != "completed":
            raise ValueError("only completed IQA jobs may carry results")


class IqaWindowContribution:
    """Explicit WindowContribution + RuntimeWindowContribution implementation.

    Holds one AnalysisWindowManager. The host owns only the job-list dock and
    actions. Publication of status/results never auto-opens a new window;
    users choose 'View selected result' / 'Open IQA Analysis'.
    """

    def __init__(
        self,
        *,
        settings_factory: IqaSettingsFactory | None = None,
        load: ResultLoader | None = None,
        save: ResultSaver | None = None,
        start_job: IqaJobStarter | None = None,
    ) -> None:
        self.manager = AnalysisWindowManager(
            settings_factory=settings_factory, load=load, save=save
        )
        self._start_job = start_job
        self._host_ref: weakref.ReferenceType[QMainWindow] | None = None
        self._records: dict[str, IqaJobSnapshot] = {}
        self._latest_job_id: str | None = None
        self.jobs_dock: QDockWidget | None = None
        self.jobs_list: QListWidget | None = None
        self.view_selected_button: QPushButton | None = None
        self.jobs_status_button: QPushButton | None = None
        self._jobs_view_action: QAction | None = None
        self._closed = False
        self._runtime_installed = False

    def prepare(self, window: QMainWindow) -> None:
        if self._closed or self._host_ref is not None:
            raise RuntimeError("IQA contribution must be prepared once")
        self._host_ref = weakref.ref(window)
        dock = QDockWidget("IQA Jobs", window)
        dock.setObjectName("enterpriseIqaJobsDock")
        dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        frame = QWidget(dock)
        layout = QVBoxLayout(frame)
        layout.addWidget(QLabel("IQA analysis requests", frame))
        self.jobs_list = QListWidget(frame)
        self.jobs_list.setObjectName("enterpriseIqaJobsList")
        self.jobs_list.currentItemChanged.connect(  # type: ignore[attr-defined]
            self._selection_changed
        )
        self.jobs_list.itemDoubleClicked.connect(  # type: ignore[attr-defined]
            self._open_selected_result
        )
        layout.addWidget(self.jobs_list, 1)
        buttons = QHBoxLayout()
        self.view_selected_button = QPushButton("View selected result", frame)
        self.view_selected_button.setEnabled(False)
        self.view_selected_button.clicked.connect(  # type: ignore[attr-defined]
            self.open_selected_result
        )
        buttons.addWidget(self.view_selected_button)
        layout.addLayout(buttons)
        dock.setWidget(frame)
        self.jobs_dock = dock
        dock.visibilityChanged.connect(  # type: ignore[attr-defined]
            self._jobs_dock_visibility_changed
        )

    def install_dock(self, window: QMainWindow) -> None:
        if self.jobs_dock is None or self._host() is not window:
            raise RuntimeError("IQA contribution must prepare the same host first")
        window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.jobs_dock)
        register = getattr(window, "register_contributed_dock", None)
        if callable(register):
            register(self.jobs_dock)
        self.jobs_dock.hide()

    def install_actions(
        self,
        window: QMainWindow,
        menu_name: str,
        add_action: MenuActionFactory,
    ) -> None:
        if self._closed or self._host() is not window:
            raise RuntimeError("IQA contribution host unavailable")
        if menu_name == "IQA":
            add_action("IQA", "Open IQA Analysis", self.open_analysis, None)
            if self._start_job is not None:
                add_action("IQA", "Run IQA", self.request_analysis, None)
        elif menu_name == "View":
            action = add_action("View", "Show IQA Jobs", self.toggle_jobs, None)
            action.setCheckable(True)
            action.setChecked(self.jobs_dock is not None and not self.jobs_dock.isHidden())
            self._jobs_view_action = action

    def install_runtime(self, window: QMainWindow) -> None:
        """Composition-root phase; intentionally does not start private workers."""
        if self._host() is not window or self._closed:
            raise RuntimeError("IQA runtime host unavailable")
        self._runtime_installed = True
        # A persistent, nonmodal host status affordance remains visible even
        # while the jobs dock is closed. No analysis window opens implicitly.
        button = QPushButton("IQA Jobs", window.statusBar())
        button.setObjectName("enterpriseIqaJobsStatusButton")
        button.setToolTip("Open IQA Jobs to review requests and completed results")
        button.clicked.connect(self.show_jobs)  # type: ignore[attr-defined]
        window.statusBar().addPermanentWidget(button)
        button.hide()
        self.jobs_status_button = button
        if self._records:
            self._update_host_status()

    def _host(self) -> QMainWindow | None:
        return self._host_ref() if self._host_ref is not None else None

    def show_jobs(self) -> None:
        if self._closed or self.jobs_dock is None:
            raise RuntimeError("IQA contribution not available")
        self.jobs_dock.show()
        self.jobs_dock.raise_()

    def toggle_jobs(self, checked: bool = False) -> None:
        """Checkable View action; dock visibility drives the checked state."""
        if self._closed or self.jobs_dock is None:
            raise RuntimeError("IQA contribution not available")
        self.jobs_dock.setVisible(checked)

    def _jobs_dock_visibility_changed(self, visible: bool) -> None:
        if self._jobs_view_action is not None:
            self._jobs_view_action.setChecked(visible)

    def _update_host_status(self) -> None:
        """Visible MAIN-side progress/completion cue independent of dock state."""
        button = self.jobs_status_button
        if button is None or not self._records:
            return
        if self._latest_job_id is None:
            return
        latest = self._records[self._latest_job_id]
        button.setText(f"IQA: {latest.label} — {latest.status} · View jobs")
        button.setAccessibleName(f"IQA job {latest.label}, {latest.status}; open the IQA jobs list")
        button.show()

    def request_analysis(self) -> None:
        """Pass selected source paths to the authorized, SUB-owned job starter."""
        if self._closed or self._start_job is None:
            raise RuntimeError("IQA job starter not installed")
        host = self._host()
        if host is None:
            raise RuntimeError("IQA host no longer exists")
        paths = getattr(host, "current_comparison_source_paths", None)
        if not callable(paths):
            raise RuntimeError("IQA host has no public source-path contract")
        self._start_job(tuple(paths()))

    def publish_job(self, snapshot: IqaJobSnapshot) -> None:
        """Update presentation only; never own the worker or open results."""
        if self._closed or self.jobs_list is None:
            raise RuntimeError("IQA contribution not available")
        app = QApplication.instance()
        if app is None or QThread.currentThread() != app.thread():
            raise RuntimeError("IQA job updates must be dispatched onto the Qt GUI thread")
        self._records[snapshot.job_id] = snapshot
        self._latest_job_id = snapshot.job_id
        # Store stable IDs in UserRole; display labels may change.
        item = next(
            (
                entry
                for row in range(self.jobs_list.count())
                if (entry := self.jobs_list.item(row)).data(Qt.ItemDataRole.UserRole)
                == snapshot.job_id
            ),
            None,
        )
        if item is None:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, snapshot.job_id)
            self.jobs_list.addItem(item)
        item.setText(f"{snapshot.label} — {snapshot.status}")
        self._update_host_status()
        if self.jobs_list.currentItem() is item:
            self._selection_changed()

    def _selected_result(self) -> AnalysisResult | None:
        if self.jobs_list is None:
            return None
        item = self.jobs_list.currentItem()
        if item is None:
            return None
        snapshot = self._records.get(str(item.data(Qt.ItemDataRole.UserRole)))
        return snapshot.result if snapshot is not None else None

    def _selection_changed(self, *_args: object) -> None:
        if self.view_selected_button is not None:
            self.view_selected_button.setEnabled(self._selected_result() is not None)

    def open_selected_result(self) -> AnalysisWindow | None:
        result = self._selected_result()
        if result is None:
            return None
        return self.manager.show(result)

    def _open_selected_result(self, *_args: object) -> None:
        self.open_selected_result()

    def open_analysis(self) -> AnalysisWindow:
        if self._closed:
            raise RuntimeError("IQA contribution shut down")
        return self.manager.show()

    def shutdown(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.manager.shutdown()
        if self.jobs_status_button is not None:
            self.jobs_status_button.hide()
        self._records.clear()
        self._latest_job_id = None
        self._start_job = None
        self._host_ref = None
