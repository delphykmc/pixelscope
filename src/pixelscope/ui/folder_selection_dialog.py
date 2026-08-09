from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QListView,
    QTreeView,
    QWidget,
)


class MultiFolderDialog(QFileDialog):
    """Qt-only directory picker with deterministic extended selection."""

    def __init__(
        self,
        parent: QWidget | None = None,
        title: str = "Open image folders",
        directory: str = "",
    ) -> None:
        super().__init__(parent, title, directory)
        self.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        self.setOption(QFileDialog.Option.ShowDirsOnly, True)
        self.setFileMode(QFileDialog.FileMode.Directory)
        self.setLabelText(QFileDialog.DialogLabel.Accept, "Open Folders")

        list_view = self.findChild(QListView, "listView")
        tree_view = self.findChild(QTreeView, "treeView")
        for view in (list_view, tree_view):
            if isinstance(view, QAbstractItemView):
                view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

    def selected_directories(self) -> tuple[Path, ...]:
        unique: dict[str, Path] = {}
        for selected in self.selectedFiles():
            path = Path(selected)
            if not path.is_dir():
                continue
            resolved = path.resolve()
            unique.setdefault(str(resolved).casefold(), resolved)
        return tuple(unique[key] for key in sorted(unique))


def choose_directories(
    parent: QWidget | None,
    title: str,
    directory: str,
) -> tuple[Path, ...]:
    """Return selected existing directories, deduplicated in deterministic order."""

    dialog = MultiFolderDialog(parent, title, directory)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return ()
    return dialog.selected_directories()
