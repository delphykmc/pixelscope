from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QComboBox, QHBoxLayout, QLabel, QWidget

RAW_GAIN_OPTIONS = (1.0, 2.0, 4.0, 8.0, 16.0)


class RawDisplayState(QObject):
    """Application-session-only RAW presentation state."""

    gain_changed = Signal(float)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._gain = 1.0

    @property
    def gain(self) -> float:
        return self._gain

    def set_gain(self, gain: float) -> None:
        value = float(gain)
        if value <= 0:
            raise ValueError("RAW display gain must be greater than zero")
        if value == self._gain:
            return
        self._gain = value
        self.gain_changed.emit(value)

    def reset(self) -> None:
        self.set_gain(1.0)


def raw_display_state() -> RawDisplayState:
    """Return the one RAW display state owned by the current QApplication."""

    app = QApplication.instance()
    if not isinstance(app, QApplication):
        raise RuntimeError("RAW display state requires QApplication")
    attribute_name = "_pixelscope_raw_display_state"
    existing = getattr(app, attribute_name, None)
    if isinstance(existing, RawDisplayState):
        return existing
    state = RawDisplayState(app)
    setattr(app, attribute_name, state)
    return state


def _is_raw_document(document: object) -> bool:
    if document is None:
        return False
    if getattr(document, "raw_profile", None) is not None:
        return True
    source_path = getattr(document, "source_path", None)
    return source_path is not None and str(getattr(source_path, "suffix", "")).casefold() == ".raw"


def install_raw_gain_control(window: Any) -> QComboBox:
    """Install the compact session-local RAW Gain control into the main toolbar."""

    state = raw_display_state()
    state.reset()

    host = QWidget(window.main_toolbar)
    host.setObjectName("RawGainControl")
    layout = QHBoxLayout(host)
    layout.setContentsMargins(4, 0, 4, 0)
    layout.setSpacing(5)

    label = QLabel("RAW Gain", host)
    label.setObjectName("RawGainLabel")
    combo = QComboBox(host)
    combo.setObjectName("RawGainCombo")
    combo.setFixedWidth(70)
    for gain in RAW_GAIN_OPTIONS:
        combo.addItem(f"{gain:g}×", gain)
    combo.setCurrentIndex(0)
    combo.setToolTip(
        "Display-only RAW gain anchored at Black Level. "
        "Native pixel values and analysis results are unchanged."
    )
    label.setToolTip(combo.toolTip())
    layout.addWidget(label)
    layout.addWidget(combo)

    def set_state_from_combo(_index: int) -> None:
        value = combo.currentData()
        if value is not None:
            state.set_gain(float(value))

    def sync_combo(gain: float) -> None:
        index = combo.findData(float(gain))
        if index >= 0 and index != combo.currentIndex():
            combo.blockSignals(True)
            combo.setCurrentIndex(index)
            combo.blockSignals(False)

    def update_enabled(*_args: object) -> None:
        current = window.central_stack.currentWidget()
        documents: list[object] = []
        if current is window.viewer:
            documents = [window.viewer.presented_document]
        elif current is window.multi_compare_view:
            documents = [
                viewer.presented_document for viewer in window.multi_compare_view.visible_viewers
            ]
        enabled = any(_is_raw_document(document) for document in documents)
        label.setEnabled(enabled)
        combo.setEnabled(enabled)

    combo.currentIndexChanged.connect(set_state_from_combo)  # type: ignore[attr-defined]
    state.gain_changed.connect(sync_combo)
    window.central_stack.currentChanged.connect(update_enabled)
    window.document_list.itemSelectionChanged.connect(update_enabled)
    for viewer in [window.viewer, *window.multi_compare_view.viewers]:
        viewer.document_changed.connect(update_enabled)

    window.main_toolbar.addSeparator()
    window.main_toolbar.addWidget(host)
    update_enabled()
    return combo
