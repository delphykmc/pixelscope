from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import QTreeWidgetItem

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.remote.iqa_fixture import write_golden_result
from pixelscope.remote.iqa_history import (
    IqaResultIdentity,
    LocalIqaResultLocator,
    LogicalIqaResultLocator,
    RecentIqaResultEntry,
)
from pixelscope.remote.iqa_submission import IqaResultReference, JobState
from pixelscope.remote.iqa_v2_fixture import write_golden_result_v2
from pixelscope.remote.iqa_v2_partial import PartialResultV2
from pixelscope.ui.iqa_submission import RemoteJobRecord

pytestmark = pytest.mark.usefixtures("isolated_qsettings_subdirectory")


def _set_result_id(root: Path, result_id: str) -> Path:
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["result_id"] = result_id
    manifest_path.write_text(
        json.dumps(manifest, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return root


def _make_partial(root: Path) -> Path:
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["publication_state"] = "partial"
    manifest["scene_outcomes"] = [
        {"scene_id": scene["scene_id"], "status": "succeeded"} for scene in manifest["scenes"]
    ] + [
        {
            "scene_id": "scene_failed_history",
            "status": "failed",
            "error": {
                "code": "fixture_failure",
                "message": "historical fixture failure",
                "retryable": True,
            },
        }
    ]
    manifest_path.write_text(
        json.dumps(manifest, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return root


def _open_and_wait(qtbot: Any, window: MainWindow, root: Path, result_id: str) -> None:
    window.iqa_controller.open_result(root)
    qtbot.waitUntil(
        lambda: getattr(window.iqa_workspace.result, "result_id", None) == result_id,
        timeout=5000,
    )


def _tree_values(item: QTreeWidgetItem) -> list[str]:
    values = [item.text(0), item.text(1)]
    for index in range(item.childCount()):
        child = item.child(index)
        if child is not None:
            values.extend(_tree_values(child))
    return values


def _provenance_text(window: MainWindow) -> str:
    panel = window.historical_iqa_results_controller.provenance
    values: list[str] = [panel.status.text()]
    for index in range(panel.tree.topLevelItemCount()):
        item = panel.tree.topLevelItem(index)
        if item is not None:
            values.extend(_tree_values(item))
    return "\n".join(values)


def test_manual_result_open_records_recent_and_remains_browsable_without_sources(
    qtbot: Any,
    tmp_path: Path,
) -> None:
    root = _set_result_id(
        write_golden_result_v2(tmp_path / "result"),
        "history-result",
    )
    window = MainWindow()
    qtbot.addWidget(window)
    _compose_main_window_presentation(window)

    _open_and_wait(qtbot, window, root, "history-result")

    history = window.historical_iqa_results_controller.repository.load()
    assert len(history) == 1
    assert history[0].identity == IqaResultIdentity("history-result", 2)
    assert isinstance(history[0].locator, LocalIqaResultLocator)
    assert window.iqa_workspace.result is not None

    # The golden result publishes source identities but no local source files/root locators.
    # Result browsing must remain valid; only explicit P5-D Inspect depends on native sources.
    window.iqa_workspace._select_scene_index(0)
    qtbot.waitUntil(
        lambda: "Native source inspection unavailable" in _provenance_text(window),
        timeout=1000,
    )
    provenance = _provenance_text(window)
    assert "history-result" in provenance
    assert "measurement_context_id" in provenance
    assert "sha256" in provenance
    assert "pixelscope-iqa-model-suite-v2" in provenance
    window.close()


def test_recent_identity_mismatch_preserves_last_valid_result_and_history(
    qtbot: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_a = _set_result_id(
        write_golden_result_v2(tmp_path / "result-a"),
        "result-a",
    )
    root_b = _set_result_id(
        write_golden_result_v2(tmp_path / "result-b"),
        "result-b",
    )
    window = MainWindow()
    qtbot.addWidget(window)
    _compose_main_window_presentation(window)
    controller = window.historical_iqa_results_controller

    _open_and_wait(qtbot, window, root_a, "result-a")
    previous_result = window.iqa_workspace.result
    previous_history = controller.repository.load()
    failures: list[str] = []
    monkeypatch.setattr(
        controller,
        "_offer_remove_keep",
        lambda _entry, reason: failures.append(reason),
    )
    mismatched = RecentIqaResultEntry(
        LocalIqaResultLocator(str(root_b.resolve())),
        IqaResultIdentity("result-a", 2),
    )

    controller.open_recent(mismatched)
    qtbot.waitUntil(lambda: bool(failures), timeout=5000)

    assert "historical identity mismatch" in failures[-1]
    assert window.iqa_workspace.result is previous_result
    assert getattr(window.iqa_workspace.result, "result_id", None) == "result-a"
    assert controller.repository.load() == previous_history
    window.close()


def test_jobs_open_signal_records_published_logical_locator_not_mapped_path(
    qtbot: Any,
    tmp_path: Path,
) -> None:
    root = _set_result_id(
        write_golden_result_v2(tmp_path / "job-result"),
        "job-result",
    )
    window = MainWindow()
    qtbot.addWidget(window)
    _compose_main_window_presentation(window)
    remote = window.remote_iqa_controller
    reference = IqaResultReference(
        job_id="job-17",
        storage_root_id="production-results",
        relative_path="results/2026/job-17",
        schema_version=2,
        publication_state="complete",
    )
    remote._jobs["job-17"] = RemoteJobRecord(
        job_id="job-17",
        submission_kind="current_pair",
        server_base_url="https://iqa.invalid",
        state=JobState.SUCCEEDED,
        result_reference=reference,
        result_path=root,
    )

    remote.workspace.open_result_requested.emit("job-17")
    qtbot.waitUntil(
        lambda: getattr(window.iqa_workspace.result, "result_id", None) == "job-result",
        timeout=5000,
    )

    entry = window.historical_iqa_results_controller.repository.load()[0]
    assert entry.locator == LogicalIqaResultLocator(
        "production-results",
        "results/2026/job-17",
    )
    assert str(root) not in entry.locator.display_location
    window.close()


def test_schema_v1_history_is_local_and_explicitly_read_only(
    qtbot: Any,
    tmp_path: Path,
) -> None:
    root = _set_result_id(
        write_golden_result(tmp_path / "v1-result"),
        "history-v1",
    )
    window = MainWindow()
    qtbot.addWidget(window)
    _compose_main_window_presentation(window)

    _open_and_wait(qtbot, window, root, "history-v1")

    entry = window.historical_iqa_results_controller.repository.load()[0]
    assert entry.identity == IqaResultIdentity("history-v1", 1)
    assert isinstance(entry.locator, LocalIqaResultLocator)
    provenance = _provenance_text(window)
    assert "historical / read-only" in provenance
    assert "schema_version" in provenance
    assert "measurement_context_id" not in provenance
    assert "storage_root_id" not in provenance
    window.close()


def test_partial_history_preserves_publication_state_and_failed_scene_diagnostics(
    qtbot: Any,
    tmp_path: Path,
) -> None:
    root = _make_partial(
        _set_result_id(
            write_golden_result_v2(tmp_path / "partial-result"),
            "history-partial",
        ),
    )
    window = MainWindow()
    qtbot.addWidget(window)
    _compose_main_window_presentation(window)

    _open_and_wait(qtbot, window, root, "history-partial")

    result = window.iqa_workspace.result
    assert isinstance(result, PartialResultV2)
    assert result.publication_state == "partial"
    assert result.unsuccessful_scene_outcomes[0].scene_id == "scene_failed_history"
    assert "PARTIAL" in _provenance_text(window)
    entry = window.historical_iqa_results_controller.repository.load()[0]
    assert entry.identity == IqaResultIdentity("history-partial", 2)
    window.close()


def test_rapid_result_open_keeps_only_latest_generation(
    qtbot: Any,
    tmp_path: Path,
) -> None:
    root_a = _set_result_id(
        write_golden_result_v2(tmp_path / "rapid-a"),
        "rapid-a",
    )
    root_b = _set_result_id(
        write_golden_result_v2(tmp_path / "rapid-b"),
        "rapid-b",
    )
    window = MainWindow()
    qtbot.addWidget(window)
    _compose_main_window_presentation(window)
    controller = window.historical_iqa_results_controller
    canonical_loader = window.iqa_controller._loader
    started = threading.Event()
    release = threading.Event()

    def gated_loader(path: Path | str) -> object:
        if Path(path) == root_a:
            started.set()
            assert release.wait(timeout=3.0)
        return canonical_loader(path)

    window.iqa_controller._loader = gated_loader
    controller._start_open(root_a)
    assert started.wait(timeout=3.0)
    controller._start_open(root_b)
    release.set()

    qtbot.waitUntil(
        lambda: getattr(window.iqa_workspace.result, "result_id", None) == "rapid-b",
        timeout=5000,
    )
    qtbot.wait(50)

    assert getattr(window.iqa_workspace.result, "result_id", None) == "rapid-b"
    assert [entry.result_id for entry in controller.repository.load()] == ["rapid-b"]
    window.close()


def test_mapping_revision_change_rejects_loaded_result_before_presentation(
    qtbot: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_a = _set_result_id(
        write_golden_result_v2(tmp_path / "mapped-a"),
        "mapped-a",
    )
    root_b = _set_result_id(
        write_golden_result_v2(tmp_path / "mapped-b"),
        "mapped-b",
    )
    window = MainWindow()
    qtbot.addWidget(window)
    _compose_main_window_presentation(window)
    controller = window.historical_iqa_results_controller
    _open_and_wait(qtbot, window, root_a, "mapped-a")
    previous_result = window.iqa_workspace.result

    canonical_loader = window.iqa_controller._loader
    started = threading.Event()
    release = threading.Event()

    def gated_loader(path: Path | str) -> object:
        if Path(path) == root_b:
            started.set()
            assert release.wait(timeout=3.0)
        return canonical_loader(path)

    window.iqa_controller._loader = gated_loader
    entry = RecentIqaResultEntry(
        LogicalIqaResultLocator("results", "history/mapped-b"),
        IqaResultIdentity("mapped-b", 2),
    )
    reopened: list[RecentIqaResultEntry] = []
    monkeypatch.setattr(controller, "open_recent", reopened.append)
    revision = controller._mapping_revision()

    controller._start_open(
        root_b,
        locator=entry.locator,
        expected=entry.identity,
        mapping_revision=revision,
        from_recent=True,
    )
    assert started.wait(timeout=3.0)
    window.remote_iqa_result_mapping._revision = revision + 1
    release.set()

    qtbot.waitUntil(lambda: reopened == [entry], timeout=5000)

    assert window.iqa_workspace.result is previous_result
    assert getattr(window.iqa_workspace.result, "result_id", None) == "mapped-a"
    assert [item.result_id for item in controller.repository.load()] == ["mapped-a"]
    window.close()


def test_recent_history_survives_window_close_and_recreate(
    qtbot: Any,
    tmp_path: Path,
) -> None:
    root = _set_result_id(
        write_golden_result_v2(tmp_path / "result"),
        "persistent-result",
    )
    first = MainWindow()
    qtbot.addWidget(first)
    _compose_main_window_presentation(first)
    _open_and_wait(qtbot, first, root, "persistent-result")
    first.close()

    second = MainWindow()
    qtbot.addWidget(second)
    _compose_main_window_presentation(second)

    entries = second.historical_iqa_results_controller.repository.load()
    assert entries
    assert entries[0].result_id == "persistent-result"
    menu_text = [
        action.text() for action in second.historical_iqa_results_controller.recent_menu.actions()
    ]
    assert any("persistent-result" in text for text in menu_text)
    second.close()
