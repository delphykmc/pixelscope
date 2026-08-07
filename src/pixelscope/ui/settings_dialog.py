from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from pixelscope.app.settings import (
    MAX_DIFFERENCE_CACHE_MIB,
    MIN_DIFFERENCE_CACHE_MIB,
    ApplicationSettings,
    SettingsRepository,
)
from pixelscope.core.performance_settings import MIB, PerformanceSettings


class SettingsDialog(QDialog):
    """Edit persisted application preferences without mutating startup runtime state."""

    settings_saved = Signal(object)

    def __init__(
        self,
        repository: SettingsRepository,
        initial_settings: ApplicationSettings,
        runtime_performance_settings: PerformanceSettings,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(760, 480)
        self.setMinimumSize(680, 420)
        self._repository = repository
        self._runtime_performance_settings = runtime_performance_settings

        self.category_list = QListWidget()
        self.category_list.setObjectName("settingsCategoryList")
        self.category_list.setFixedWidth(150)
        self.category_list.addItems(("General", "Files", "Performance"))

        self.page_stack = QStackedWidget()
        self.page_stack.setObjectName("settingsPageStack")

        self.dont_show_raw_json_profiles = QCheckBox("Don't Show RAW JSON Profiles")
        self.dont_show_raw_json_profiles.setObjectName("generalDontShowRawJsonProfiles")

        self.default_open_directory = QLineEdit()
        self.default_open_directory.setObjectName("filesDefaultOpenDirectory")
        self.default_open_directory.setPlaceholderText("Use last-used folder")
        self.default_open_browse = QPushButton("Browse...")
        self.default_open_browse.setObjectName("filesDefaultOpenBrowse")

        self.default_export_directory = QLineEdit()
        self.default_export_directory.setObjectName("filesDefaultExportDirectory")
        self.default_export_directory.setPlaceholderText("Use last-used folder")
        self.default_export_browse = QPushButton("Browse...")
        self.default_export_browse.setObjectName("filesDefaultExportBrowse")

        self.difference_cache_mib = QSpinBox()
        self.difference_cache_mib.setObjectName("performanceDifferenceCacheMiB")
        self.difference_cache_mib.setRange(
            MIN_DIFFERENCE_CACHE_MIB,
            MAX_DIFFERENCE_CACHE_MIB,
        )
        self.difference_cache_mib.setSuffix(" MiB")
        self.difference_cache_mib.setKeyboardTracking(False)

        self.restart_required_label = QLabel("Changes take effect after restarting PixelScope.")
        self.restart_required_label.setObjectName("restartRequiredLabel")
        self.restart_required_label.setWordWrap(True)

        self.compatibility_label = QLabel()
        self.compatibility_label.setObjectName("settingsCompatibilityLabel")
        self.compatibility_label.setWordWrap(True)
        self.compatibility_label.hide()

        self.page_stack.addWidget(self._build_general_page())
        self.page_stack.addWidget(self._build_files_page())
        self.page_stack.addWidget(self._build_performance_page())

        self.reset_button = QPushButton("Reset Settings")
        self.reset_button.setObjectName("resetSettingsButton")
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.setObjectName("settingsButtonBox")

        body = QHBoxLayout()
        body.setSpacing(16)
        body.addWidget(self.category_list)
        body.addWidget(self.page_stack, 1)

        button_row = QHBoxLayout()
        button_row.addWidget(self.reset_button)
        button_row.addStretch(1)
        button_row.addWidget(self.button_box)

        layout = QVBoxLayout(self)
        layout.addWidget(self.compatibility_label)
        layout.addLayout(body, 1)
        layout.addLayout(button_row)

        self.category_list.currentRowChanged.connect(  # type: ignore[attr-defined]
            self.page_stack.setCurrentIndex
        )
        self.default_open_browse.clicked.connect(  # type: ignore[attr-defined]
            self._browse_default_open_directory
        )
        self.default_export_browse.clicked.connect(  # type: ignore[attr-defined]
            self._browse_default_export_directory
        )
        self.difference_cache_mib.valueChanged.connect(  # type: ignore[attr-defined]
            self._update_restart_required
        )
        self.button_box.accepted.connect(self._save)  # type: ignore[attr-defined]
        self.button_box.rejected.connect(self.reject)  # type: ignore[attr-defined]
        self.reset_button.clicked.connect(self._reset)  # type: ignore[attr-defined]

        self.category_list.setCurrentRow(0)
        self.set_settings(initial_settings)
        if repository.is_read_only_compatibility_mode:
            self._set_future_schema_read_only(repository.future_schema_version)

    def _build_general_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 0, 0, 0)
        layout.addWidget(self._page_title("General"))

        raw_group = QGroupBox("RAW Profiles")
        raw_layout = QVBoxLayout(raw_group)
        raw_layout.addWidget(self.dont_show_raw_json_profiles)
        explanation = QLabel(
            "Skip repeated confirmation when a valid RAW JSON sidecar matches "
            "the source file."
        )
        explanation.setWordWrap(True)
        raw_layout.addWidget(explanation)
        layout.addWidget(raw_group)
        layout.addStretch(1)
        return page

    def _build_files_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 0, 0, 0)
        layout.addWidget(self._page_title("Files"))

        locations_group = QGroupBox("Default Locations")
        form = QFormLayout(locations_group)
        form.addRow(
            "Open Folder",
            self._directory_editor(self.default_open_directory, self.default_open_browse),
        )
        form.addRow(
            "Export Folder",
            self._directory_editor(self.default_export_directory, self.default_export_browse),
        )
        explanation = QLabel(
            "Leave a field blank to keep using the last folder used by PixelScope. "
            "Configured folders only change the starting location of file dialogs."
        )
        explanation.setWordWrap(True)
        form.addRow("", explanation)
        layout.addWidget(locations_group)
        layout.addStretch(1)
        return page

    def _build_performance_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 0, 0, 0)
        layout.addWidget(self._page_title("Performance"))

        performance_group = QGroupBox("Memory")
        form = QFormLayout(performance_group)
        form.addRow("Difference Cache", self.difference_cache_mib)
        range_label = QLabel(
            f"Allowed range: {MIN_DIFFERENCE_CACHE_MIB}–"
            f"{MAX_DIFFERENCE_CACHE_MIB} MiB"
        )
        range_label.setObjectName("differenceCacheRangeLabel")
        form.addRow("", range_label)
        form.addRow("", self.restart_required_label)
        layout.addWidget(performance_group)
        layout.addStretch(1)
        return page

    @staticmethod
    def _page_title(text: str) -> QLabel:
        label = QLabel(text)
        font = label.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 3)
        label.setFont(font)
        return label

    @staticmethod
    def _directory_editor(line_edit: QLineEdit, browse_button: QPushButton) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(line_edit, 1)
        layout.addWidget(browse_button)
        return container

    @property
    def restart_required(self) -> bool:
        return not self.restart_required_label.isHidden()

    def settings(self) -> ApplicationSettings:
        return ApplicationSettings(
            dont_show_raw_json_profiles=self.dont_show_raw_json_profiles.isChecked(),
            difference_cache_mib=self.difference_cache_mib.value(),
            default_open_directory=self.default_open_directory.text().strip(),
            default_export_directory=self.default_export_directory.text().strip(),
        )

    def set_settings(self, settings: ApplicationSettings) -> None:
        self.dont_show_raw_json_profiles.setChecked(settings.dont_show_raw_json_profiles)
        self.default_open_directory.setText(settings.default_open_directory)
        self.default_export_directory.setText(settings.default_export_directory)
        self.difference_cache_mib.setValue(settings.difference_cache_mib)
        self._update_restart_required()

    def _save(self) -> None:
        settings = self._repository.save(self.settings())
        self.settings_saved.emit(settings)
        self.accept()

    def _reset(self) -> None:
        settings = self._repository.reset()
        self.set_settings(settings)
        self.settings_saved.emit(settings)

    def _browse_default_open_directory(self) -> None:
        self._browse_directory(
            self.default_open_directory,
            "Select default open folder",
        )

    def _browse_default_export_directory(self) -> None:
        self._browse_directory(
            self.default_export_directory,
            "Select default export folder",
        )

    def _browse_directory(self, target: QLineEdit, title: str) -> None:
        path = QFileDialog.getExistingDirectory(self, title, target.text().strip())
        if path:
            target.setText(path)

    def _update_restart_required(self, _value: int | None = None) -> None:
        requested_bytes = self.difference_cache_mib.value() * MIB
        self.restart_required_label.setVisible(
            requested_bytes != self._runtime_performance_settings.difference_cache_bytes
        )

    def _set_future_schema_read_only(self, version: int | None) -> None:
        self.dont_show_raw_json_profiles.setEnabled(False)
        self.default_open_directory.setEnabled(False)
        self.default_open_browse.setEnabled(False)
        self.default_export_directory.setEnabled(False)
        self.default_export_browse.setEnabled(False)
        self.difference_cache_mib.setEnabled(False)
        self.reset_button.setEnabled(False)
        save_button = self.button_box.button(QDialogButtonBox.StandardButton.Save)
        if save_button is not None:
            save_button.setEnabled(False)
        self.compatibility_label.setText(
            "Settings were created by a newer PixelScope schema"
            + (f" ({version})." if version is not None else ".")
            + " Preferences are read-only in this version."
        )
        self.compatibility_label.setVisible(True)
