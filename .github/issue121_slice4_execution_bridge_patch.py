from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, got {count}")
    return text.replace(old, new)


def patch_submission() -> None:
    path = Path("src/pixelscope/ui/iqa_submission.py")
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "from pathlib import Path\nfrom typing import Any\n",
        "from pathlib import Path\nfrom typing import Any\nfrom weakref import ReferenceType, ref\n",
        "weakref import",
    )

    text = replace_once(
        text,
        "from pixelscope.remote.iqa_client import HttpIqaJobClient, IqaJobClient\n",
        "from pixelscope.remote.iqa_client import HttpIqaJobClient, IqaJobClient\n"
        "from pixelscope.remote.iqa_public_contract import (\n"
        "    IqaExecutionPort,\n"
        "    IqaJobReference as PublicIqaJobReference,\n"
        "    IqaJobSnapshot as PublicIqaJobSnapshot,\n"
        "    IqaJobState as PublicIqaJobState,\n"
        "    IqaResultAccessPort,\n"
        "    IqaResultReference as PublicIqaResultReference,\n"
        "    IqaSubmissionIntent,\n"
        "    IqaSubmissionScene,\n"
        "    IqaSubmissionSource,\n"
        "    IqaVariant,\n"
        ")\n",
        "public contract imports",
    )

    text = replace_once(
        text,
        "    state: JobState\n"
        "    completed_scenes: int | None = None\n"
        "    total_scenes: int | None = None\n"
        "    message: str | None = None\n"
        "    result_reference: IqaResultReference | None = None\n"
        "    result_path: Path | None = None\n"
        "    result_resolution_error: str | None = None\n",
        "    state: JobState | PublicIqaJobState\n"
        "    completed_scenes: int | None = None\n"
        "    total_scenes: int | None = None\n"
        "    message: str | None = None\n"
        "    result_reference: IqaResultReference | None = None\n"
        "    result_path: Path | None = None\n"
        "    result_resolution_error: str | None = None\n"
        "    public_result_reference: PublicIqaResultReference | None = None\n"
        "    can_cancel: bool = True\n",
        "RemoteJobRecord public fields",
    )

    marker = "    def set_current_pair_state(\n"
    public_workspace_method = '''    def set_public_provider_state(self) -> None:\n        """Present the provider-neutral Client path without exposing backend settings."""\n\n        self.configuration_label.setText(\n            "Public IQA provider connected · Current Pair submission available."\n        )\n        self.configure_button.setEnabled(False)\n        self.folder_a.setEnabled(False)\n        self.folder_b.setEnabled(False)\n        self.folder_a_browse.setEnabled(False)\n        self.folder_b_browse.setEnabled(False)\n        self.preview_button.setEnabled(False)\n        self.folder_submit.setEnabled(False)\n        self.preview_status.setText(\n            "Folder Pair remains on the legacy P5 path; this provider uses Current Pair."\n        )\n\n'''
    text = replace_once(
        text,
        marker,
        public_workspace_method + marker,
        "public provider workspace method",
    )

    old_selection = '''    def _job_selection_changed(self) -> None:\n        job_id = self._selected_job_id()\n        job = self._jobs.get(job_id) if job_id is not None else None\n        self.cancel_button.setEnabled(job is not None and not job.state.terminal)\n        self.open_button.setEnabled(\n            job is not None\n            and job.state in {JobState.SUCCEEDED, JobState.PARTIAL}\n            and job.result_path is not None\n        )\n        if job is not None and job.result_resolution_error:\n            self.open_button.setToolTip(job.result_resolution_error)\n        else:\n            self.open_button.setToolTip("")\n'''
    new_selection = '''    def _job_selection_changed(self) -> None:\n        job_id = self._selected_job_id()\n        job = self._jobs.get(job_id) if job_id is not None else None\n        self.cancel_button.setEnabled(\n            job is not None and job.can_cancel and not job.state.terminal\n        )\n        legacy_ready = (\n            job is not None\n            and job.state in {JobState.SUCCEEDED, JobState.PARTIAL}\n            and job.result_path is not None\n        )\n        public_ready = (\n            job is not None\n            and job.state is PublicIqaJobState.COMPLETED\n            and job.public_result_reference is not None\n        )\n        self.open_button.setEnabled(legacy_ready or public_ready)\n        if job is not None and job.result_resolution_error:\n            self.open_button.setToolTip(job.result_resolution_error)\n        else:\n            self.open_button.setToolTip("")\n'''
    text = replace_once(text, old_selection, new_selection, "job selection state")

    insert_before = "\n\nclass _RemoteIqaCloseFilter(QObject):\n"
    public_controller = r'''

class PublicIqaExecutionController(QObject):
    """Provider-neutral Current Pair execution owned by the MAIN IQA Client."""

    def __init__(
        self,
        window: Any,
        workspace: RemoteIqaWorkspace,
        result_controller: IqaWorkspaceController,
        *,
        execution_port: IqaExecutionPort,
        result_access_port: IqaResultAccessPort,
    ) -> None:
        super().__init__(window)
        self._window_ref: ReferenceType[Any] | None = ref(window)
        self.workspace = workspace
        self.result_controller = result_controller
        self._execution_port = execution_port
        self._result_access_port = result_access_port
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(REMOTE_WORKER_LIMIT)
        self._workers: dict[str, TaskWorker] = {}
        self._jobs: dict[str, RemoteJobRecord] = {}
        self._job_references: dict[str, PublicIqaJobReference] = {}
        self._polling_jobs: set[str] = set()
        self._result_fetch_jobs: set[str] = set()
        self._generation = 0
        self._active = True
        self._last_pair_identity: tuple[object, ...] | None = None

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll_due)  # type: ignore[attr-defined]
        self._poll_timer.start()
        self._state_timer = QTimer(self)
        self._state_timer.setInterval(400)
        self._state_timer.timeout.connect(  # type: ignore[attr-defined]
            self.refresh_setup_state
        )
        self._state_timer.start()

        workspace.set_public_provider_state()
        workspace.current_submit_requested.connect(self.submit_current_pair)
        workspace.cancel_requested.connect(self.cancel_job)
        workspace.open_result_requested.connect(self.open_result)
        result_controller.outcome_ready.connect(workspace.present_result_outcome)
        self.refresh_setup_state()

    @property
    def window(self) -> Any:
        window = self._window_ref() if self._window_ref is not None else None
        if window is None:
            raise RuntimeError("IQA Client owner was destroyed")
        return window

    def refresh_setup_state(self) -> None:
        if not self._active:
            return
        documents = list(self.window.current_comparison_documents())
        identity = tuple(
            (
                getattr(item, "document_id", None),
                getattr(item, "generation", None),
                getattr(item, "source_path", None),
            )
            for item in documents
        )
        if identity == self._last_pair_identity:
            return
        self._last_pair_identity = identity
        try:
            _intent, paths = _public_current_pair_intent(documents)
        except ValueError as exc:
            self.workspace.set_current_pair_state(
                "Current Pair is not available.",
                False,
                str(exc),
            )
            return
        self.workspace.set_current_pair_state(
            f"Ready · {paths[0].name} / {paths[1].name}",
            True,
            None,
            names=(paths[0].name, paths[1].name),
        )

    @Slot()
    def submit_current_pair(self) -> None:
        if not self._active:
            return
        try:
            intent, _paths = _public_current_pair_intent(
                list(self.window.current_comparison_documents())
            )
        except ValueError as exc:
            self.workspace.show_submission_error(str(exc))
            self.refresh_setup_state()
            return

        worker = TaskWorker(
            self._execution_port.submit,
            intent,
            generation=self._generation,
        )
        worker.signals.succeeded.connect(self._submission_ready)
        worker.signals.failed.connect(self._submission_failed)
        self._track_worker(worker)
        self.workspace.jobs_status.setText("Submitting IQA Current Pair...")
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
            value, PublicIqaJobReference
        ):
            return
        self._job_references[value.job_id] = value
        job = RemoteJobRecord(
            value.job_id,
            "current_pair",
            "",
            PublicIqaJobState.QUEUED,
            message="queued",
            can_cancel=self._execution_port.capabilities.can_cancel,
        )
        self._jobs[value.job_id] = job
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
        if self._accept_generation(generation):
            self.workspace.show_submission_error(_task_error_message(value))

    @Slot()
    def _poll_due(self) -> None:
        if not self._active:
            return
        for job in tuple(self._jobs.values()):
            if job.state.terminal or job.job_id in self._polling_jobs:
                continue
            reference = self._job_references.get(job.job_id)
            if reference is None:
                continue
            self._polling_jobs.add(job.job_id)
            worker = TaskWorker(
                self._execution_port.get_status,
                reference,
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
            or not isinstance(value, PublicIqaJobSnapshot)
        ):
            return
        job = self._jobs.get(document_id)
        if job is None or value.reference.job_id != document_id:
            return
        job.state = value.state
        job.completed_scenes = value.progress.completed
        job.total_scenes = value.progress.total
        job.message = value.message
        self.workspace.upsert_job(job)
        if value.state is PublicIqaJobState.COMPLETED:
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
        if job.public_result_reference is not None or job.job_id in self._result_fetch_jobs:
            return
        reference = self._job_references.get(job.job_id)
        if reference is None:
            return
        self._result_fetch_jobs.add(job.job_id)
        worker = TaskWorker(
            self._execution_port.get_result_reference,
            reference,
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
            or not isinstance(value, PublicIqaResultReference)
        ):
            return
        job = self._jobs.get(document_id)
        if job is None or job.state is not PublicIqaJobState.COMPLETED:
            return
        job.public_result_reference = value
        job.message = "result published"
        self.workspace.upsert_job(job)

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

    @Slot(str)
    def cancel_job(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        reference = self._job_references.get(job_id)
        if not self._active or job is None or reference is None or job.state.terminal:
            return
        if not self._execution_port.capabilities.can_cancel:
            self.workspace.show_job_operation_error(job_id, "provider does not support cancellation")
            return
        worker = TaskWorker(
            self._execution_port.cancel,
            reference,
            document_id=job_id,
            generation=self._generation,
        )
        worker.signals.succeeded.connect(self._status_ready)
        worker.signals.failed.connect(self._status_failed)
        self._track_worker(worker)

    @Slot(str)
    def open_result(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        if job is None or job.state is not PublicIqaJobState.COMPLETED:
            return
        reference = job.public_result_reference
        if reference is None:
            self.workspace.show_job_operation_error(job_id, "result reference is not available")
            return
        self.result_controller.open_result_reference(self._result_access_port, reference)
        self.workspace.tabs.setCurrentWidget(self.workspace.results_page)

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
        self._pool.clear()
        self._window_ref = None
        # Deliberately no provider cancel: submitted jobs are durable across Client close.

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


def install_public_iqa(
    window: Any,
    *,
    execution_port: IqaExecutionPort,
    result_access_port: IqaResultAccessPort,
) -> PublicIqaExecutionController:
    """Install the provider-neutral Client shell without any Enterprise implementation knowledge."""

    existing_results = window.iqa_workspace
    shell = RemoteIqaWorkspace(existing_results)
    window.iqa_dock.setWidget(shell)
    controller = PublicIqaExecutionController(
        window,
        shell,
        window.iqa_controller,
        execution_port=execution_port,
        result_access_port=result_access_port,
    )
    window.remote_iqa_workspace = shell
    window.remote_iqa_controller = controller
    return controller


def _public_current_pair_intent(
    documents: list[Any],
) -> tuple[IqaSubmissionIntent, tuple[Path, Path]]:
    if len(documents) != 2:
        raise ValueError("Current Comparison Page must contain exactly two images")
    paths: list[Path] = []
    for document in documents:
        path = getattr(document, "source_path", None)
        if not isinstance(path, Path):
            raise ValueError("Current Pair requires two native source paths")
        paths.append(path)
    variants = (IqaVariant("A", "A"), IqaVariant("B", "B"))
    sources = tuple(
        IqaSubmissionSource(variant.variant_id, path)
        for variant, path in zip(variants, paths, strict=True)
    )
    intent = IqaSubmissionIntent(
        "current_pair",
        variants,
        (IqaSubmissionScene("scene_000000", sources),),
    )
    return intent, (paths[0], paths[1])
'''
    text = replace_once(
        text,
        insert_before,
        public_controller + insert_before,
        "public execution controller",
    )

    path.write_text(text, encoding="utf-8")


