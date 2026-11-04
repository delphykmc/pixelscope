from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from pixelscope.io.yuv_profile import YuvProfile
from pixelscope.ui.input_profile_library import ProfileLibraryControls


class YuvOpenDialog(QDialog):
    """Minimal explicit WP-C1 interpretation dialog for ambiguous `.yuv` files."""

    GENERIC_RAW = "GENERIC_RAW"

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self.setWindowTitle("YUV profile")
        self._source_path: Path | None = None
        self._profile_name: str | None = None
        self._file_size_state = "unverified"

        self.width_box = QSpinBox()
        self.width_box.setRange(1, 1_000_000)
        self.width_box.setValue(1920)
        self.height_box = QSpinBox()
        self.height_box.setRange(1, 1_000_000)
        self.height_box.setValue(1080)
        self.layout_kind = QComboBox()
        self.layout_kind.addItem("YUV420 · Y + interleaved UV", "YUV420")
        self.layout_kind.addItem("YUV422 · Y + interleaved UV", "YUV422")
        self.layout_kind.addItem("YUV444 · Y + interleaved UV", "YUV444")
        self.layout_kind.addItem("Generic RAW profile…", self.GENERIC_RAW)
        self.fixed_contract = QLabel("8-bit · UV order · BT.601 Full · tightly packed")
        self.fixed_contract.setWordWrap(True)
        self.file_size = QLabel("Expected size —")
        self.file_size.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        form = QFormLayout()
        form.addRow("Width", self.width_box)
        form.addRow("Height", self.height_box)
        form.addRow("Interpretation", self.layout_kind)
        form.addRow("Contract", self.fixed_contract)
        form.addRow("File size", self.file_size)
        self.interpretation_summary = QLabel()
        self.interpretation_summary.setWordWrap(True)
        self.interpretation_summary.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        form.addRow("Native layout", self.interpretation_summary)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_validated)  # type: ignore[attr-defined]
        buttons.rejected.connect(self.reject)  # type: ignore[attr-defined]

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        self.import_button = QPushButton("Load YUV JSON…")
        layout.addWidget(self.import_button)
        self.profile_library_controls = ProfileLibraryControls(
            "yuv",
            self.profile,
            self.set_profile,
            parent=self,  # type: ignore[arg-type]
        )
        layout.addWidget(self.profile_library_controls)
        layout.addWidget(buttons)

        self.import_button.clicked.connect(self._import_profile_json)  # type: ignore[attr-defined]
        self.width_box.valueChanged.connect(self._update_file_size)  # type: ignore[attr-defined]
        self.height_box.valueChanged.connect(self._update_file_size)  # type: ignore[attr-defined]
        self.layout_kind.currentIndexChanged.connect(  # type: ignore[attr-defined]
            self._update_file_size
        )
        self._update_file_size()

    def set_source_path(self, path: str | Path) -> None:
        self._source_path = Path(path)
        self._update_file_size()

    def set_profile(self, profile: YuvProfile) -> None:
        self._profile_name = profile.name
        self.width_box.setValue(profile.width)
        self.height_box.setValue(profile.height)
        index = self.layout_kind.findData(profile.channel_layout)
        if index >= 0:
            self.layout_kind.setCurrentIndex(index)
        self._update_file_size()

    def uses_generic_raw(self) -> bool:
        return str(self.layout_kind.currentData()) == self.GENERIC_RAW

    def profile(self) -> YuvProfile:
        if self.uses_generic_raw():
            raise ValueError("Generic RAW selection does not define a YUV profile")
        return YuvProfile(
            name=(
                self._profile_name
                or (self._source_path.stem if self._source_path is not None else "native_yuv")
            ),
            width=self.width_box.value(),
            height=self.height_box.value(),
            channel_layout=self.layout_kind.currentData(),
        )

    def _import_profile_json(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load YUV profile", "", "JSON (*.json)")
        if not path:
            return
        try:
            profile = YuvProfile.load_json(path)
        except (OSError, ValidationError, ValueError) as exc:
            QMessageBox.warning(self, "Cannot load YUV profile", str(exc))
            return
        self.profile_library_controls.origin = "Explicit JSON"
        self.set_profile(profile)

    def _accept_validated(self) -> None:
        if self.uses_generic_raw():
            self.accept()
            return
        try:
            profile = self.profile()
        except (ValidationError, ValueError) as exc:
            QMessageBox.warning(self, "Invalid YUV profile", str(exc))
            return
        if self._source_path is not None and self._source_path.is_file():
            actual = self._source_path.stat().st_size
            if actual != profile.expected_file_size:
                QMessageBox.warning(
                    self,
                    "YUV file size mismatch",
                    f"Expected {profile.expected_file_size} bytes but file has {actual} bytes.",
                )
                return
        if not self.profile_library_controls.library.read_only:
            self.profile_library_controls.library.record_recent(
                profile, self.profile_library_controls.origin
            )
        self.accept()

    @property
    def file_size_state(self) -> str:
        return self._file_size_state

    def _update_file_size(self) -> None:
        source = self._source_path.name if self._source_path is not None else "Not selected"
        origin = self.profile_library_controls.origin
        if self.uses_generic_raw():
            self._file_size_state = "unverified"
            self.fixed_contract.setText("Use the existing generic RAW profile workflow")
            self.file_size.setText("Expected size —")
            self.interpretation_summary.setText(
                f"Source: {source} | Generic RAW requires explicit interpretation."
            )
            return
        self.fixed_contract.setText("8-bit · UV order · BT.601 Full · tightly packed")
        try:
            profile = self.profile()
        except (ValidationError, ValueError) as exc:
            self._file_size_state = "unsupported"
            self.file_size.setText(f"Unsupported interpretation: {exc}")
            self.interpretation_summary.setText(
                f"Source: {source} | Invalid Native YUV interpretation"
            )
            return
        expected = profile.expected_file_size
        self.interpretation_summary.setText(
            f"Source: {source} | Origin: {origin} | Profile: {profile.name}\n"
            f"{profile.width}×{profile.height}, {profile.channel_layout}, "
            "Y-first / interleaved UV, tightly packed uint8; "
            "Y/U/V values remain native. Size matching cannot verify interpretation."
        )
        if self._source_path is None:
            self._file_size_state = "unverified"
            self.file_size.setText(f"Expected {expected:,} bytes · actual unverified")
            return
        try:
            actual = self._source_path.stat().st_size
        except OSError as exc:
            self._file_size_state = "unverified"
            self.file_size.setText(f"Expected {expected:,} bytes · cannot stat file: {exc}")
            return
        if actual == expected:
            self._file_size_state = "match"
            state = "match"
        elif actual < expected:
            self._file_size_state = "truncated"
            state = f"truncated by {expected - actual:,} bytes (reject)"
        else:
            self._file_size_state = "trailing"
            state = f"{actual - expected:,} trailing bytes (reject for native YUV)"
        self.file_size.setText(f"Expected {expected:,} bytes · actual {actual:,} bytes · {state}")
