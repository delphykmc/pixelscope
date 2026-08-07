from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
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
        self._repository = repository
        self._runtime_performance_settings = runtime_performance_settings

        self.dont_show_raw_json_profiles = QCheckBox("Don't Show RAW JSON Profiles")
        self.dont_show_raw_json_profiles.setObjectName("generalDontShowRawJsonProfiles")

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

        general_group = QGroupBox("General")
        general_layout = QVBoxLayout(general_group)
        general_layout.addWidget(self.dont_show_raw_json_profiles)

        performance_group = QGroupBox("Performance")
        performance_layout = QFormLayout(performance_group)
        performance_layout.addRow("Difference Cache", self.difference_cache_mib)
        range_label = QLabel(
            f"Allowed range: {MIN_DIFFERENCE_CACHE_MIB}–{MAX_DIFFERENCE_CACHE_MIB} MiB"
        )
        range_label.setObjectName("differenceCacheRangeLabel")
        performance_layout.addRow("", range_label)
        performance_layout.addRow("", self.restart_required_label)

        self.reset_button = QPushButton("Reset Settings")
        self.reset_button.setObjectName("resetSettingsButton")
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.setObjectName("settingsButtonBox")

        button_row = QHBoxLayout()
        button_row.addWidget(self.reset_button)
        button_row.addStretch(1)
        button_row.addWidget(self.button_box)

        layout = QVBoxLayout(self)
        layout.addWidget(general_group)
        layout.addWidget(performance_group)
        layout.addLayout(button_row)

        self.difference_cache_mib.valueChanged.connect(  # type: ignore[attr-defined]
            self._update_restart_required
        )
        self.button_box.accepted.connect(self._save)  # type: ignore[attr-defined]
        self.button_box.rejected.connect(self.reject)  # type: ignore[attr-defined]
        self.reset_button.clicked.connect(self._reset)  # type: ignore[attr-defined]

        self.set_settings(initial_settings)
        if repository.is_read_only_compatibility_mode:
            self._set_future_schema_read_only(repository.future_schema_version)

    @property
    def restart_required(self) -> bool:
        return not self.restart_required_label.isHidden()

    def settings(self) -> ApplicationSettings:
        return ApplicationSettings(
            dont_show_raw_json_profiles=self.dont_show_raw_json_profiles.isChecked(),
            difference_cache_mib=self.difference_cache_mib.value(),
        )

    def set_settings(self, settings: ApplicationSettings) -> None:
        self.dont_show_raw_json_profiles.setChecked(settings.dont_show_raw_json_profiles)
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

    def _update_restart_required(self, _value: int | None = None) -> None:
        requested_bytes = self.difference_cache_mib.value() * MIB
        self.restart_required_label.setVisible(
            requested_bytes != self._runtime_performance_settings.difference_cache_bytes
        )

    def _set_future_schema_read_only(self, version: int | None) -> None:
        self.dont_show_raw_json_profiles.setEnabled(False)
        self.difference_cache_mib.setEnabled(False)
        self.reset_button.setEnabled(False)
        save_button = self.button_box.button(QDialogButtonBox.StandardButton.Save)
        if save_button is not None:
            save_button.setEnabled(False)
        self.restart_required_label.setText(
            "Settings were created by a newer PixelScope schema"
            + (f" ({version})." if version is not None else ".")
        )
        self.restart_required_label.setVisible(True)
