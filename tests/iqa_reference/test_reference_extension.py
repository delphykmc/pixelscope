from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QDockWidget

from pixelscope.app.main_window import MainWindow
from pixelscope.remote.iqa_public_fixture import FixtureIqaProvider, IqaFixtureProfile
from pixelscope_iqa_reference.extension import ReferenceIqaExtension


def test_reference_extension_exercises_mock_job_result_reference_and_scene_flow(
    qtbot: object,
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    provider = FixtureIqaProvider(tmp_path / "reference", IqaFixtureProfile.MINIMAL)
    extension = ReferenceIqaExtension(provider)
    window = MainWindow(window_contributions=(extension,))
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    path_a = tmp_path / "a.png"
    path_b = tmp_path / "b.png"
    monkeypatch.setattr(  # type: ignore[attr-defined]
        window,
        "current_comparison_source_paths",
        lambda: (path_a, path_b),
    )

    assert extension.active
    assert extension.dock is not None
    assert extension.widget is not None
    assert extension.dock.objectName() == "referenceIqaWorkspaceDock"
    assert extension.dock.widget() is extension.widget
    assert window.action_map["Open IQA Reference Result..."] is not None
    assert window.action_map["Show IQA Reference"] is extension.action
    assert [
        dock
        for dock in window.findChildren(QDockWidget)
        if dock.objectName() == "referenceIqaWorkspaceDock"
    ] == [extension.dock]

    extension.widget.submit_button.click()
    assert "queued" in extension.widget.job_label.text()
    assert "Current pair" in extension.widget.selection_label.text()

    extension.widget.advance_button.click()
    assert "running" in extension.widget.job_label.text()
    extension.widget.advance_button.click()
    assert "completed" in extension.widget.job_label.text()
    assert extension.widget.open_button.isEnabled()

    extension.widget.open_button.click()
    assert extension.widget.result is not None
    assert extension.widget.result.result_id == "fixture-minimal"
    assert extension.widget.reference_combo.count() == 2
    assert extension.widget.scene_combo.count() == 3
    assert "Synthetic IQA fixture" in extension.widget.result_label.text()
    assert "Spatial: available" in extension.widget.detail_label.text()

    extension.widget.reference_combo.setCurrentIndex(1)
    extension.widget.scene_combo.setCurrentIndex(2)
    assert "Variant" not in extension.widget.detail_label.text()
    assert "scene_0002_variant_001.png" in extension.widget.detail_label.text()

    window.close()
    assert not extension.active


def test_reference_file_action_opens_published_mock_result_without_external_backend(
    qtbot: object,
    tmp_path: Path,
) -> None:
    provider = FixtureIqaProvider(tmp_path / "saved", IqaFixtureProfile.MINIMAL)
    extension = ReferenceIqaExtension(provider)
    window = MainWindow(window_contributions=(extension,))
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    window.action_map["Open IQA Reference Result..."].trigger()

    assert extension.widget is not None
    assert extension.widget.result is not None
    assert extension.widget.result.result_id == "fixture-minimal"
    assert "completed" in extension.widget.job_label.text()
    assert extension.dock is not None and extension.dock.isVisible()

    window.close()
    assert not extension.active
