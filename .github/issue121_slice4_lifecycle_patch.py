from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, got {count}")
    return text.replace(old, new)


def patch_client_install() -> None:
    path = Path("src/pixelscope/ui/iqa_client_install.py")
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from pixelscope.workers.iqa_thread_pool import remote_iqa_thread_pool\n",
        "from pixelscope.workers.iqa_thread_pool import remote_iqa_thread_pool\n"
        "from pixelscope.workers.thread_pools import analysis_thread_pool\n",
        "analysis pool import",
    )
    marker = "    @property\n    def execution_port(self) -> IqaExecutionPort:\n"
    helper = '''    def _resolve_result_pool(self) -> QThreadPool | None:\n        """Preserve the characterized result/file resource domain for public providers."""\n\n        if self._result_pool is not None or self._install_legacy_runtime:\n            return self._result_pool\n        # Slice 1 froze local analysis registration before the application-owned\n        # Remote IQA result/file pool. Keep that ordering even for a SUB launcher\n        # that composes the Client directly through ``from_ports()``.\n        analysis_thread_pool()\n        self._result_pool = remote_iqa_thread_pool()\n        return self._result_pool\n\n'''
    text = replace_once(text, marker, helper + marker, "result pool resolver")
    text = replace_once(
        text,
        "        workspace = IqaWorkspaceWidget()\n"
        "        controller = IqaWorkspaceController(workspace, window, pool=self._result_pool)\n",
        "        workspace = IqaWorkspaceWidget()\n"
        "        result_pool = self._resolve_result_pool()\n"
        "        controller = IqaWorkspaceController(workspace, window, pool=result_pool)\n",
        "prepare result pool",
    )
    path.write_text(text, encoding="utf-8")


def patch_submission() -> None:
    path = Path("src/pixelscope/ui/iqa_submission.py")
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "        job = self._jobs.get(document_id)\n"
        "        if job is None or value.reference.job_id != document_id:\n"
        "            return\n"
        "        job.state = value.state\n",
        "        job = self._jobs.get(document_id)\n"
        "        # Match the characterized P5 lifecycle: the first terminal state is\n"
        "        # sticky. A late poll/cancel callback must never reopen a terminal job.\n"
        "        if (\n"
        "            job is None\n"
        "            or job.state.terminal\n"
        "            or value.reference.job_id != document_id\n"
        "        ):\n"
        "            return\n"
        "        job.state = value.state\n",
        "public terminal stickiness",
    )
    path.write_text(text, encoding="utf-8")


