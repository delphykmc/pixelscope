from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
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


class _SettingRow(QWidget):
    """Flat title/description/control row used by Settings sections."""

    def __init__(
        self,
        title: str,
        description: str,
        control: QWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 12)
        layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setProperty("settingsRole", "settingTitle")
        layout.addWidget(title_label)

        description_label = QLabel(description)
        description_label.setProperty("settingsRole", "description")
        description_label.setWordWrap(True)
        layout.addWidget(description_label)
        layout.addSpacing(2)
        layout.addWidget(control)


class _SettingsSection(QWidget):
    """Flat Settings section with optional explanatory text and separators."""

    def __init__(
        self,
        title: str,
        description: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._row_count = 0
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        title_label = QLabel(title)
        title_label.setProperty("settingsRole", "sectionTitle")
        self._layout.addWidget(title_label)
        if description:
            description_label = QLabel(description)
            description_label.setProperty("settingsRole", "description")
            description_label.setWordWrap(True)
            self._layout.addWidget(description_label)
            self._layout.addSpacing(4)

    def add_row(self, row: _SettingRow) -> None:
        if self._row_count:
            separator = QFrame()
            separator.setObjectName("settingsRowSeparator")
            separator.setFrameShape(QFrame.Shape.HLine)
            separator.setFrameShadow(QFrame.Shadow.Plain)
            self._layout.addWidget(separator)
        self._layout.addWidget(row)
        self._row_count += 1


class _SettingsPage(QWidget):
    """Scrollable page content with a title, description, and flat sections."""

    def __init__(
        self,
        title: str,
        description: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(28, 24, 32, 32)
        self._layout.setSpacing(18)

        title_label = QLabel(title)
        title_label.setProperty("settingsRole", "pageTitle")
        self._layout.addWidget(title_label)

        description_label = QLabel(description)
        description_label.setProperty("settingsRole", "pageDescription")
        description_label.setWordWrap(True)
        self._layout.addWidget(description_label)
        self._layout.addSpacing(4)

    def add_section(self, section: _SettingsSection) -> None:
        self._layout.addWidget(section)

    def finish(self) -> None:
        self._layout.addStretch(1)


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
        self.resize(900, 600)
        self.setMinimumSize(760, 500)
        self.setObjectName("settingsDialog")
        self._repository = repository
        self._runtime_performance_settings = runtime_performance_settings

        self.category_list = QListWidget()
        self.category_list.setObjectName("settingsCategoryList")
        self.category_list.setFixedWidth(184)
        self.category_list.setSpacing(2)
        self.category_list.addItems(("General", "Files", "Performance"))

        self.page_stack = QStackedWidget()
        self.page_stack.setObjectName("settingsPageStack")

        self.dont_show_raw_json_profiles = QCheckBox(
            "Don't Show RAW JSON Profiles"
        )
        self.dont_show_raw_json_profiles.setObjectName(
            "generalDontShowRawJsonProfiles"
        )

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
        self.difference_cache_mib.setMaximumWidth(150)

        self.restart_required_label = QLabel(
            "Changes take effect after restarting PixelScope."
        )
        self.restart_required_label.setObjectName("restartRequiredLabel")
        self.restart_required_label.setProperty("settingsRole", "supportingText")
        self.restart_required_label.setWordWrap(True)

        self.compatibility_label = QLabel()
        self.compatibility_label.setObjectName("settingsCompatibilityLabel")
        self.compatibility_label.setProperty("settingsRole", "compatibility")
        self.compatibility_label.setWordWrap(True)
        self.compatibility_label.hide()

        self.page_stack.addWidget(self._build_general_page())
        self.page_stack.addWidget(self._build_files_page())
        self.page_stack.addWidget(self._build_performance_page())

        self.reset_button = QPushButton("Reset Settings")
        self.reset_button.setObjectName("resetSettingsButton")
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.setObjectName("settingsButtonBox")

        sidebar = QWidget()
        sidebar.setObjectName("settingsSidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(10, 16, 10, 12)
        sidebar_layout.setSpacing(10)
        sidebar_title = QLabel("Settings")
        sidebar_title.setProperty("settingsRole", "sidebarTitle")
        sidebar_layout.addWidget(sidebar_title)
        sidebar_layout.addWidget(self.category_list, 1)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(sidebar)
        body.addWidget(self.page_stack, 1)

        footer_separator = QFrame()
        footer_separator.setObjectName("settingsFooterSeparator")
        footer_separator.setFrameShape(QFrame.Shape.HLine)
        footer_separator.setFrameShadow(QFrame.Shadow.Plain)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(16, 10, 16, 12)
        button_row.addWidget(self.reset_button)
        button_row.addStretch(1)
        button_row.addWidget(self.button_box)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.compatibility_label)
        layout.addLayout(body, 1)
        layout.addWidget(footer_separator)
        layout.addLayout(button_row)

        self._apply_style()

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

    def _build_general_page(self) -> QScrollArea:
        page = _SettingsPage(
            "General",
            "Application-wide preferences for PixelScope behavior.",
        )
        raw_section = _SettingsSection("RAW Profiles")
        raw_section.add_row(
            _SettingRow(
                "RAW JSON confirmation",
                "Skip repeated confirmation when a valid RAW JSON sidecar matches "
                "the source file.",
                self.dont_show_raw_json_profiles,
            )
        )
        page.add_section(raw_section)
        page.finish()
        return self._scrollable_page(page, "generalSettingsPage")

    def _build_files_page(self) -> QScrollArea:
        page = _SettingsPage(
            "Files",
            "Choose optional starting locations for PixelScope file dialogs.",
        )
        locations_section = _SettingsSection(
            "Default Locations",
            "Leave a field blank to keep using the last folder used by PixelScope.",
        )
        locations_section.add_row(
            _SettingRow(
                "Default Open Folder",
                "Starting location for Open Images, Open Folder, and Open RAW. "
                "This does not replace PixelScope's remembered last-used folder.",
                self._directory_editor(
                    self.default_open_directory,
                    self.default_open_browse,
                ),
            )
        )
        locations_section.add_row(
            _SettingRow(
                "Default Export Folder",
                "Starting location for export dialogs. Leave blank to continue "
                "from the last-used folder.",
                self._directory_editor(
                    self.default_export_directory,
                    self.default_export_browse,
                ),
            )
        )
        page.add_section(locations_section)
        page.finish()
        return self._scrollable_page(page, "filesSettingsPage")

    def _build_performance_page(self) -> QScrollArea:
        page = _SettingsPage(
            "Performance",
            "Tune startup performance limits without changing the current session.",
        )
        memory_section = _SettingsSection("Memory")

        cache_control = QWidget()
        cache_layout = QVBoxLayout(cache_control)
        cache_layout.setContentsMargins(0, 0, 0, 0)
        cache_layout.setSpacing(6)
        cache_layout.addWidget(self.difference_cache_mib)
        range_label = QLabel(
            f"Allowed range: {MIN_DIFFERENCE_CACHE_MIB}–"
            f"{MAX_DIFFERENCE_CACHE_MIB} MiB"
        )
        range_label.setObjectName("differenceCacheRangeLabel")
        range_label.setProperty("settingsRole", "supportingText")
        cache_layout.addWidget(range_label)
        cache_layout.addWidget(self.restart_required_label)

        memory_section.add_row(
            _SettingRow(
                "Difference Cache",
                "Memory budget for cached Difference maps. The configured value "
                "is applied on the next PixelScope launch.",
                cache_control,
            )
        )
        page.add_section(memory_section)
        page.finish()
        return self._scrollable_page(page, "performanceSettingsPage")

    @staticmethod
    def _scrollable_page(page: QWidget, object_name: str) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setObjectName(object_name)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setWidget(page)
        return scroll

    @staticmethod
    def _directory_editor(line_edit: QLineEdit, browse_button: QPushButton) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(line_edit, 1)
        layout.addWidget(browse_button)
        return container

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QWidget#settingsSidebar {
                background: palette(alternate-base);
                border-right: 1px solid palette(mid);
            }
            QListWidget#settingsCategoryList {
                background: transparent;
                border: 0;
                outline: 0;
                padding: 0;
            }
            QListWidget#settingsCategoryList::item {
                border-radius: 4px;
                margin: 1px 0;
                padding: 8px 10px;
            }
            QListWidget#settingsCategoryList::item:selected {
                background: palette(highlight);
                color: palette(highlighted-text);
            }
            QLabel[settingsRole="sidebarTitle"] {
                font-weight: 600;
                padding: 0 8px 4px 8px;
            }
            QLabel[settingsRole="pageTitle"] {
                font-size: 18px;
                font-weight: 600;
            }
            QLabel[settingsRole="pageDescription"],
            QLabel[settingsRole="description"],
            QLabel[settingsRole="supportingText"] {
                color: palette(mid);
            }
            QLabel[settingsRole="sectionTitle"] {
                font-size: 14px;
                font-weight: 600;
                padding-top: 4px;
            }
            QLabel[settingsRole="settingTitle"] {
                font-weight: 600;
            }
            QLabel[settingsRole="compatibility"] {
                background: palette(alternate-base);
                border-bottom: 1px solid palette(mid);
                padding: 8px 16px;
            }
            QFrame#settingsRowSeparator,
            QFrame#settingsFooterSeparator {
                color: palette(mid);
            }
            QLineEdit, QSpinBox {
                min-height: 24px;
            }
            QPushButton {
                min-height: 24px;
                padding-left: 10px;
                padding-right: 10px;
            }
            """
        )

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
        self.dont_show_raw_json_profiles.setChecked(
            settings.dont_show_raw_json_profiles
        )
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
