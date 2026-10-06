"""Company-neutral reference/mock IQA extension.

The reference extension is a peer consumer of Base host facilities and the public IQA
ports. It intentionally does not import the legacy P5 Client installer, transport,
storage, settings, or Enterprise implementation.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast
from weakref import ReferenceType, ref

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QHBoxLayout,
    QLabel,
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


class ReferenceIqaWidget(QWidget):
    """Small IQA UX reference that exercises public job/result/reference/Scene semantics."""

    submit_requested = Signal()
    advance_requested = Signal()
    open_result_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("referenceIqaWorkspace")
        self._result: IqaResult | None = None

        layout = QVBoxLayout(self)
        self.status_label = QLabel("Reference IQA ready.", self)
        self.status_label.setObjectName("referenceIqaStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.selection_label = QLabel(
            "Run Mock IQA uses the current comparison pair when available.",
            self,
        )
        self.selection_label.setObjectName("referenceIqaSelection")
        self.selection_label.setWordWrap(True)
        layout.addWidget(self.selection_label)

        job_row = QHBoxLayout()
        self.submit_button = QPushButton("Run Mock IQA", self)
        self.submit_button.setObjectName("referenceIqaSubmit")
        self.advance_button = QPushButton("Advance Mock Job", self)
        self.advance_button.setObjectName("referenceIqaAdvance")
        self.open_button = QPushButton("Open Result", self)
        self.open_button.setObjectName("referenceIqaOpenResult")
        self.advance_button.setEnabled(False)
        self.open_button.setEnabled(False)
        job_row.addWidget(self.submit_button)
        job_row.addWidget(self.advance_button)
        job_row.addWidget(self.open_button)
        layout.addLayout(job_row)

        self.job_label = QLabel("No mock job.", self)
        self.job_label.setObjectName("referenceIqaJob")
        layout.addWidget(self.job_label)

        result_row = QHBoxLayout()
        result_row.addWidget(QLabel("Reference", self))
        self.reference_combo = QComboBox(self)
        self.reference_combo.setObjectName("referenceIqaReference")
        result_row.addWidget(self.reference_combo, 1)
        result_row.addWidget(QLabel("Scene", self))
        self.scene_combo = QComboBox(self)
        self.scene_combo.setObjectName("referenceIqaScene")
        result_row.addWidget(self.scene_combo, 1)
        layout.addLayout(result_row)

        self.result_label = QLabel("No result open.", self)
        self.result_label.setObjectName("referenceIqaResult")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)

        self.detail_label = QLabel("", self)
        self.detail_label.setObjectName("referenceIqaDetail")
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.detail_label)
        layout.addStretch(1)

        self.reference_combo.setEnabled(False)
        self.scene_combo.setEnabled(False)
        self.submit_button.clicked.connect(  # type: ignore[attr-defined]
            self.submit_requested.emit
        )
        self.advance_button.clicked.connect(  # type: ignore[attr-defined]
            self.advance_requested.emit
        )
        self.open_button.clicked.connect(  # type: ignore[attr-defined]
            self.open_result_requested.emit
        )
        self.reference_combo.currentIndexChanged.connect(  # type: ignore[attr-defined]
            self._selection_changed
        )
        self.scene_combo.currentIndexChanged.connect(  # type: ignore[attr-defined]
            self._selection_changed
        )

    @property
    def result(self) -> IqaResult | None:
        return self._result

    def present_submission_sources(self, paths: tuple[Path, Path], *, synthetic: bool) -> None:
        names = f"{paths[0].name} ↔ {paths[1].name}"
        prefix = "Synthetic pair" if synthetic else "Current pair"
        self.selection_label.setText(f"{prefix}: {names}")

    def present_job(self, snapshot: IqaJobSnapshot) -> None:
        progress = ""
        if snapshot.progress.completed is not None and snapshot.progress.total is not None:
            progress = f" · {snapshot.progress.completed}/{snapshot.progress.total}"
        message = f" · {snapshot.message}" if snapshot.message else ""
        self.job_label.setText(
            f"{snapshot.reference.job_id} · {snapshot.state.value}{progress}{message}"
        )
        self.advance_button.setEnabled(snapshot.state in {IqaJobState.QUEUED, IqaJobState.RUNNING})
        self.open_button.setEnabled(snapshot.state is IqaJobState.COMPLETED)
        self.submit_button.setEnabled(snapshot.state.terminal)
        self.status_label.setText(f"Mock job: {snapshot.state.value}")

    def present_result(self, result: IqaResult) -> None:
        self._result = result
        self.reference_combo.blockSignals(True)
        self.scene_combo.blockSignals(True)
        self.reference_combo.clear()
        self.scene_combo.clear()
        for variant in result.variants:
            self.reference_combo.addItem(variant.label, variant.variant_id)
        for scene in result.scenes:
            self.scene_combo.addItem(scene.scene_id, scene.scene_id)
        self.reference_combo.blockSignals(False)
        self.scene_combo.blockSignals(False)
        self.reference_combo.setEnabled(bool(result.variants))
        self.scene_combo.setEnabled(bool(result.scenes))
        self.result_label.setText(
            f"{result.dataset.label} · {len(result.variants)} variants · "
            f"{len(result.scenes)} Scenes · {result.completeness.value}"
        )
        self.status_label.setText("Reference result open.")
        self._selection_changed()

    def show_error(self, message: str) -> None:
        self.status_label.setText(f"Reference IQA error: {message}")

    def _selection_changed(self) -> None:
        result = self._result
        variant_id = self.reference_combo.currentData()
        scene_id = self.scene_combo.currentData()
        if result is None or not isinstance(variant_id, str) or not isinstance(scene_id, str):
            self.detail_label.setText("")
            return

        attribute = result.attributes[0]
        summary = result.dataset_summary(variant_id, attribute.attribute_id).pooled
        value = "—" if summary.weighted_mean is None else f"{summary.weighted_mean:.4f}"
        scene = result.scene(scene_id)
        source = scene.source_for_variant(variant_id).source
        spatial = result.load_spatial(scene_id)
        self.detail_label.setText(
            f"{attribute.name}: {value} · Source: {source.relative_path} · "
            f"Spatial: {spatial.availability.value}"
        )


class ReferenceIqaExtension:
    """Explicit MAIN-owned reference contribution using only public host/contracts."""

    def __init__(
        self,
        provider: FixtureIqaProvider | None = None,
    ) -> None:
        self.provider = provider or FixtureIqaProvider(
            Path("synthetic-iqa-reference"),
            IqaFixtureProfile.MINIMAL,
        )
        self._window_ref: ReferenceType[QMainWindow] | None = None
        self._active = False
        self._current_job: IqaJobReference | None = None
        self.widget: ReferenceIqaWidget | None = None
        self.dock: QDockWidget | None = None
        self.action: QAction | None = None

    @property
    def active(self) -> bool:
        return self._active

    def prepare(self, window: QMainWindow) -> None:
        self._window_ref = ref(window)
        self._active = True
        widget = ReferenceIqaWidget()
        widget.submit_requested.connect(self.submit_mock)
        widget.advance_requested.connect(self.advance_mock)
        widget.open_result_requested.connect(self.open_current_result)
        self.widget = widget

    def install_dock(self, window: QMainWindow) -> None:
        if self.widget is None:
            raise RuntimeError("Reference IQA contribution must be prepared before dock install")
        dock = QDockWidget("IQA Reference", window)
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
            add_action("File", "Open IQA Reference Result...", self.open_reference_result, None)
            return
        if menu_name != "View":
            return
        if self.dock is None:
            raise RuntimeError("Reference IQA dock must exist before actions are installed")
        action = add_action("View", "Show IQA Reference", self.toggle_workspace, None)
        action.setCheckable(True)
        self.dock.visibilityChanged.connect(action.setChecked)  # type: ignore[attr-defined]
        self.action = action

    def submit_mock(self) -> None:
        if not self._active or self.widget is None:
            return
        try:
            intent, paths, synthetic = self._submission_intent()
            self.widget.present_submission_sources(paths, synthetic=synthetic)
            self._current_job = self.provider.submit(intent)
            self.widget.present_job(self.provider.get_status(self._current_job))
        except IqaProviderError as exc:
            self.widget.show_error(exc.display_message)

    def advance_mock(self) -> None:
        if not self._active or self.widget is None or self._current_job is None:
            return
        try:
            self.widget.present_job(self.provider.advance(self._current_job))
        except IqaProviderError as exc:
            self.widget.show_error(exc.display_message)

    def open_current_result(self) -> None:
        if not self._active or self.widget is None or self._current_job is None:
            return
        try:
            reference = self.provider.get_result_reference(self._current_job)
            source = self.provider.materialize(reference)
            if not source.succeeded or source.source is None:
                self.widget.show_error("Synthetic result is not available.")
                return
            opened = self.provider.open_result(source.source)
            if not opened.succeeded or opened.result is None:
                self.widget.show_error("Synthetic result could not be opened.")
                return
            self._show_dock()
            self.widget.present_result(opened.result)
        except IqaProviderError as exc:
            self.widget.show_error(exc.display_message)

    def open_reference_result(self) -> None:
        """Open a deterministic published mock result through the public result ports."""

        if not self._active or self.widget is None:
            return
        intent, paths, synthetic = self._submission_intent()
        self.widget.present_submission_sources(paths, synthetic=synthetic)
        job = self.provider.submit(intent)
        self.provider.advance(job)
        self.provider.advance(job)
        self._current_job = job
        self.widget.present_job(self.provider.get_status(job))
        self.open_current_result()

    def toggle_workspace(self) -> None:
        if self.dock is None or self.action is None:
            return
        visible = self.action.isChecked()
        self.dock.setVisible(visible)
        if visible:
            self.dock.raise_()

    def shutdown(self) -> None:
        if not self._active:
            return
        self._active = False
        if self.widget is not None:
            self.widget.submit_requested.disconnect(self.submit_mock)
            self.widget.advance_requested.disconnect(self.advance_mock)
            self.widget.open_result_requested.disconnect(self.open_current_result)
        self._window_ref = None

    def _show_dock(self) -> None:
        if self.dock is not None:
            self.dock.show()
            self.dock.raise_()

    def _submission_intent(self) -> tuple[IqaSubmissionIntent, tuple[Path, Path], bool]:
        window = self._window_ref() if self._window_ref is not None else None
        if window is None:
            raise RuntimeError("Reference IQA contribution is not prepared")
        selected = cast(WindowHostAccess, window).current_comparison_source_paths()
        synthetic = len(selected) < 2
        paths: tuple[Path, Path]
        if synthetic:
            paths = (Path("reference-a.synthetic"), Path("reference-b.synthetic"))
        else:
            paths = (selected[0], selected[1])
        variants = (IqaVariant("reference", "Reference"), IqaVariant("candidate", "Candidate"))
        scene = IqaSubmissionScene(
            "reference_scene_0001",
            (
                IqaSubmissionSource(variants[0].variant_id, paths[0]),
                IqaSubmissionSource(variants[1].variant_id, paths[1]),
            ),
        )
        return IqaSubmissionIntent("reference_mock", variants, (scene,)), paths, synthetic