def patch_composition_tests() -> None:
    path = Path("tests/ui/test_issue121_iqa_composition_seam.py")
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from pathlib import Path\nfrom types import SimpleNamespace\n",
        "from pathlib import Path\nfrom threading import Event, Lock\nfrom types import SimpleNamespace\n",
        "threading imports",
    )
    text = replace_once(
        text,
        "import pytest\nfrom PySide6.QtWidgets import QDockWidget\n",
        "import pytest\nfrom PySide6.QtCore import QThreadPool\nfrom PySide6.QtWidgets import QDockWidget\n",
        "QThreadPool import",
    )
    text = replace_once(
        text,
        "from pixelscope.remote.iqa_public_contract import IqaJobReference\n",
        "from pixelscope.remote.iqa_public_contract import (\n"
        "    IqaJobReference,\n"
        "    IqaJobSnapshot,\n"
        "    IqaJobState,\n"
        ")\n",
        "public job imports",
    )
    marker = 'pytestmark = pytest.mark.usefixtures("isolated_qsettings")\n\n\n'
    helper = '''pytestmark = pytest.mark.usefixtures("isolated_qsettings")\n\n\nclass _DelayedStatusFixtureProvider(FixtureIqaProvider):\n    """Capture one status snapshot and release it later to exercise callback races."""\n\n    def __init__(self, root: Path) -> None:\n        super().__init__(root, IqaFixtureProfile.MINIMAL)\n        self.status_entered = Event()\n        self.release_status = Event()\n        self._delay_guard = Lock()\n        self._delay_next_status = False\n        self.cancel_calls = 0\n\n    def delay_next_status(self) -> None:\n        self.status_entered.clear()\n        self.release_status.clear()\n        with self._delay_guard:\n            self._delay_next_status = True\n\n    def get_status(self, reference: IqaJobReference) -> IqaJobSnapshot:\n        snapshot = super().get_status(reference)\n        with self._delay_guard:\n            should_delay = self._delay_next_status\n            if should_delay:\n                self._delay_next_status = False\n        if should_delay:\n            self.status_entered.set()\n            if not self.release_status.wait(timeout=5.0):\n                raise TimeoutError("delayed fixture status was not released")\n        return snapshot\n\n    def cancel(self, reference: IqaJobReference) -> IqaJobSnapshot:\n        with self._delay_guard:\n            self.cancel_calls += 1\n        return super().cancel(reference)\n\n\n'''
    text = replace_once(text, marker, helper, "delayed provider helper")

    marker = "def test_public_provider_injection_drives_client_execution_workflow(\n"
    pool_test = '''def test_public_provider_default_result_pool_preserves_resource_domain(\n    qtbot: object,\n    monkeypatch: pytest.MonkeyPatch,\n    tmp_path: Path,\n) -> None:\n    provider = FixtureIqaProvider(tmp_path, IqaFixtureProfile.MINIMAL)\n    analysis_pool = QThreadPool()\n    result_pool = QThreadPool()\n    result_pool.setMaxThreadCount(2)\n    events: list[str] = []\n\n    monkeypatch.setattr(\n        client_install,\n        "analysis_thread_pool",\n        lambda: events.append("analysis") or analysis_pool,\n    )\n    monkeypatch.setattr(\n        client_install,\n        "remote_iqa_thread_pool",\n        lambda: events.append("remote_result") or result_pool,\n    )\n\n    installer = IqaClientInstaller.from_ports(provider, provider)\n    window = MainWindow(window_contributions=(installer,))\n    qtbot.addWidget(window)  # type: ignore[attr-defined]\n\n    assert events == ["analysis", "remote_result"]\n    assert installer.result_pool is result_pool\n    assert installer.result_pool is not analysis_pool\n\n    installer.install_runtime(window)\n    assert installer.execution_controller is not None\n    assert installer.execution_controller._pool is not result_pool\n    assert installer.execution_controller._pool.maxThreadCount() == 2\n\n    window.close()\n\n\n'''
    text = replace_once(text, marker, pool_test + marker, "public result pool test")

    marker = "def test_iqa_runtime_installer_preserves_characterized_p5_order(\n"
    lifecycle_tests = '''def test_public_terminal_state_is_sticky_across_poll_cancel_race(\n    qtbot: object,\n    monkeypatch: pytest.MonkeyPatch,\n    tmp_path: Path,\n) -> None:\n    provider = _DelayedStatusFixtureProvider(tmp_path)\n    installer = IqaClientInstaller.from_ports(provider, provider)\n    window = MainWindow(window_contributions=(installer,))\n    qtbot.addWidget(window)  # type: ignore[attr-defined]\n    documents = (\n        SimpleNamespace(source_path=tmp_path / "a.png", document_id="a", generation=1),\n        SimpleNamespace(source_path=tmp_path / "b.png", document_id="b", generation=1),\n    )\n    monkeypatch.setattr(window, "current_comparison_documents", lambda: list(documents))\n\n    installer.install_runtime(window)\n    shell = window.remote_iqa_workspace\n    controller = window.remote_iqa_controller\n    shell.current_submit.click()\n    qtbot.waitUntil(  # type: ignore[attr-defined]\n        lambda: shell.jobs_tree.topLevelItemCount() == 1,\n        timeout=5000,\n    )\n    controller._poll_timer.stop()\n    reference = IqaJobReference("fixture-job-0001")\n    provider.advance(reference)\n    qtbot.waitUntil(  # type: ignore[attr-defined]\n        lambda: reference.job_id not in controller._polling_jobs,\n        timeout=5000,\n    )\n\n    provider.delay_next_status()\n    controller._poll_due()\n    assert provider.status_entered.wait(timeout=5.0)\n\n    item = shell.jobs_tree.topLevelItem(0)\n    shell.cancel_button.click()\n    qtbot.waitUntil(  # type: ignore[attr-defined]\n        lambda: item.text(2) == "cancelled",\n        timeout=5000,\n    )\n    assert controller._jobs[reference.job_id].state is IqaJobState.CANCELLED\n\n    provider.release_status.set()\n    qtbot.waitUntil(  # type: ignore[attr-defined]\n        lambda: reference.job_id not in controller._polling_jobs,\n        timeout=5000,\n    )\n    assert controller._jobs[reference.job_id].state is IqaJobState.CANCELLED\n    assert item.text(2) == "cancelled"\n\n    window.close()\n\n\ndef test_public_inflight_status_is_ignored_after_window_close(\n    qtbot: object,\n    monkeypatch: pytest.MonkeyPatch,\n    tmp_path: Path,\n) -> None:\n    provider = _DelayedStatusFixtureProvider(tmp_path)\n    installer = IqaClientInstaller.from_ports(provider, provider)\n    window = MainWindow(window_contributions=(installer,))\n    qtbot.addWidget(window)  # type: ignore[attr-defined]\n    documents = (\n        SimpleNamespace(source_path=tmp_path / "a.png", document_id="a", generation=1),\n        SimpleNamespace(source_path=tmp_path / "b.png", document_id="b", generation=1),\n    )\n    monkeypatch.setattr(window, "current_comparison_documents", lambda: list(documents))\n\n    installer.install_runtime(window)\n    shell = window.remote_iqa_workspace\n    controller = window.remote_iqa_controller\n    shell.current_submit.click()\n    qtbot.waitUntil(  # type: ignore[attr-defined]\n        lambda: shell.jobs_tree.topLevelItemCount() == 1,\n        timeout=5000,\n    )\n    controller._poll_timer.stop()\n    reference = IqaJobReference("fixture-job-0001")\n    provider.advance(reference)\n    qtbot.waitUntil(  # type: ignore[attr-defined]\n        lambda: reference.job_id not in controller._polling_jobs,\n        timeout=5000,\n    )\n\n    provider.delay_next_status()\n    controller._poll_due()\n    assert provider.status_entered.wait(timeout=5.0)\n    assert controller._jobs[reference.job_id].state is IqaJobState.QUEUED\n\n    window.close()\n    assert controller._active is False\n    assert provider.cancel_calls == 0\n\n    provider.release_status.set()\n    qtbot.wait(100)  # type: ignore[attr-defined]\n    assert controller._jobs[reference.job_id].state is IqaJobState.QUEUED\n    assert provider.cancel_calls == 0\n\n\n'''
    text = replace_once(text, marker, lifecycle_tests + marker, "public lifecycle race tests")
    path.write_text(text, encoding="utf-8")


