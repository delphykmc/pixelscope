from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QDockWidget

from pixelscope.app.main_window import MainWindow
from pixelscope.remote.iqa_public_contract import (
    IqaJobState,
    IqaProviderError,
    IqaProviderErrorKind,
)
from pixelscope.remote.iqa_public_fixture import FixtureIqaProvider, IqaFixtureProfile
from pixelscope.ui.beta_workspace_hardening import install_beta_workspace_hardening
from pixelscope_iqa_reference.extension import ReferenceIqaExtension


def test_reference_lite_proves_existing_menu_dock_status_and_child_window_hooks(
    qtbot: object,
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    extension = ReferenceIqaExtension(
        FixtureIqaProvider(tmp_path / "reference", IqaFixtureProfile.MINIMAL)
    )
    window = MainWindow(window_contributions=(extension,))
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    path_a, path_b = tmp_path / "a.png", tmp_path / "b.png"
    monkeypatch.setattr(  # type: ignore[attr-defined]
        window, "current_comparison_source_paths", lambda: (path_a, path_b)
    )

    assert extension.active
    assert window.action_map["Run IQA (Synthetic)"] is not None
    assert window.action_map["Show IQA Mock Jobs"] is extension.action
    assert extension.dock is not None
    assert extension.widget is not None
    assert extension.dock.objectName() == "referenceIqaWorkspaceDock"
    assert extension.dock.widget() is extension.widget

    # Run from MainWindow, not from a Base-specific IQA method.
    window.action_map["Run IQA (Synthetic)"].trigger()
    jobs = extension.jobs
    first_id = next(iter(jobs))
    assert jobs[first_id].state is IqaJobState.QUEUED
    assert extension.widget.jobs_list.count() == 1
    assert "Current pair: a.png" in extension.widget.selection_label.text()
    assert extension._job_sources[first_id] == ((path_a, path_b), False)
    assert "queued" in window.statusBar().currentMessage()

    # Captured sources and job identity survive a changed MainWindow selection.
    monkeypatch.setattr(  # type: ignore[attr-defined]
        window, "current_comparison_source_paths", lambda: (None, path_b)
    )
    extension.widget.submit_button.click()
    jobs = extension.jobs
    second_id = next(identifier for identifier in jobs if identifier != first_id)
    assert jobs[second_id].state is IqaJobState.QUEUED
    assert extension._job_sources[first_id] == ((path_a, path_b), False)
    assert extension._job_sources[second_id][1] is True
    assert "Synthetic pair" in extension.widget.selection_label.text()

    # One child can open EMPTY while there are multiple live jobs.
    extension.widget.empty_button.click()
    analysis = extension.analysis_window
    assert analysis is not None
    assert analysis.result is None
    assert analysis.isWindow()
    assert analysis.parent() is window

    # Manually advancing a selected fixture job never auto-switches the viewer.
    extension.widget.advance_button.click()
    assert extension.jobs[second_id].state is IqaJobState.RUNNING
    assert extension.jobs[first_id].state is IqaJobState.QUEUED
    extension.widget.advance_button.click()
    assert extension.jobs[second_id].state is IqaJobState.COMPLETED
    assert extension.widget.view_button.isEnabled()
    assert analysis.result is None

    extension.widget.view_button.click()
    assert analysis is extension.analysis_window
    assert analysis.result is not None
    assert analysis.result.result_id == "fixture-minimal"
    assert "Synthetic published result" in analysis.result_label.text()
    assert "No saved-file reader" in analysis.note_label.text()

    # Closing the child neither removes nor cancels jobs; the same child reopens.
    analysis.close()
    assert extension.jobs[first_id].state is IqaJobState.QUEUED
    assert extension.jobs[second_id].state is IqaJobState.COMPLETED
    extension.widget.view_button.click()
    assert extension.analysis_window is analysis

    # Selecting an older job retains its independent state/controls.
    extension.widget.jobs_list.setCurrentRow(0)
    assert extension.widget.advance_button.isEnabled()
    assert not extension.widget.view_button.isEnabled()
    extension.widget.advance_button.click()
    assert extension.jobs[first_id].state is IqaJobState.RUNNING

    window.close()
    assert not extension.active
    assert extension.analysis_window is None
    assert extension.jobs == {}
    extension.shutdown()  # idempotent


def test_reference_published_result_demo_is_explicitly_synthetic(
    qtbot: object,
    tmp_path: Path,
) -> None:
    extension = ReferenceIqaExtension(
        FixtureIqaProvider(tmp_path / "published", IqaFixtureProfile.MINIMAL)
    )
    window = MainWindow(window_contributions=(extension,))
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    window.action_map["Open Published Synthetic IQA Result (Demo)"].trigger()
    assert len(extension.jobs) == 1
    assert next(iter(extension.jobs.values())).state is IqaJobState.COMPLETED
    assert extension.analysis_window is not None
    assert extension.analysis_window.result is not None
    assert extension.analysis_window.result.result_id == "fixture-minimal"

    window.action_map["Open Empty IQA Analysis Canary"].trigger()
    assert extension.analysis_window.result is None
    assert "Empty analysis window" in extension.analysis_window.result_label.text()

    window.close()
    assert extension.analysis_window is None


def test_reference_failed_job_keeps_result_unavailable_without_disabling_new_jobs(
    qtbot: object,
    tmp_path: Path,
) -> None:
    extension = ReferenceIqaExtension(
        FixtureIqaProvider(tmp_path / "failure", IqaFixtureProfile.FAILURE)
    )
    window = MainWindow(window_contributions=(extension,))
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    assert extension.widget is not None

    extension.widget.submit_button.click()
    job_id = next(iter(extension.jobs))
    extension.widget.advance_button.click()
    extension.widget.advance_button.click()
    assert extension.jobs[job_id].state is IqaJobState.FAILED
    assert not extension.widget.advance_button.isEnabled()
    assert not extension.widget.view_button.isEnabled()
    assert "failed" in window.statusBar().currentMessage()
    assert extension.analysis_window is None

    extension.widget.submit_button.click()
    assert len(extension.jobs) == 2
    assert extension.jobs[job_id].state is IqaJobState.FAILED
    window.close()


def test_published_demo_submission_failure_does_not_advance_previous_selection(
    qtbot: object,
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    provider = FixtureIqaProvider(tmp_path / "submit-error", IqaFixtureProfile.MINIMAL)
    extension = ReferenceIqaExtension(provider)
    window = MainWindow(window_contributions=(extension,))
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    assert extension.widget is not None

    # An earlier selected job must never be mistaken for the failed new submission.
    extension.widget.submit_button.click()
    previous_id = extension.widget.selected_job_id()
    assert previous_id is not None
    assert extension.jobs[previous_id].state is IqaJobState.QUEUED

    def reject_submit(_intent: object) -> None:
        raise IqaProviderError(
            IqaProviderErrorKind.UNAVAILABLE,
            "Synthetic provider submission failed.",
        )

    monkeypatch.setattr(provider, "submit", reject_submit)
    window.action_map["Open Published Synthetic IQA Result (Demo)"].trigger()

    assert extension.widget.selected_job_id() == previous_id
    assert len(extension.jobs) == 1
    assert extension.jobs[previous_id].state is IqaJobState.QUEUED
    assert extension.analysis_window is None
    assert "submission failed" in extension.widget.status_label.text()

    # A second failed attempt also leaves the prior job intact.
    window.action_map["Open Published Synthetic IQA Result (Demo)"].trigger()
    assert extension.jobs[previous_id].state is IqaJobState.QUEUED
    assert len(extension.jobs) == 1
    window.close()


def test_reference_child_reopen_cycles_keep_jobs_alive_until_owner_shutdown(
    qtbot: object,
    tmp_path: Path,
) -> None:
    extension = ReferenceIqaExtension(
        FixtureIqaProvider(tmp_path / "child-cycles", IqaFixtureProfile.MINIMAL)
    )
    window = MainWindow(window_contributions=(extension,))
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    assert extension.widget is not None
    extension.widget.submit_button.click()
    job_id = extension.widget.selected_job_id()
    assert job_id is not None

    extension.widget.empty_button.click()
    child = extension.analysis_window
    assert child is not None
    for _ in range(5):
        child.close()
        assert child.isHidden()
        assert extension.jobs[job_id].state is IqaJobState.QUEUED
        extension.widget.empty_button.click()
        assert extension.analysis_window is child
        assert not child.isHidden()

    window.close()
    assert not extension.active
    assert extension.analysis_window is None
    assert child.isHidden()
    extension.shutdown()


def test_window_host_preserves_comparison_slot_cardinality_and_missing_native_paths(
    qtbot: object,
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    path_a = tmp_path / "a.png"
    path_b = tmp_path / "b.png"
    documents = [
        SimpleNamespace(source_path=None),
        SimpleNamespace(source_path=path_a),
        SimpleNamespace(source_path=path_b),
    ]
    monkeypatch.setattr(  # type: ignore[attr-defined]
        window,
        "current_comparison_documents",
        lambda: documents,
    )
    assert window.current_comparison_source_paths() == (None, path_a, path_b)
    window.close()


def test_reference_current_pair_requires_exactly_two_native_slots(
    qtbot: object,
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    extension = ReferenceIqaExtension(
        FixtureIqaProvider(tmp_path / "cardinality", IqaFixtureProfile.MINIMAL)
    )
    window = MainWindow(window_contributions=(extension,))
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    path_a = tmp_path / "a.png"
    path_b = tmp_path / "b.png"
    path_c = tmp_path / "c.png"

    for slots in (
        (path_a, path_b, path_c),
        (None, path_a),
        (path_a, None),
        (None, path_a, path_b),
    ):
        monkeypatch.setattr(  # type: ignore[attr-defined]
            window,
            "current_comparison_source_paths",
            lambda slots=slots: slots,
        )
        _intent, paths, synthetic = extension._submission_intent()
        assert synthetic
        assert paths == (Path("reference-a.synthetic"), Path("reference-b.synthetic"))

    monkeypatch.setattr(  # type: ignore[attr-defined]
        window, "current_comparison_source_paths", lambda: (path_a, path_b)
    )
    intent, paths, synthetic = extension._submission_intent()
    assert not synthetic
    assert paths == (path_a, path_b)
    assert intent.scenes[0].sources[0].local_path == path_a
    assert intent.scenes[0].sources[1].local_path == path_b
    window.close()


def test_reference_dock_uses_generic_contributed_dock_lifecycle_hardening(
    qtbot: object,
    tmp_path: Path,
) -> None:
    extension = ReferenceIqaExtension(
        FixtureIqaProvider(tmp_path / "generic-dock", IqaFixtureProfile.MINIMAL)
    )
    window = MainWindow(window_contributions=(extension,))
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    hardening = install_beta_workspace_hardening(window)
    assert extension.dock is not None
    managed_parents = {controller.parent() for controller in hardening._dock_controllers}
    assert window.bottom_dock in managed_parents
    assert extension.dock in managed_parents
    assert not hasattr(window, "iqa_dock")
    assert not hasattr(window, "iqa_workspace_action")

    window.close()


def test_core_only_has_no_reference_ui_or_import_dependency(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    assert "Run IQA (Synthetic)" not in window.action_map
    assert "Open Empty IQA Analysis Canary" not in window.action_map
    assert not any(
        dock.objectName() == "referenceIqaWorkspaceDock"
        for dock in window.findChildren(QDockWidget)
    )
    window.close()
