"""Remote-IQA category layered onto the existing application Settings dialog."""

from __future__ import annotations

from dataclasses import replace
from types import MethodType
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pixelscope.app.settings import ApplicationSettings, SettingsRepository
from pixelscope.core.performance_settings import PerformanceSettings
from pixelscope.remote.iqa_settings import RemoteIqaSettings, RemoteIqaStorageRoot
from pixelscope.ui.settings_dialog import SettingsDialog


class RemoteIqaSettingsDialog(SettingsDialog):
    """Existing Settings UI plus live-applied Remote IQA machine-local mapping."""

    def __init__(
        self,
        repository: SettingsRepository,
        initial_settings: ApplicationSettings,
        runtime_performance_settings: PerformanceSettings,
        parent: QWidget | None = None,
        physical_memory_bytes: int | None = None,
    ) -> None:
        super().__init__(
            repository,
            initial_settings,
            runtime_performance_settings,
            parent,
            physical_memory_bytes,
        )
        self.category_list.addItem("Remote IQA")
        self.remote_page = self._build_remote_page()
        self.page_stack.addWidget(self.remote_page)
        self._set_remote_iqa(initial_settings.remote_iqa)
        if repository.is_read_only_compatibility_mode:
            self.remote_page.setEnabled(False)

    def _build_remote_page(self) -> QScrollArea:
        page = QWidget()
        page.setObjectName("remoteIqaSettingsPageContent")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 26, 32, 36)
        layout.setSpacing(12)

        title = QLabel("Remote IQA", page)
        title.setProperty("settingsRole", "pageTitle")
        layout.addWidget(title)
        description = QLabel(
            "Configure the Remote IQA endpoint and this machine's logical shared-storage "
            "mappings. Server physical paths and credentials are never stored here.",
            page,
        )
        description.setProperty("settingsRole", "pageDescription")
        description.setWordWrap(True)
        layout.addWidget(description)

        layout.addWidget(QLabel("Server base URL", page))
        self.remote_server_url = QLineEdit(page)
        self.remote_server_url.setObjectName("remoteIqaServerBaseUrl")
        self.remote_server_url.setPlaceholderText("https://iqa.example.invalid")
        layout.addWidget(self.remote_server_url)

        roots_heading = QLabel("Shared-storage roots", page)
        roots_heading.setProperty("settingsRole", "sectionTitle")
        layout.addWidget(roots_heading)
        roots_help = QLabel(
            "Each portable storage_root_id maps to one absolute local drive or UNC root. "
            "The share may be offline while the setting is saved; availability is checked "
            "when a submission or result is resolved.",
            page,
        )
        roots_help.setWordWrap(True)
        roots_help.setProperty("settingsRole", "description")
        layout.addWidget(roots_help)

        self.remote_roots = QTableWidget(0, 2, page)
        self.remote_roots.setObjectName("remoteIqaStorageRoots")
        self.remote_roots.setHorizontalHeaderLabels(("Root ID", "Client path"))
        self.remote_roots.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.remote_roots.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.remote_roots.verticalHeader().setVisible(False)
        header = self.remote_roots.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.remote_roots, 1)

        root_buttons = QHBoxLayout()
        self.add_remote_root = QPushButton("Add Root", page)
        self.add_remote_root.setObjectName("remoteIqaAddRoot")
        self.remove_remote_root = QPushButton("Remove Root", page)
        self.remove_remote_root.setObjectName("remoteIqaRemoveRoot")
        root_buttons.addWidget(self.add_remote_root)
        root_buttons.addWidget(self.remove_remote_root)
        root_buttons.addStretch(1)
        layout.addLayout(root_buttons)

        layout.addWidget(QLabel("Staging root", page))
        self.remote_staging_root = QComboBox(page)
        self.remote_staging_root.setObjectName("remoteIqaStagingRoot")
        layout.addWidget(self.remote_staging_root)
        staging_help = QLabel(
            "Sources outside all configured roots require a staging root. PixelScope "
            "publishes them as staging/<sha256>/<basename> without changing Files or "
            "Selected.",
            page,
        )
        staging_help.setWordWrap(True)
        staging_help.setProperty("settingsRole", "description")
        layout.addWidget(staging_help)
        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setObjectName("remoteIqaSettingsPage")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(page)

        self.add_remote_root.clicked.connect(  # type: ignore[attr-defined]
            self._add_root_row
        )
        self.remove_remote_root.clicked.connect(  # type: ignore[attr-defined]
            self._remove_root_row
        )
        self.remote_roots.itemChanged.connect(  # type: ignore[attr-defined]
            self._roots_changed
        )
        return scroll

    def settings(self) -> ApplicationSettings:
        base = super().settings()
        return replace(base, remote_iqa=self._remote_iqa_from_controls())

    def set_settings(self, settings: ApplicationSettings) -> None:
        super().set_settings(settings)
        if hasattr(self, "remote_server_url"):
            self._set_remote_iqa(settings.remote_iqa)

    def _save(self) -> None:
        try:
            self._remote_iqa_from_controls()
        except (TypeError, ValueError) as exc:
            QMessageBox.warning(self, "Invalid Remote IQA settings", str(exc))
            return
        super()._save()

    def _set_remote_iqa(self, settings: RemoteIqaSettings) -> None:
        self.remote_server_url.setText(settings.server_base_url)
        self.remote_roots.blockSignals(True)
        self.remote_roots.setRowCount(0)
        for root in settings.storage_roots:
            row = self.remote_roots.rowCount()
            self.remote_roots.insertRow(row)
            self.remote_roots.setItem(row, 0, QTableWidgetItem(root.storage_root_id))
            self.remote_roots.setItem(row, 1, QTableWidgetItem(root.client_path))
        self.remote_roots.blockSignals(False)
        self._refresh_staging_choices(settings.staging_root_id)

    def _remote_iqa_from_controls(self) -> RemoteIqaSettings:
        roots: list[RemoteIqaStorageRoot] = []
        for row in range(self.remote_roots.rowCount()):
            id_item = self.remote_roots.item(row, 0)
            path_item = self.remote_roots.item(row, 1)
            root_id = "" if id_item is None else id_item.text().strip()
            client_path = "" if path_item is None else path_item.text().strip()
            roots.append(RemoteIqaStorageRoot(root_id, client_path))
        staging_data = self.remote_staging_root.currentData()
        staging = str(staging_data) if isinstance(staging_data, str) and staging_data else None
        return RemoteIqaSettings(
            server_base_url=self.remote_server_url.text().strip(),
            storage_roots=tuple(roots),
            staging_root_id=staging,
        )

    def _add_root_row(self) -> None:
        row = self.remote_roots.rowCount()
        self.remote_roots.insertRow(row)
        self.remote_roots.setItem(row, 0, QTableWidgetItem(""))
        self.remote_roots.setItem(row, 1, QTableWidgetItem(""))
        self.remote_roots.setCurrentCell(row, 0)
        item = self.remote_roots.item(row, 0)
        if item is not None:
            self.remote_roots.editItem(item)
        self._refresh_staging_choices(None)

    def _remove_root_row(self) -> None:
        row = self.remote_roots.currentRow()
        if row >= 0:
            selected = self.remote_staging_root.currentData()
            self.remote_roots.removeRow(row)
            self._refresh_staging_choices(str(selected) if isinstance(selected, str) else None)

    def _roots_changed(self, _item: QTableWidgetItem) -> None:
        selected = self.remote_staging_root.currentData()
        self._refresh_staging_choices(str(selected) if isinstance(selected, str) else None)

    def _refresh_staging_choices(self, preferred: str | None) -> None:
        self.remote_staging_root.blockSignals(True)
        self.remote_staging_root.clear()
        self.remote_staging_root.addItem("No staging root", None)
        preferred_index = 0
        seen: set[str] = set()
        for row in range(self.remote_roots.rowCount()):
            item = self.remote_roots.item(row, 0)
            root_id = "" if item is None else item.text().strip()
            if not root_id or root_id in seen:
                continue
            seen.add(root_id)
            self.remote_staging_root.addItem(root_id, root_id)
            if root_id == preferred:
                preferred_index = self.remote_staging_root.count() - 1
        self.remote_staging_root.setCurrentIndex(preferred_index)
        self.remote_staging_root.blockSignals(False)


def install_remote_iqa_settings_dialog(window: Any) -> None:
    """Use the extended Settings dialog without changing MainWindow's settings ownership."""

    def create_settings_dialog(self: Any) -> RemoteIqaSettingsDialog:
        dialog = RemoteIqaSettingsDialog(
            self.settings_repository,
            self.application_settings,
            self.performance_settings,
            self,
        )
        dialog.settings_saved.connect(self._application_settings_saved)

        def remote_settings_saved(_settings: object) -> None:
            controller = getattr(self, "remote_iqa_controller", None)
            if controller is not None:
                controller.settings_changed()

        dialog.settings_saved.connect(remote_settings_saved)
        return dialog

    window.create_settings_dialog = MethodType(create_settings_dialog, window)
