from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDockWidget

from pixelscope.app.bootstrap import compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
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
    window.action_map["Show IQA Analysis Window"].trigger()
    analysis = extension.analysis_window
    assert analysis is not None
    assert analysis.result is None
    assert analysis.isWindow()
    assert analysis.parent() is window
    assert window.action_map["Show IQA Analysis Window"].isChecked()

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
    assert not window.action_map["Show IQA Analysis Window"].isChecked()
    assert extension.jobs[first_id].state is IqaJobState.QUEUED
    assert extension.jobs[second_id].state is IqaJobState.COMPLETED
    extension.widget.view_button.click()
    assert extension.analysis_window is analysis
    assert window.action_map["Show IQA Analysis Window"].isChecked()

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

    window.action_map["Load Synthetic Demo Result"].trigger()
    assert len(extension.jobs) == 1
    assert next(iter(extension.jobs.values())).state is IqaJobState.COMPLETED
    assert extension.analysis_window is not None
    assert extension.analysis_window.result is not None
    assert extension.analysis_window.result.result_id == "fixture-minimal"

    # Visibility-only toggle preserves the published result and child identity.
    view_action = window.action_map["Show IQA Analysis Window"]
    assert view_action.isChecked()
    analysis = extension.analysis_window
    view_action.trigger()
    assert not view_action.isChecked()
    assert analysis.isHidden()
    assert analysis.result is not None
    assert analysis.result.result_id == "fixture-minimal"
    view_action.trigger()
    assert view_action.isChecked()
    assert extension.analysis_window is analysis
    assert analysis.result.result_id == "fixture-minimal"

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


