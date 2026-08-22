from __future__ import annotations

import pytest
from PySide6.QtWidgets import QGroupBox

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

    assert isinstance(
        workspace.setup_page.findChild(QGroupBox, "remoteIqaCurrentPairGroup"),
        QGroupBox,
    )
    assert isinstance(
        workspace.setup_page.findChild(QGroupBox, "remoteIqaFolderPairGroup"),
        QGroupBox,
    )
    assert workspace.current_submit.text() == "Submit Pair"
    assert workspace.preview_button.text() == "Validate"
    assert workspace.folder_submit.text() == "Submit Pairs"
    assert workspace.folder_a.placeholderText() == "Choose Folder A"
    assert workspace.folder_b.placeholderText() == "Choose Folder B"
    assert workspace.folder_a_browse.text() == "Browse…"
    assert workspace.folder_b_browse.text() == "Browse…"
    assert not hasattr(window, "remote_iqa_request_inspector")
    window.close()


def test_debug_request_inspection_is_secondary_and_hidden_until_used(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PIXELSCOPE_REMOTE_IQA_DEBUG", "1")
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    _compose_main_window_presentation(window)

    assert window.remote_iqa_request_inspect_current.text() == "Inspect Request · DEBUG"
    assert window.remote_iqa_request_inspect_folder.text() == "Inspect Request · DEBUG"
    assert window.remote_iqa_request_inspector.isHidden()
    assert window.remote_iqa_request_inspector.request_text.isReadOnly()
    window.close()
