from __future__ import annotations

import json
import threading
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import QTreeWidgetItem

import pixelscope.ui.iqa_historical_results as history_module
from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.remote.iqa_history import (
    IqaResultIdentity,
    LogicalIqaResultLocator,
    RecentIqaResultEntry,
)
from pixelscope.remote.iqa_settings import (
    RemoteIqaSettings,
    RemoteIqaStorageRoot,
)
from pixelscope.remote.iqa_submission import IqaResultReference, JobState
from pixelscope.remote.iqa_v2_fixture import write_golden_result_v2
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


def _publish_source_root(root: Path, storage_root_id: str) -> Path:
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for scene in manifest["scenes"]:
        for source in scene["sources"]:
            source["storage_root_id"] = storage_root_id
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


def _delayed_recent(
    monkeypatch: pytest.MonkeyPatch,
    target: Path,
) -> tuple[threading.Event, threading.Event]:
    started = threading.Event()
    release = threading.Event()

    def delayed_resolve(
        _storage_root_id: str,
        _relative_path: str,
        _settings: RemoteIqaSettings,
    ) -> Path:
        started.set()
        assert release.wait(timeout=3.0)
        return target

    monkeypatch.setattr(history_module, "resolve_result_reference", delayed_resolve)
    return started, release


def test_delayed_logical_recent_cannot_override_newer_file_open(
    qtbot: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_a = _set_result_id(write_golden_result_v2(tmp_path / "recent-a"), "recent-a")
    root_b = _set_result_id(write_golden_result_v2(tmp_path / "file-b"), "file-b")
    window = MainWindow()
    qtbot.addWidget(window)
    _compose_main_window_presentation(window)
    controller = window.historical_iqa_results_controller
    canonical_loader = window.iqa_controller._loader
    loaded: list[Path] = []

    def tracking_loader(path: Path | str) -> object:
        loaded.append(Path(path))
        return canonical_loader(path)

    window.iqa_controller._loader = tracking_loader
    started, release = _delayed_recent(monkeypatch, root_a)
    entry = RecentIqaResultEntry(
        LogicalIqaResultLocator("results", "history/recent-a"),
        IqaResultIdentity("recent-a", 2),
    )

    controller.open_recent(entry)
    assert started.wait(timeout=3.0)
    _open_and_wait(qtbot, window, root_b, "file-b")
    release.set()
    qtbot.wait(100)

    assert getattr(window.iqa_workspace.result, "result_id", None) == "file-b"
    assert root_a not in loaded
    assert [item.result_id for item in controller.repository.load()] == ["file-b"]
    assert getattr(controller.provenance.result, "result_id", None) == "file-b"
    window.close()


def test_delayed_logical_recent_cannot_override_newer_jobs_open(
    qtbot: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_a = _set_result_id(write_golden_result_v2(tmp_path / "recent-a"), "recent-a")
    root_b = _set_result_id(write_golden_result_v2(tmp_path / "job-b"), "job-b")
    window = MainWindow()
    qtbot.addWidget(window)
    _compose_main_window_presentation(window)
    controller = window.historical_iqa_results_controller
    remote = window.remote_iqa_controller
    canonical_loader = window.iqa_controller._loader
    loaded: list[Path] = []

    def tracking_loader(path: Path | str) -> object:
        loaded.append(Path(path))
        return canonical_loader(path)

    window.iqa_controller._loader = tracking_loader
    started, release = _delayed_recent(monkeypatch, root_a)
    recent_entry = RecentIqaResultEntry(
        LogicalIqaResultLocator("results", "history/recent-a"),
        IqaResultIdentity("recent-a", 2),
    )
    job_reference = IqaResultReference(
        job_id="job-b",
        storage_root_id="published-results",
        relative_path="results/job-b",
        schema_version=2,
        publication_state="complete",
    )
    remote._jobs["job-b"] = RemoteJobRecord(
        job_id="job-b",
        submission_kind="current_pair",
        server_base_url="https://iqa.invalid",
        state=JobState.SUCCEEDED,
        result_reference=job_reference,
        result_path=root_b,
    )

    controller.open_recent(recent_entry)
    assert started.wait(timeout=3.0)
    remote.workspace.open_result_requested.emit("job-b")
    qtbot.waitUntil(
        lambda: getattr(window.iqa_workspace.result, "result_id", None) == "job-b",
        timeout=5000,
    )
    release.set()
    qtbot.wait(100)

    assert getattr(window.iqa_workspace.result, "result_id", None) == "job-b"
    assert root_a not in loaded
    history = controller.repository.load()
    assert [item.result_id for item in history] == ["job-b"]
    assert history[0].locator == LogicalIqaResultLocator(
        "published-results",
        "results/job-b",
    )
    assert getattr(controller.provenance.result, "result_id", None) == "job-b"
    window.close()


def test_provenance_tracks_live_remote_root_mapping_changes(
    qtbot: Any,
    tmp_path: Path,
) -> None:
    result_root = _publish_source_root(
        _set_result_id(
            write_golden_result_v2(tmp_path / "result"),
            "live-provenance",
        ),
        "native-root",
    )
    native_root = tmp_path / "native"
    native_root.mkdir()
    window = MainWindow()
    qtbot.addWidget(window)
    _compose_main_window_presentation(window)
    _open_and_wait(qtbot, window, result_root, "live-provenance")
    window.iqa_workspace._select_scene_index(0)
    inspection = window.iqa_scene_inspection_controller

    assert not inspection.inspect_button.isEnabled()
    assert "storage root not configured" in _provenance_text(window)

    configured = RemoteIqaSettings(
        storage_roots=(RemoteIqaStorageRoot("native-root", str(native_root)),)
    )
    window.application_settings = replace(window.application_settings, remote_iqa=configured)
    window.remote_iqa_controller.settings_changed()

    assert inspection.inspect_button.isEnabled()
    assert "Inspect performs existence/dimension/SHA verification" in _provenance_text(window)

    window.application_settings = replace(
        window.application_settings,
        remote_iqa=RemoteIqaSettings(),
    )
    window.remote_iqa_controller.settings_changed()

    assert not inspection.inspect_button.isEnabled()
    assert "storage root not configured" in _provenance_text(window)
    window.close()
