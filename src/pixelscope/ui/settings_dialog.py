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
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from pixelscope.app.settings import (
    DIFFERENCE_CACHE_STEP_MIB,
    MAX_DIFFERENCE_CACHE_MIB,
    MAX_DIFFERENCE_GAIN,
    MAX_DIFFERENCE_THRESHOLD,
    MAX_SOURCE_RESIDENCY_MIB,
    MIN_DIFFERENCE_CACHE_MIB,
    MIN_DIFFERENCE_GAIN,
    MIN_DIFFERENCE_THRESHOLD,
    MIN_SOURCE_RESIDENCY_MIB,
    SOURCE_RESIDENCY_STEP_MIB,
    ApplicationSettings,
    SettingsRepository,
)
from pixelscope.core.performance_settings import (
    MIB,
    PerformanceSettings,
    detect_physical_memory_bytes,
    memory_budgets_fit_physical_memory,
    recommended_combined_memory_limit_bytes,
)


class _SettingRow(QWidget):
    """Flat setting row with consistent title, description, and control spacing."""

    def __init__(
        self,
        title: str,
        description: str,
        control: QWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(7)

        title_label = QLabel(title)
        title_label.setProperty("settingsRole", "settingTitle")
        layout.addWidget(title_label)

        description_label = QLabel(description)
        description_label.setProperty("settingsRole", "description")
        description_label.setWordWrap(True)
        layout.addWidget(description_label)
        layout.addWidget(control)


class _SettingsSection(QWidget):
    """Named group of related setting rows with a clear visual hierarchy."""

    def __init__(
        self,
        title: str,
        description: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        title_label = QLabel(title)
        title_label.setProperty("settingsRole", "sectionTitle")
        self._layout.addWidget(title_label)

        if description:
            description_label = QLabel(description)
            description_label.setProperty("settingsRole", "sectionDescription")
            description_label.setWordWrap(True)
            self._layout.addWidget(description_label)

        self._layout.addSpacing(8)

    def add_row(self, row: _SettingRow) -> None:
        self._layout.addWidget(row)

    def add_widget(self, widget: QWidget) -> None:
        self._layout.addWidget(widget)


class _SettingsPage(QWidget):
    """Scrollable page content with a restrained VS Code-style hierarchy."""

    def __init__(
        self,
        title: str,
        description: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        content = QWidget()
        content.setObjectName("settingsPageContent")
        content.setMaximumWidth(880)
        self._layout = QVBoxLayout(content)
        self._layout.setContentsMargins(30, 26, 32, 36)
        self._layout.setSpacing(22)

        title_label = QLabel(title)
        title_label.setProperty("settingsRole", "pageTitle")
        self._layout.addWidget(title_label)

        description_label = QLabel(description)
        description_label.setProperty("settingsRole", "pageDescription")
        description_label.setWordWrap(True)
        self._layout.addWidget(description_label)

        outer_layout.addWidget(content, 0, Qt.AlignmentFlag.AlignTop)
        outer_layout.addStretch(1)

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
        physical_memory_bytes: int | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(960, 620)
        self.setMinimumSize(0, 0)
        self.setObjectName("settingsDialog")
        self._repository = repository
        self._runtime_performance_settings = runtime_performance_settings
        self._physical_memory_bytes = (
            detect_physical_memory_bytes()
            if physical_memory_bytes is None
            else physical_memory_bytes
        )

        self.category_list = QListWidget()
        self.category_list.setObjectName("settingsCategoryList")
        self.category_list.setFixedWidth(184)
        self.category_list.setSpacing(2)
        self.category_list.setAlternatingRowColors(False)
        self.category_list.addItems(("General", "Files", "Performance"))

        self.page_stack = QStackedWidget()
        self.page_stack.setObjectName("settingsPageStack")

        self.dont_show_raw_json_profiles = QCheckBox("Don't Show RAW JSON Profiles")
        self.dont_show_raw_json_profiles.setObjectName("generalDontShowRawJsonProfiles")
        self.require_exact_raw_file_size = QCheckBox("Require Exact RAW File Size")
        self.require_exact_raw_file_size.setObjectName("generalRequireExactRawFileSize")

        self.difference_threshold = QSpinBox()
        self.difference_threshold.setObjectName("generalDifferenceThreshold")
        self.difference_threshold.setRange(
            MIN_DIFFERENCE_THRESHOLD,
            MAX_DIFFERENCE_THRESHOLD,
        )
        self.difference_threshold.setKeyboardTracking(False)
        self.difference_threshold.setMaximumWidth(160)

        self.difference_gain = QSpinBox()
        self.difference_gain.setObjectName("generalDifferenceGain")
        self.difference_gain.setRange(MIN_DIFFERENCE_GAIN, MAX_DIFFERENCE_GAIN)
        self.difference_gain.setKeyboardTracking(False)
        self.difference_gain.setMaximumWidth(160)

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
        self.difference_cache_mib.setSingleStep(DIFFERENCE_CACHE_STEP_MIB)
        self.difference_cache_mib.setMaximumWidth(132)

        self.difference_cache_slider = QSlider(Qt.Orientation.Horizontal)
        self.difference_cache_slider.setObjectName("performanceDifferenceCacheSlider")
        self.difference_cache_slider.setRange(
            MIN_DIFFERENCE_CACHE_MIB // DIFFERENCE_CACHE_STEP_MIB,
            MAX_DIFFERENCE_CACHE_MIB // DIFFERENCE_CACHE_STEP_MIB,
        )
        self.difference_cache_slider.setSingleStep(1)
        self.difference_cache_slider.setPageStep(4)
        self.difference_cache_slider.setTickInterval(4)
        self.difference_cache_slider.setTickPosition(QSlider.TickPosition.TicksBelow)

        self.source_residency_mib = QSpinBox()
        self.source_residency_mib.setObjectName("performanceSourceResidencyMiB")
        self.source_residency_mib.setRange(
            MIN_SOURCE_RESIDENCY_MIB,
            MAX_SOURCE_RESIDENCY_MIB,
        )
        self.source_residency_mib.setSuffix(" MiB")
        self.source_residency_mib.setKeyboardTracking(False)
        self.source_residency_mib.setSingleStep(SOURCE_RESIDENCY_STEP_MIB)
        self.source_residency_mib.setMaximumWidth(132)

        self.source_residency_slider = QSlider(Qt.Orientation.Horizontal)
        self.source_residency_slider.setObjectName("performanceSourceResidencySlider")
        self.source_residency_slider.setRange(
            MIN_SOURCE_RESIDENCY_MIB // SOURCE_RESIDENCY_STEP_MIB,
            MAX_SOURCE_RESIDENCY_MIB // SOURCE_RESIDENCY_STEP_MIB,
        )
        self.source_residency_slider.setSingleStep(1)
        self.source_residency_slider.setPageStep(4)
        self.source_residency_slider.setTickInterval(4)
        self.source_residency_slider.setTickPosition(QSlider.TickPosition.TicksBelow)

        self.preload_enabled = QCheckBox("Preload Next Folder Position")
        self.preload_enabled.setObjectName("performancePreloadEnabled")

        self.restart_required_label = QLabel("Changes take effect after restarting PixelScope.")
        self.restart_required_label.setObjectName("restartRequiredLabel")
        self.restart_required_label.setProperty("settingsRole", "supportingText")
        self.restart_required_label.setWordWrap(True)

        self.memory_budget_summary = QLabel()
        self.memory_budget_summary.setObjectName("memoryBudgetSummary")
        self.memory_budget_summary.setProperty("settingsRole", "supportingText")
        self.memory_budget_summary.setWordWrap(True)

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
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.setObjectName("settingsButtonBox")

        sidebar = QWidget()
        sidebar.setObjectName("settingsSidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 16, 12, 12)
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

        footer = QWidget()
        footer.setObjectName("settingsFooter")
        button_row = QHBoxLayout(footer)
        button_row.setContentsMargins(16, 10, 16, 12)
        button_row.setSpacing(8)
        button_row.addWidget(self.reset_button)
        button_row.addStretch(1)
        button_row.addWidget(self.button_box)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.compatibility_label)
        layout.addLayout(body, 1)
        layout.addWidget(footer)

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
        self.difference_cache_slider.valueChanged.connect(  # type: ignore[attr-defined]
            self._difference_cache_slider_changed
        )
        self.difference_cache_mib.valueChanged.connect(  # type: ignore[attr-defined]
            self._difference_cache_spin_changed
        )
        self.source_residency_slider.valueChanged.connect(  # type: ignore[attr-defined]
            self._source_residency_slider_changed
        )
        self.source_residency_mib.valueChanged.connect(  # type: ignore[attr-defined]
            self._source_residency_spin_changed
        )
        self.preload_enabled.toggled.connect(  # type: ignore[attr-defined]
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
            "Configure application-wide preferences for PixelScope behavior.",
        )

        raw_section = _SettingsSection("RAW Profiles")
        raw_section.add_row(
            _SettingRow(
                "RAW JSON Confirmation",
                "Skip repeated confirmation when a valid RAW JSON sidecar matches "
                "the source file.",
                self.dont_show_raw_json_profiles,
            )
        )
        raw_section.add_row(
            _SettingRow(
                "RAW File Size Validation",
                "Require the RAW file size to exactly match the bytes required by "
                "the selected profile. When disabled, larger files are allowed; "
                "too-small files are always rejected.",
                self.require_exact_raw_file_size,
            )
        )
        page.add_section(raw_section)

        difference_section = _SettingsSection(
            "Difference Defaults",
            "Set the initial display controls used by Difference analysis.",
        )
        difference_section.add_row(
            _SettingRow(
                "Threshold",
                "Default threshold used by the Difference mask display. Changes "
                "apply immediately to the current Difference panel.",
                self.difference_threshold,
            )
        )
        difference_section.add_row(
            _SettingRow(
                "Gain",
                "Default amplification used by the Absolute Difference display. "
                "Changes apply immediately to the current Difference panel.",
                self.difference_gain,
            )
        )
        page.add_section(difference_section)
        page.finish()
        return self._scrollable_page(page, "generalSettingsPage")

    def _build_files_page(self) -> QScrollArea:
        page = _SettingsPage(
            "Files",
            "Choose optional starting locations for PixelScope file dialogs.",
        )
        locations_section = _SettingsSection(
            "Default Locations",
            "Leave fields blank to keep using PixelScope's remembered " "last-used folder.",
        )
        locations_section.add_row(
            _SettingRow(
                "Default Open Folder",
                "Starting location for Open Images, Open Folder, and Open RAW.",
                self._directory_editor(
                    self.default_open_directory,
                    self.default_open_browse,
                ),
            )
        )
        locations_section.add_row(
            _SettingRow(
                "Default Export Folder",
                "Starting location for export dialogs such as Statistics CSV.",
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
        memory_section = _SettingsSection(
            "Memory",
            "Control memory budgets used by analysis features.",
        )

        memory_section.add_row(
            _SettingRow(
                "Decoded Source Memory",
                "Memory budget for decoded source image arrays kept resident for "
                "fast navigation. The green residency indicator in Files reflects "
                "this source residency. 256 MiB is roughly 8 UHD working images "
                "with headroom; actual capacity depends on dtype and channels.",
                self._memory_budget_control(
                    self.source_residency_slider,
                    self.source_residency_mib,
                    MIN_SOURCE_RESIDENCY_MIB,
                    MAX_SOURCE_RESIDENCY_MIB,
                ),
            )
        )
        memory_section.add_row(
            _SettingRow(
                "Difference Map Cache",
                "Memory budget for cached Difference maps. 128 MiB is roughly 4 UHD "
                "maps with headroom. Adjust in 64 MiB steps; changes apply on the "
                "next PixelScope launch.",
                self._memory_budget_control(
                    self.difference_cache_slider,
                    self.difference_cache_mib,
                    MIN_DIFFERENCE_CACHE_MIB,
                    MAX_DIFFERENCE_CACHE_MIB,
                ),
            )
        )
        memory_section.add_widget(self.memory_budget_summary)
        memory_section.add_widget(self.restart_required_label)
        page.add_section(memory_section)
        preload_section = _SettingsSection("Background Loading")
        preload_section.add_row(
            _SettingRow(
                "Preload Next Folder Position",
                "Decode the next registered folder position in the background after "
                "interactive loading becomes idle. Preloading is limited to one "
                "position ahead and always yields to normal image loading.",
                self.preload_enabled,
            )
        )
        page.add_section(preload_section)
        page.finish()
        return self._scrollable_page(page, "performanceSettingsPage")

    @staticmethod
    def _scrollable_page(page: QWidget, object_name: str) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setObjectName(object_name)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        return scroll

    @staticmethod
    def _directory_editor(line_edit: QLineEdit, browse_button: QPushButton) -> QWidget:
        container = QWidget()
        container.setMaximumWidth(700)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(line_edit, 1)
        layout.addWidget(browse_button)
        return container

    @staticmethod
    def _memory_budget_control(
        slider: QSlider,
        spin_box: QSpinBox,
        minimum_mib: int,
        maximum_mib: int,
    ) -> QWidget:
        control = QWidget()
        control.setMaximumWidth(680)
        layout = QVBoxLayout(control)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        value_row = QHBoxLayout()
        value_row.setContentsMargins(0, 0, 0, 0)
        value_row.setSpacing(12)
        value_row.addWidget(slider, 1)
        value_row.addWidget(spin_box)
        layout.addLayout(value_row)

        endpoint_row = QHBoxLayout()
        endpoint_row.setContentsMargins(0, 0, 144, 0)
        minimum_label = QLabel(f"{minimum_mib} MiB")
        minimum_label.setProperty("settingsRole", "supportingText")
        maximum_label = QLabel(f"{maximum_mib} MiB")
        maximum_label.setProperty("settingsRole", "supportingText")
        endpoint_row.addWidget(minimum_label)
        endpoint_row.addStretch(1)
        endpoint_row.addWidget(maximum_label)
        layout.addLayout(endpoint_row)
        return control

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QDialog#settingsDialog {
                background: palette(base);
            }
            QWidget#settingsSidebar {
                background: palette(alternate-base);
                border-right: 1px solid palette(mid);
            }
            QWidget#settingsFooter {
                background: palette(alternate-base);
                border-top: 1px solid palette(mid);
            }
            QListWidget#settingsCategoryList {
                background: transparent;
                border: 0;
                outline: 0;
                padding: 0;
                color: palette(text);
            }
            QListWidget#settingsCategoryList::item {
                border-radius: 4px;
                margin: 1px 0;
                padding: 7px 10px;
                color: palette(text);
            }
            QListWidget#settingsCategoryList::item:selected {
                background: palette(highlight);
                color: palette(highlighted-text);
            }
            QWidget#settingsPageContent {
                background: transparent;
            }
            QLabel {
                color: palette(text);
            }
            QLabel[settingsRole="sidebarTitle"] {
                font-size: 13px;
                font-weight: 600;
                padding: 0 8px 4px 8px;
            }
            QLabel[settingsRole="pageTitle"] {
                font-size: 20px;
                font-weight: 600;
            }
            QLabel[settingsRole="pageDescription"] {
                font-size: 12px;
                font-weight: 400;
                color: palette(text);
            }
            QLabel[settingsRole="sectionTitle"] {
                font-size: 15px;
                font-weight: 600;
                color: palette(text);
                padding-top: 2px;
            }
            QLabel[settingsRole="sectionDescription"] {
                font-size: 12px;
                font-weight: 400;
                color: palette(text);
                padding-top: 3px;
            }
            QLabel[settingsRole="settingTitle"] {
                font-size: 13px;
                font-weight: 600;
            }
            QLabel[settingsRole="description"],
            QLabel[settingsRole="supportingText"] {
                font-size: 12px;
                font-weight: 400;
                color: palette(text);
            }
            QLabel[settingsRole="compatibility"] {
                background: palette(alternate-base);
                color: palette(text);
                border-bottom: 1px solid palette(mid);
                padding: 8px 16px;
            }
            QLineEdit,
            QSpinBox {
                min-height: 28px;
                padding-left: 8px;
                padding-right: 8px;
                color: palette(text);
                background: palette(base);
                selection-background-color: palette(highlight);
                selection-color: palette(highlighted-text);
            }
            QSlider#performanceDifferenceCacheSlider,
            QSlider#performanceSourceResidencySlider {
                min-height: 30px;
            }
            QPushButton {
                min-height: 28px;
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
            source_residency_mib=self.source_residency_mib.value(),
            default_open_directory=self.default_open_directory.text().strip(),
            default_export_directory=self.default_export_directory.text().strip(),
            require_exact_raw_file_size=self.require_exact_raw_file_size.isChecked(),
            difference_threshold=self.difference_threshold.value(),
            difference_gain=self.difference_gain.value(),
            preload_enabled=self.preload_enabled.isChecked(),
        )

    def set_settings(self, settings: ApplicationSettings) -> None:
        self.dont_show_raw_json_profiles.setChecked(settings.dont_show_raw_json_profiles)
        self.require_exact_raw_file_size.setChecked(settings.require_exact_raw_file_size)
        self.difference_threshold.setValue(settings.difference_threshold)
        self.difference_gain.setValue(settings.difference_gain)
        self.default_open_directory.setText(settings.default_open_directory)
        self.default_export_directory.setText(settings.default_export_directory)
        self.difference_cache_mib.setValue(settings.difference_cache_mib)
        self.source_residency_mib.setValue(settings.source_residency_mib)
        self.preload_enabled.setChecked(settings.preload_enabled)
        self._sync_difference_cache_slider(settings.difference_cache_mib)
        self._sync_source_residency_slider(settings.source_residency_mib)
        self._update_restart_required()

    def _save(self) -> None:
        requested = self.settings()
        if not memory_budgets_fit_physical_memory(
            requested.source_residency_mib * MIB,
            requested.difference_cache_mib * MIB,
            self._physical_memory_bytes,
        ):
            total_mib = requested.source_residency_mib + requested.difference_cache_mib
            physical_mib = (
                self._physical_memory_bytes // MIB if self._physical_memory_bytes is not None else 0
            )
            allowed_bytes = recommended_combined_memory_limit_bytes(self._physical_memory_bytes)
            allowed_mib = allowed_bytes // MIB if allowed_bytes is not None else 0
            QMessageBox.warning(
                self,
                "Memory budget too high",
                f"The combined image-memory budget ({total_mib} MiB) exceeds the "
                f"recommended machine limit ({allowed_mib} MiB, 50% of the "
                f"detected {physical_mib} MiB physical RAM). The values were not "
                "saved. Reduce either budget and select Save again. This limit is "
                "a conservative configuration guard, not an out-of-memory guarantee.",
            )
            return
        settings = self._repository.save(requested)
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

    def _difference_cache_slider_changed(self, slider_value: int) -> None:
        requested_mib = slider_value * DIFFERENCE_CACHE_STEP_MIB
        if self.difference_cache_mib.value() != requested_mib:
            self.difference_cache_mib.setValue(requested_mib)
        else:
            self._update_restart_required()

    def _difference_cache_spin_changed(self, value: int) -> None:
        self._sync_difference_cache_slider(value)
        self._update_restart_required()

    def _sync_difference_cache_slider(self, value_mib: int) -> None:
        slider_value = round(value_mib / DIFFERENCE_CACHE_STEP_MIB)
        slider_value = max(
            self.difference_cache_slider.minimum(),
            min(self.difference_cache_slider.maximum(), slider_value),
        )
        if self.difference_cache_slider.value() == slider_value:
            return
        was_blocked = self.difference_cache_slider.blockSignals(True)
        self.difference_cache_slider.setValue(slider_value)
        self.difference_cache_slider.blockSignals(was_blocked)

    def _source_residency_slider_changed(self, slider_value: int) -> None:
        requested_mib = slider_value * SOURCE_RESIDENCY_STEP_MIB
        if self.source_residency_mib.value() != requested_mib:
            self.source_residency_mib.setValue(requested_mib)
        else:
            self._update_restart_required()

    def _source_residency_spin_changed(self, value: int) -> None:
        self._sync_source_residency_slider(value)
        self._update_restart_required()

    def _sync_source_residency_slider(self, value_mib: int) -> None:
        slider_value = round(value_mib / SOURCE_RESIDENCY_STEP_MIB)
        slider_value = max(
            self.source_residency_slider.minimum(),
            min(self.source_residency_slider.maximum(), slider_value),
        )
        if self.source_residency_slider.value() == slider_value:
            return
        was_blocked = self.source_residency_slider.blockSignals(True)
        self.source_residency_slider.setValue(slider_value)
        self.source_residency_slider.blockSignals(was_blocked)

    def _update_restart_required(self) -> None:
        requested_bytes = self.difference_cache_mib.value() * MIB
        combined_mib = self.difference_cache_mib.value() + self.source_residency_mib.value()
        if self._physical_memory_bytes is None:
            physical_text = "Machine limit unavailable; product bounds apply"
        else:
            allowed_bytes = recommended_combined_memory_limit_bytes(self._physical_memory_bytes)
            assert allowed_bytes is not None
            physical_text = (
                f"Recommended limit: {allowed_bytes // MIB} MiB "
                f"(50% of {self._physical_memory_bytes // MIB} MiB RAM)"
            )
        self.memory_budget_summary.setText(
            f"Combined image budget: {combined_mib} MiB  ·  {physical_text}"
        )
        self.restart_required_label.setVisible(
            requested_bytes != self._runtime_performance_settings.difference_cache_bytes
            or self.source_residency_mib.value() * MIB
            != self._runtime_performance_settings.source_residency_bytes
            or self.preload_enabled.isChecked()
            != self._runtime_performance_settings.preload_enabled
        )

    def _set_future_schema_read_only(self, version: int | None) -> None:
        self.dont_show_raw_json_profiles.setEnabled(False)
        self.require_exact_raw_file_size.setEnabled(False)
        self.difference_threshold.setEnabled(False)
        self.difference_gain.setEnabled(False)
        self.default_open_directory.setEnabled(False)
        self.default_open_browse.setEnabled(False)
        self.default_export_directory.setEnabled(False)
        self.default_export_browse.setEnabled(False)
        self.difference_cache_mib.setEnabled(False)
        self.difference_cache_slider.setEnabled(False)
        self.source_residency_mib.setEnabled(False)
        self.source_residency_slider.setEnabled(False)
        self.preload_enabled.setEnabled(False)
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
