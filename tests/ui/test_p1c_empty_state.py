from __future__ import annotations

from pixelscope.ui.empty_state import EmptyWorkspace


def test_empty_workspace_uses_final_guidance_and_actions(qtbot: object) -> None:
    workspace = EmptyWorkspace()
    qtbot.addWidget(workspace)  # type: ignore[attr-defined]

    assert workspace.title.text() == "Drop images or folders here"
    assert workspace.open_images_button.text() == "Open Images..."
    assert workspace.open_folders_button.text() == "Open Folder..."
    assert not hasattr(workspace, "open_raw_button")
    assert not hasattr(workspace, "open_raw_requested")
    assert workspace.formats_hint.text() == "PNG · JPEG · BMP · RAW"
    assert workspace.shortcuts_hint.text() == "Ctrl+O images · Ctrl+Shift+O folder"
    assert workspace.gestures_hint.text() == (
        "On an image: Ctrl+drag ROI · Shift+drag line profile"
    )

    with qtbot.waitSignal(workspace.open_images_requested):  # type: ignore[attr-defined]
        workspace.open_images_button.click()
    with qtbot.waitSignal(workspace.open_folders_requested):  # type: ignore[attr-defined]
        workspace.open_folders_button.click()


def test_registered_but_unselected_workspace_prompts_for_files_selection(
    qtbot: object,
) -> None:
    workspace = EmptyWorkspace()
    qtbot.addWidget(workspace)  # type: ignore[attr-defined]

    workspace.set_registered_documents(True)

    assert workspace.title.text() == "Select an image from Files to view"
    assert workspace.open_images_button.isHidden()
    assert workspace.open_folders_button.isHidden()
    assert workspace.formats_hint.isHidden()
    assert workspace.shortcuts_hint.isHidden()
    assert workspace.gestures_hint.isHidden()

    workspace.set_registered_documents(False)
    assert workspace.title.text() == "Drop images or folders here"
