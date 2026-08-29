"""Presentation-only polish for the Remote IQA Setup workflow."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class _CompactStatusLabel(QLabel):
    """QLabel that renders compact text while preserving full detail as a tooltip."""

    def __init__(
        self,
        source: QLabel,
        compact: Callable[[str], str],
    ) -> None:
        super().__init__(source.parentWidget())
        self._compact = compact
        self.setObjectName(source.objectName())
        self.setAccessibleName(source.accessibleName())
        self.setAlignment(source.alignment())
        self.setSizePolicy(source.sizePolicy())
        self.setWordWrap(False)
        self.setText(source.text())
        source.hide()

    def setText(self, text: str) -> None:  # noqa: N802 - Qt API override
        self.setToolTip(text)
        super().setText(self._compact(text))


def polish_remote_iqa_setup(workspace: Any) -> None:
    """Recompose existing P5-C controls without changing submission authority."""

    layout = workspace.setup_page.layout()
    if not isinstance(layout, QVBoxLayout):
        raise RuntimeError("Remote IQA Setup page layout is unavailable")

    workspace.configuration_label = _replace_status_label(
        workspace.configuration_label,
        _compact_configuration_status,
    )
    workspace.current_pair_label = _replace_status_label(
        workspace.current_pair_label,
        _compact_current_pair_status,
    )
    workspace.preview_status = _replace_status_label(
        workspace.preview_status,
        _compact_folder_status,
    )

    preserved = (
        workspace.configuration_label,
        workspace.configure_button,
        workspace.current_pair_label,
        workspace.current_pair_a,
        workspace.current_pair_b,
        workspace.current_submit,
        workspace.folder_a,
        workspace.folder_b,
        workspace.folder_a_browse,
        workspace.folder_b_browse,
        workspace.preview_button,
        workspace.preview_status,
        workspace.folder_submit,
        workspace.preview_table,
    )
    _drain_layout(layout, preserved)
    layout.setContentsMargins(6, 8, 6, 6)
    layout.setSpacing(10)

    settings_row = QHBoxLayout()
    settings_row.setSpacing(8)
    workspace.configure_button.setText("Settings…")
    workspace.configure_button.setToolTip(
        "Configure the Remote IQA server and this machine's shared-storage mappings."
    )
    settings_row.addWidget(workspace.configuration_label, 1)
    settings_row.addWidget(workspace.configure_button)
    layout.addLayout(settings_row)

    current_group = QGroupBox("Current Pair", workspace.setup_page)
    current_group.setObjectName("remoteIqaCurrentPairGroup")
    current_group.setToolTip(
        "Uses exactly the two native RGB images on the Current Comparison Page, "
        "in A/B page order."
    )
    current_layout = QVBoxLayout(current_group)
    current_layout.setContentsMargins(8, 10, 8, 8)
    current_layout.setSpacing(6)

    for label_text, value in (
        ("A", workspace.current_pair_a),
        ("B", workspace.current_pair_b),
    ):
        row = QHBoxLayout()
        row.setSpacing(6)
        label = QLabel(label_text, current_group)
        label.setFixedWidth(14)
        value.setMinimumWidth(0)
        value_policy = value.sizePolicy()
        value_policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
        value.setSizePolicy(value_policy)
        value.show()
        row.addWidget(label)
        row.addWidget(value, 1)
        current_layout.addLayout(row)

    current_actions = QHBoxLayout()
    current_actions.setSpacing(6)
    workspace.current_submit.setText("Submit Pair")
    workspace.current_submit.setToolTip(
        "Submit the current A/B pair. Both images must be RGB, have the same dimensions, "
        "and use the same pixel format."
    )
    current_actions.addWidget(workspace.current_pair_label, 1)
    current_actions.addWidget(workspace.current_submit)
    current_layout.addLayout(current_actions)
    layout.addWidget(current_group)

    folder_group = QGroupBox("Folder Pair", workspace.setup_page)
    folder_group.setObjectName("remoteIqaFolderPairGroup")
    folder_group.setToolTip(
        "Choose A/B folders, validate the deterministic lexical pairing, "
        "then submit the previewed pairs."
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
        "Validate every A/B pair and preview the exact deterministic Scene order "
        "before submission."
    )
    workspace.folder_submit.setText("Submit Pairs")
    workspace.folder_submit.setToolTip(
        "Submit the currently validated Folder Pair. "
        "This is disabled until validation succeeds."
    )
    folder_actions.addWidget(workspace.preview_button)
    folder_actions.addWidget(workspace.preview_status, 1)
    folder_actions.addWidget(workspace.folder_submit)
    folder_layout.addLayout(folder_actions)
    folder_layout.addWidget(workspace.preview_table, 1)
    layout.addWidget(folder_group, 1)

    workspace.remote_iqa_current_layout = current_layout
    workspace.remote_iqa_current_actions = current_actions
    workspace.remote_iqa_folder_actions = folder_actions
    workspace.remote_iqa_setup_layout = layout


def _replace_status_label(
    source: QLabel,
    compact: Callable[[str], str],
) -> _CompactStatusLabel:
    return _CompactStatusLabel(source, compact)


def _compact_configuration_status(text: str) -> str:
    if text.startswith("Configured · "):
        return text.replace(" storage root(s)", " root", 1)
    if text.startswith("Remote IQA submission unavailable"):
        return "Not configured"
    return text


def _compact_current_pair_status(text: str) -> str:
    folded = text.casefold()
    if text.startswith("OK · "):
        return text
    if "rgb images" in folded:
        return "Blocked · RGB images required"
    if "size mismatch" in folded:
        return "Blocked · size mismatch"
    if "format mismatch" in folded:
        return "Blocked · format mismatch"
    if "exactly two images" in folded or "not an eligible pair" in folded:
        return "Select 2 images in Comparison Page"
    if "configure" in folded and "remote iqa" in folded:
        return "Configure Remote IQA first"
    if "native source" in folded or "split/difference" in folded:
        return "Native image pair required"
    if "raw is not eligible" in folded:
        return "RAW is not supported"
    if "unsupported remote iqa extension" in folded:
        return "Unsupported image format"
    if text.startswith("Unavailable · "):
        return "Unavailable · see tooltip"
    return text


def _compact_folder_status(text: str) -> str:
    folded = text.casefold()
    if "choose folder a and folder b" in folded or "choose both folders" in folded:
        return "Choose A/B folders"
    if "inputs changed" in folded:
        return "Changed · Validate again"
    if "validating folder pair" in folded:
        return "Validating…"
    if text.startswith("Validated full Pair Preview · ") and text.endswith(" Scenes"):
        count = text.removeprefix("Validated full Pair Preview · ").removesuffix(" Scenes")
        return f"{count} pairs ready"
    if text.startswith("Blocked · "):
        if "count mismatch" in folded:
            return "Blocked · count mismatch"
        if "no eligible images" in folded:
            return "Blocked · no images"
        if "dimension mismatch" in folded:
            return "Blocked · size mismatch"
        if "folder is unavailable" in folded:
            return "Blocked · folder unavailable"
        return "Blocked · see tooltip"
    return text


def _drain_layout(layout: QLayout, preserved: tuple[QWidget, ...]) -> None:
    """Remove old layout ownership and hide presentation widgets that will not be reused."""

    while layout.count():
        item = layout.takeAt(0)
        if item is None:
            continue
        widget = item.widget()
        if widget is not None and widget not in preserved:
            widget.hide()
        child_layout = item.layout()
        if child_layout is not None:
            _drain_layout(child_layout, preserved)
            child_layout.deleteLater()
