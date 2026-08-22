"""Presentation-only polish for the Remote IQA Setup workflow."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QLayout, QVBoxLayout


def polish_remote_iqa_setup(workspace: Any) -> None:
    """Recompose existing P5-C controls without changing submission authority."""

    layout = workspace.setup_page.layout()
    if not isinstance(layout, QVBoxLayout):
        raise RuntimeError("Remote IQA Setup page layout is unavailable")

    _drain_layout(layout)
    layout.setContentsMargins(6, 8, 6, 6)
    layout.setSpacing(10)

    settings_row = QHBoxLayout()
    settings_row.setSpacing(8)
    title = QLabel("Remote IQA", workspace.setup_page)
    title_font = title.font()
    title_font.setBold(True)
    title.setFont(title_font)
    workspace.configuration_label.setToolTip(
        "Machine-local server and shared-storage configuration. Configure once, then submit pairs."
    )
    workspace.configure_button.setText("Settings…")
    settings_row.addWidget(title)
    settings_row.addWidget(workspace.configuration_label, 1)
    settings_row.addWidget(workspace.configure_button)
    layout.addLayout(settings_row)

    current_group = QGroupBox("Current Pair", workspace.setup_page)
    current_group.setObjectName("remoteIqaCurrentPairGroup")
    current_group.setToolTip(
        "Uses exactly the two native images on the Current Comparison Page, in A/B page order."
    )
    current_layout = QVBoxLayout(current_group)
    current_layout.setContentsMargins(8, 10, 8, 8)
    current_layout.setSpacing(6)
    current_layout.addWidget(workspace.current_pair_label)
    current_actions = QHBoxLayout()
    current_actions.addStretch(1)
    workspace.current_submit.setText("Submit Pair")
    workspace.current_submit.setToolTip(
        "Prepare the current A/B pair and submit one Remote IQA job."
    )
    current_actions.addWidget(workspace.current_submit)
    current_layout.addLayout(current_actions)
    layout.addWidget(current_group)

    folder_group = QGroupBox("Folder Pair", workspace.setup_page)
    folder_group.setObjectName("remoteIqaFolderPairGroup")
    folder_group.setToolTip(
        "Choose A/B folders, validate the deterministic lexical pairing, then submit the previewed pairs."
    )
    folder_layout = QVBoxLayout(folder_group)
    folder_layout.setContentsMargins(8, 10, 8, 8)
    folder_layout.setSpacing(6)

    for label_text, editor, button in (
        ("A", workspace.folder_a, workspace.folder_a_browse),
        ("B", workspace.folder_b, workspace.folder_b_browse),
    ):
        row = QHBoxLayout()
        row.setSpacing(6)
        label = QLabel(label_text, folder_group)
        label.setFixedWidth(14)
        editor.setPlaceholderText(f"Choose Folder {label_text}")
        editor.setAccessibleName(f"Remote IQA Folder {label_text}")
        button.setText("Browse…")
        row.addWidget(label)
        row.addWidget(editor, 1)
        row.addWidget(button)
        folder_layout.addLayout(row)

    folder_actions = QHBoxLayout()
    folder_actions.setSpacing(6)
    workspace.preview_button.setText("Validate")
    workspace.preview_button.setToolTip(
        "Validate every A/B pair and preview the exact deterministic Scene order before submission."
    )
    workspace.preview_status.setWordWrap(False)
    workspace.preview_status.setToolTip(
        "Folder Pair must be validated again whenever either folder input changes."
    )
    workspace.folder_submit.setText("Submit Pairs")
    workspace.folder_submit.setToolTip(
        "Submit the currently validated Folder Pair. This is disabled until validation succeeds."
    )
    folder_actions.addWidget(workspace.preview_button)
    folder_actions.addWidget(workspace.preview_status, 1)
    folder_actions.addWidget(workspace.folder_submit)
    folder_layout.addLayout(folder_actions)
    folder_layout.addWidget(workspace.preview_table, 1)
    layout.addWidget(folder_group, 1)

    workspace.remote_iqa_current_actions = current_actions
    workspace.remote_iqa_folder_actions = folder_actions
    workspace.remote_iqa_setup_layout = layout


def _drain_layout(layout: QLayout) -> None:
    """Remove layout ownership while preserving the existing widgets for recomposition."""

    while layout.count():
        item = layout.takeAt(0)
        if item is None:
            continue
        child_layout = item.layout()
        if child_layout is not None:
            _drain_layout(child_layout)
            child_layout.deleteLater()