@pytest.mark.parametrize("completed_first", (False, True))
def test_published_demo_submission_failure_does_not_advance_previous_selection(
    completed_first: bool,
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
    if completed_first:
        extension.widget.advance_button.click()
        extension.widget.advance_button.click()
    expected = IqaJobState.COMPLETED if completed_first else IqaJobState.QUEUED
    assert extension.jobs[previous_id].state is expected

    def reject_submit(_intent: object) -> None:
        raise IqaProviderError(
            IqaProviderErrorKind.UNAVAILABLE,
            "Synthetic provider submission failed.",
        )

    monkeypatch.setattr(provider, "submit", reject_submit)
    window.action_map["Load Synthetic Demo Result"].trigger()

    assert extension.widget.selected_job_id() == previous_id
    assert len(extension.jobs) == 1
    assert extension.jobs[previous_id].state is expected
    assert extension.analysis_window is None
    assert "submission failed" in extension.widget.status_label.text()

    # A second failed attempt also leaves the prior job intact.
    window.action_map["Load Synthetic Demo Result"].trigger()
    assert extension.jobs[previous_id].state is expected
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

    view_action = window.action_map["Show IQA Analysis Window"]
    view_action.trigger()
    child = extension.analysis_window
    assert child is not None
    for _ in range(5):
        child.close()
        assert child.isHidden()
        assert not view_action.isChecked()
        assert extension.jobs[job_id].state is IqaJobState.QUEUED
        view_action.trigger()
        assert view_action.isChecked()
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


def test_reference_iqa_commands_and_view_controls_in_composed_window(
    qtbot: object,
    tmp_path: Path,
) -> None:
    extension = ReferenceIqaExtension(
        FixtureIqaProvider(tmp_path / "menu", IqaFixtureProfile.MINIMAL)
    )
    window = MainWindow(window_contributions=(extension,))
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    compose_main_window_presentation(window)  # Match the Reference launcher.
    window.show()

    # Session replaces File during presentation composition. Check the
    # attached menus, not stale QMenu wrappers in the old File menu.
    menu_bar = window.menuBar()
    top_actions = list(menu_bar.actions())
    names = [action.text().replace("&", "") for action in top_actions]
    assert names.index("Selection") < names.index("IQA") < names.index("View")
    assert menu_bar.isVisible()
    for name in ("File", "IQA", "View"):
        menu = window._menu_map[name]
        assert menu.menuAction() in top_actions, (name, names)
        assert menu.menuAction().isVisible() and menu.menuAction().isEnabled()

    file_actions = window._menu_map["File"].actions()
    file_labels = [action.text() for action in file_actions]
    assert "Open Images..." in file_labels and "Open Folder..." in file_labels
    assert "Run IQA (Synthetic)" not in file_labels
    assert "Load Synthetic Demo Result" not in file_labels
    assert "Open Empty IQA Analysis Canary" not in file_labels
    assert "Open IQA Result..." not in file_labels  # No saved-file reader in Reference.

    iqa_menu = window._menu_map["IQA"]
    commands = ("Run IQA (Synthetic)", "Load Synthetic Demo Result")
    iqa_actions = list(iqa_menu.actions())
    iqa_labels = [action.text() for action in iqa_actions]
    assert iqa_labels == list(commands)
    for label in commands:
        action = window.action_map[label]
        assert action in iqa_actions
        assert action.isVisible() and action.isEnabled()

    view_menu = window._menu_map["View"]
    view_labels = [action.text() for action in view_menu.actions()]
    for label in ("Show IQA Mock Jobs", "Show IQA Analysis Window"):
        action = window.action_map[label]
        assert action in view_menu.actions()
        assert view_labels.count(label) == 1
        assert action.isCheckable()
        assert action.isVisible() and action.isEnabled()
    assert not window.action_map["Show IQA Analysis Window"].isChecked()

    # Verify the actual IQA popup rather than just an action map.
    anchor = menu_bar.actionGeometry(iqa_menu.menuAction()).bottomLeft()
    iqa_menu.popup(menu_bar.mapToGlobal(anchor))
    qtbot.waitUntil(iqa_menu.isVisible)  # type: ignore[attr-defined]
    assert all(action.isVisible() and action.isEnabled() for action in iqa_actions)
    iqa_menu.hide()
    window.close()


def test_jobs_dock_view_toggle_honors_explicit_hide_across_new_jobs(
    qtbot: object,
    tmp_path: Path,
) -> None:
    extension = ReferenceIqaExtension(
        FixtureIqaProvider(tmp_path / "dock-visibility", IqaFixtureProfile.MINIMAL)
    )
    window = MainWindow(window_contributions=(extension,))
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.show()
    assert extension.widget is not None
    assert extension.dock is not None
    dock_action = window.action_map["Show IQA Mock Jobs"]
    assert not dock_action.isChecked()

    # The first submission may reveal Jobs as a convenience.
    extension.widget.submit_button.click()
    assert extension.dock.isVisible()
    assert dock_action.isChecked()

    dock_action.trigger()  # User explicitly hides the dock from View.
    assert not dock_action.isChecked()
    assert extension.dock.isHidden()

    extension.widget.submit_button.click()
    assert len(extension.jobs) == 2
    assert extension.dock.isHidden()
    assert not dock_action.isChecked()

    dock_action.trigger()
    assert dock_action.isChecked()
    assert extension.dock.isVisible()
    assert extension.widget.jobs_list.count() == 2
    window.close()


def test_delete_and_ctrl_a_only_modify_files_when_files_tree_has_focus(
    qtbot: object,
    tmp_path: Path,
) -> None:
    extension = ReferenceIqaExtension(
        FixtureIqaProvider(tmp_path / "keys", IqaFixtureProfile.MINIMAL)
    )
    window = MainWindow(window_contributions=(extension,))
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = [
        ImageDocument.from_array(np.zeros((4, 4), dtype=np.uint8), f"image-{i}") for i in range(2)
    ]
    window.add_document(documents[0], select=True)
    window.add_document(documents[1], select=False)
    window.show()
    window.activateWindow()
    assert extension.widget is not None
    extension.widget.submit_button.click()  # Show dock and populate its job list.
    jobs_list = extension.widget.jobs_list
    assert jobs_list.count() == 1
    assert len(window.document_list.selected_document_items()) == 1

    # Delete while IQA Jobs has focus must not remove the previously selected image.
    jobs_list.setFocus()
    qtbot.waitUntil(lambda: QApplication.focusWidget() == jobs_list)  # type: ignore[attr-defined]
    qtbot.keyClick(jobs_list, Qt.Key.Key_Delete)  # type: ignore[attr-defined]
    assert all(doc.document_id in window.documents for doc in documents)
    assert window.document_list.document_count == 2
    assert len(window.document_list.selected_document_items()) == 1

    # Ctrl+A in the Jobs list must likewise not change background Files selection.
    qtbot.keyClick(  # type: ignore[attr-defined]
        jobs_list, Qt.Key.Key_A, modifier=Qt.KeyboardModifier.ControlModifier
    )
    assert len(window.document_list.selected_document_items()) == 1

    # The scoped shortcuts must continue working in Files itself.
    files = window.document_list
    files.setFocus()
    qtbot.waitUntil(lambda: QApplication.focusWidget() == files)  # type: ignore[attr-defined]
    qtbot.keyClick(  # type: ignore[attr-defined]
        files, Qt.Key.Key_A, modifier=Qt.KeyboardModifier.ControlModifier
    )
    assert len(files.selected_document_items()) == 2
    qtbot.keyClick(files, Qt.Key.Key_Delete)  # type: ignore[attr-defined]
    assert window.documents == {}
    assert files.document_count == 0
    assert jobs_list.count() == 1
    window.close()


def test_core_only_has_no_reference_ui_or_import_dependency(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    assert "Run IQA (Synthetic)" not in window.action_map
    assert "Show IQA Analysis Window" not in window.action_map
    assert "IQA" not in window._menu_map
    assert not any(
        dock.objectName() == "referenceIqaWorkspaceDock"
        for dock in window.findChildren(QDockWidget)
    )
    window.close()
