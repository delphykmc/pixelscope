from __future__ import annotations

import pytest
from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow


def test_release_remote_iqa_setup_uses_compact_pair_workflow(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PIXELSCOPE_REMOTE_IQA_DEBUG", raising=False)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    _compose_main_window_presentation(window)
    workspace = window.remote_iqa_workspace
    current_group = workspace.setup_page.findChild(
        QGroupBox,
        "remoteIqaCurrentPairGroup",
    )
    folder_group = workspace.setup_page.findChild(
        QGroupBox,
        "remoteIqaFolderPairGroup",
    )

    assert isinstance(current_group, QGroupBox)
    assert isinstance(folder_group, QGroupBox)
    assert isinstance(current_group.layout(), QVBoxLayout)
    assert isinstance(workspace.remote_iqa_current_actions, QHBoxLayout)
    assert workspace.remote_iqa_current_actions.indexOf(workspace.current_pair_label) >= 0
    assert workspace.remote_iqa_current_actions.indexOf(workspace.current_submit) >= 0
    assert workspace.current_pair_a.text() == "—"
    assert workspace.current_pair_b.text() == "—"
    assert workspace.current_pair_a.minimumWidth() == 0
    assert workspace.current_pair_b.minimumWidth() == 0
    assert (
        workspace.current_pair_a.sizePolicy().horizontalPolicy()
        == QSizePolicy.Policy.Ignored
    )
    assert (
        workspace.current_pair_b.sizePolicy().horizontalPolicy()
        == QSizePolicy.Policy.Ignored
    )
    assert workspace.current_submit.text() == "Submit Pair"
    assert workspace.preview_button.text() == "Validate"
    assert workspace.folder_submit.text() == "Submit Pairs"
    assert workspace.folder_a.placeholderText() == "Choose Folder A"
    assert workspace.folder_b.placeholderText() == "Choose Folder B"
    assert workspace.folder_a_browse.text() == "Browse…"
    assert workspace.folder_b_browse.text() == "Browse…"
    assert workspace.current_pair_label.text() == "Configure Remote IQA first"
    assert workspace.preview_status.text() == "Choose A/B folders"

    stale_headings = [
        label
        for label in workspace.setup_page.findChildren(QLabel)
        if label.text() in {"Current Pair", "Folder Pair"}
    ]
    assert stale_headings
    assert all(label.isHidden() for label in stale_headings)
    assert not hasattr(window, "remote_iqa_request_inspector")
    window.close()


def test_compact_setup_status_keeps_full_text_in_tooltip(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PIXELSCOPE_REMOTE_IQA_DEBUG", raising=False)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    workspace = window.remote_iqa_workspace

    current_full = "Unavailable · Current Comparison Page must contain exactly two images"
    workspace.current_pair_label.setText(current_full)
    assert workspace.current_pair_label.text() == "Select 2 images in Comparison Page"
    assert workspace.current_pair_label.toolTip() == current_full

    workspace.current_pair_label.setText("Unavailable · IQA requires RGB images")
    assert workspace.current_pair_label.text() == "Blocked · RGB images required"

    workspace.current_pair_label.setText("Unavailable · image size mismatch")
    assert workspace.current_pair_label.text() == "Blocked · size mismatch"

    workspace.current_pair_label.setText("Unavailable · image format mismatch")
    assert workspace.current_pair_label.text() == "Blocked · format mismatch"

    preview_full = "Validated full Pair Preview · 24 Scenes"
    workspace.preview_status.setText(preview_full)
    assert workspace.preview_status.text() == "24 pairs ready"
    assert workspace.preview_status.toolTip() == preview_full
    window.close()


def test_current_pair_presentation_shows_a_b_status_and_submit_rows(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PIXELSCOPE_REMOTE_IQA_DEBUG", raising=False)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    workspace = window.remote_iqa_workspace

    workspace.set_current_pair_state(
        "OK · RGB · 1920×1080",
        True,
        None,
        names=("reference_with_a_long_name.png", "candidate_with_a_long_name.png"),
    )

    assert workspace.current_pair_a.text() == "reference_with_a_long_name.png"
    assert workspace.current_pair_b.text() == "candidate_with_a_long_name.png"
    assert workspace.current_pair_label.text() == "OK · RGB · 1920×1080"
    assert workspace.current_submit.isEnabled()

    workspace.set_current_pair_state(
        "Current Pair is not eligible.",
        False,
        "image size mismatch",
        names=("reference.png", "candidate.png"),
    )
    assert workspace.current_pair_label.text() == "Blocked · size mismatch"
    assert not workspace.current_submit.isEnabled()
    window.close()


def test_debug_request_inspection_is_secondary_and_hidden_until_used(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PIXELSCOPE_REMOTE_IQA_DEBUG", "1")
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    _compose_main_window_presentation(window)

    assert window.remote_iqa_request_inspect_current.text() == "Inspect JSON · DEBUG"
    assert window.remote_iqa_request_inspect_folder.text() == "Inspect JSON · DEBUG"
    assert window.remote_iqa_request_inspector.isHidden()
    assert window.remote_iqa_request_inspector.request_text.isReadOnly()
    window.close()