def patch_installer() -> None:
    path = Path("src/pixelscope/ui/iqa_client_install.py")
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "from pixelscope.ui.iqa_submission_lifecycle import install_remote_iqa_submission_lifecycle\n"
        "from pixelscope.ui.iqa_workspace import IqaWorkspaceController, IqaWorkspaceWidget\n",
        "from pixelscope.ui.iqa_submission import (\n"
        "    PublicIqaExecutionController,\n"
        "    install_public_iqa,\n"
        ")\n"
        "from pixelscope.ui.iqa_submission_lifecycle import install_remote_iqa_submission_lifecycle\n"
        "from pixelscope.ui.iqa_workspace import IqaWorkspaceController, IqaWorkspaceWidget\n",
        "installer public execution imports",
    )

    text = replace_once(
        text,
        "        self.controller: IqaWorkspaceController | None = None\n"
        "        self.dock: QDockWidget | None = None\n",
        "        self.controller: IqaWorkspaceController | None = None\n"
        "        self.execution_controller: PublicIqaExecutionController | None = None\n"
        "        self.dock: QDockWidget | None = None\n",
        "installer execution controller field",
    )

    text = replace_once(
        text,
        "        if not self._install_legacy_runtime:\n"
        "            return\n"
        "        result_pool = self.result_pool\n",
        "        if not self._install_legacy_runtime:\n"
        "            self.execution_controller = install_public_iqa(\n"
        "                window,\n"
        "                execution_port=self.execution_port,\n"
        "                result_access_port=self.result_access_port,\n"
        "            )\n"
        "            return\n"
        "        result_pool = self.result_pool\n",
        "installer public runtime branch",
    )

    text = replace_once(
        text,
        "    def shutdown(self) -> None:\n"
        "        if self.controller is not None:\n"
        "            self.controller.shutdown()\n"
        "        self._window_ref = None\n",
        "    def shutdown(self) -> None:\n"
        "        if self.execution_controller is not None:\n"
        "            self.execution_controller.shutdown()\n"
        "        if self.controller is not None:\n"
        "            self.controller.shutdown()\n"
        "        self._window_ref = None\n",
        "installer public shutdown",
    )

    path.write_text(text, encoding="utf-8")