def patch_lifecycle_guard() -> None:
    path = Path("tests/unit/test_qt_lifecycle_architecture.py")
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '    "src/pixelscope/ui/iqa_client_install.py",\n'
        '    "src/pixelscope/ui/iqa_submission_lifecycle.py",\n',
        '    "src/pixelscope/ui/iqa_client_install.py",\n'
        '    "src/pixelscope/ui/iqa_submission.py",\n'
        '    "src/pixelscope/ui/iqa_submission_lifecycle.py",\n',
        "lifecycle module coverage",
    )
    text = replace_once(
        text,
        '    "src/pixelscope/ui/iqa_client_install.py": {\n'
        '        ("_window", "window"),\n'
        '        ("window", "window"),\n'
        '    },\n',
        '    "src/pixelscope/ui/iqa_client_install.py": {\n'
        '        ("_window", "window"),\n'
        '        ("window", "window"),\n'
        '    },\n'
        '    "src/pixelscope/ui/iqa_submission.py": {\n'
        '        ("_window", "window"),\n'
        '        ("window", "window"),\n'
        '    },\n',
        "public controller owner guard",
    )
    path.write_text(text, encoding="utf-8")


def main() -> None:
    patch_client_install()
    patch_submission()
    patch_composition_tests()
    patch_lifecycle_guard()


if __name__ == "__main__":
    main()