def patch_test() -> None:
    path = Path("tests/ui/test_issue121_iqa_composition_seam.py")
    text = path.read_text(encoding="utf-8")

    old_import = '''from pixelscope.remote.iqa_public_contract import (\n    IqaSubmissionIntent,\n    IqaSubmissionScene,\n    IqaSubmissionSource,\n    IqaVariant,\n)\n'''
    text = replace_once(
        text,
        old_import,
        "from pixelscope.remote.iqa_public_contract import IqaJobReference\n",
        "test public contract import",
    )

    start = text.index("def test_public_provider_injection_drives_client_workspace(")
    end = text.index("\n\ndef test_iqa_runtime_installer_preserves_characterized_p5_order", start)
    replacement = r'''def test_public_provider_injection_drives_client_execution_workflow(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    provider = FixtureIqaProvider(tmp_path, IqaFixtureProfile.MINIMAL)
    installer = IqaClientInstaller.from_ports(provider, provider)
    window = MainWindow(window_contributions=(installer,))
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    path_a = tmp_path / "a.png"
    path_b = tmp_path / "b.png"
    path_a.write_bytes(b"fixture-a")
    path_b.write_bytes(b"fixture-b")
    documents = (
        SimpleNamespace(source_path=path_a, document_id="a", generation=1),
        SimpleNamespace(source_path=path_b, document_id="b", generation=1),
    )
    monkeypatch.setattr(window, "current_comparison_documents", lambda: list(documents))

    installer.install_runtime(window)
    shell = window.remote_iqa_workspace
    execution_controller = window.remote_iqa_controller

    assert installer.execution_controller is execution_controller
    assert installer.execution_port is provider
    assert installer.result_access_port is provider
    assert shell.current_submit.isEnabled()

    shell.current_submit.click()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: shell.jobs_tree.topLevelItemCount() == 1,
        timeout=5000,
    )
    item = shell.jobs_tree.topLevelItem(0)
    assert item.text(2) == "queued"

    job_reference = IqaJobReference("fixture-job-0001")
    provider.advance(job_reference)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: item.text(2) == "running",
        timeout=5000,
    )
    provider.advance(job_reference)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: item.text(2) == "completed" and shell.open_button.isEnabled(),
        timeout=5000,
    )

    shell.open_button.click()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: installer.workspace is not None and installer.workspace.model is not None,
        timeout=5000,
    )

    assert installer.workspace is not None
    assert installer.workspace.model is not None
    assert installer.workspace.model.result.result_id == "fixture-minimal"

    window.close()


def test_public_provider_injection_uses_client_cancel_action(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    provider = FixtureIqaProvider(tmp_path, IqaFixtureProfile.MINIMAL)
    installer = IqaClientInstaller.from_ports(provider, provider)
    window = MainWindow(window_contributions=(installer,))
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    path_a = tmp_path / "a.png"
    path_b = tmp_path / "b.png"
    documents = (
        SimpleNamespace(source_path=path_a, document_id="a", generation=1),
        SimpleNamespace(source_path=path_b, document_id="b", generation=1),
    )
    monkeypatch.setattr(window, "current_comparison_documents", lambda: list(documents))

    installer.install_runtime(window)
    shell = window.remote_iqa_workspace
    shell.current_submit.click()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: shell.jobs_tree.topLevelItemCount() == 1 and shell.cancel_button.isEnabled(),
        timeout=5000,
    )

    item = shell.jobs_tree.topLevelItem(0)
    shell.cancel_button.click()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: item.text(2) == "cancelled",
        timeout=5000,
    )
    assert not shell.cancel_button.isEnabled()
    assert not shell.open_button.isEnabled()

    window.close()
'''
    text = text[:start] + replacement + text[end:]

    path.write_text(text, encoding="utf-8")


def main() -> None:
    patch_submission()
    patch_installer()
    patch_test()


if __name__ == "__main__":
    main()
