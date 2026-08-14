from __future__ import annotations

from contextlib import suppress
from typing import Any

from PySide6.QtCore import QEvent, QObject, Qt, Signal, Slot
from PySide6.QtWidgets import QApplication, QComboBox, QFrame, QHBoxLayout, QLabel, QWidget

from pixelscope.ui.design_tokens import TOKENS

DISPLAY_GAIN_OPTIONS = (1.0, 2.0, 4.0, 8.0, 16.0)


class DisplayGainState(QObject):
    """Application-session-only viewer presentation gain state."""

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
            raise ValueError("display gain must be greater than zero")
        if value == self._gain:
            return
        self._gain = value
        self.gain_changed.emit(value)

    def reset(self) -> None:
        self.set_gain(1.0)


def display_gain_state() -> DisplayGainState:
    """Return the one Display Gain state owned by the current QApplication."""

    app = QApplication.instance()
    if not isinstance(app, QApplication):
        raise RuntimeError("Display Gain state requires QApplication")
    attribute_name = "_pixelscope_display_gain_state"
    existing = getattr(app, attribute_name, None)
    if isinstance(existing, DisplayGainState):
        return existing
    state = DisplayGainState(app)
    setattr(app, attribute_name, state)
    return state


class _DisplayGainComboBox(QComboBox):
    """Display Gain selector whose state subscription follows Qt object lifetime."""

    def __init__(self, state: DisplayGainState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self.currentIndexChanged.connect(self._set_state_from_index)  # type: ignore[attr-defined]
        state.gain_changed.connect(self._sync_gain)

    @Slot(int)
    def _set_state_from_index(self, _index: int) -> None:
        value = self.currentData()
        if value is not None:
            self._state.set_gain(float(value))

    @Slot(float)
    def _sync_gain(self, gain: float) -> None:
        index = self.findData(float(gain))
        if index >= 0 and index != self.currentIndex():
            self.blockSignals(True)
            self.setCurrentIndex(index)
            self.blockSignals(False)


class _DisplayGainWindowLifetime(QObject):
    """Disarm app-global Display Gain callbacks when one MainWindow closes."""

    def __init__(self, window: Any, state: DisplayGainState, combo: _DisplayGainComboBox) -> None:
        super().__init__(window)
        self.window = window
        self.state = state
        self.combo = combo
        self._shutting_down = False
        window.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched is self.window and event.type() == QEvent.Type.Close:
            self.shutdown()
        return super().eventFilter(watched, event)

    def shutdown(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        with suppress(RuntimeError):
            self.window.removeEventFilter(self)
        with suppress(RuntimeError, TypeError):
            self.state.gain_changed.disconnect(self.combo._sync_gain)
        for viewer in [self.window.viewer, *self.window.multi_compare_view.viewers]:
            callback = getattr(viewer, "_display_gain_changed", None)
            if callable(callback):
                with suppress(RuntimeError, TypeError):
                    self.state.gain_changed.disconnect(callback)
            cancel = getattr(viewer, "_cancel_display_preview", None)
            if callable(cancel):
                cancel()


def is_display_gain_capable(document: object) -> bool:
    """Return whether a document has a viewer presentation owned by Display Gain."""

    if document is None:
        return False
    channel_layout = str(getattr(document, "channel_layout", "")).upper()
    if channel_layout == "DIFFERENCE":
        return False
    if channel_layout in {"GRAY", "RGB", "RGBA"}:
        return True
    if channel_layout.startswith("CHANNEL_"):
        return True
    return channel_layout == "BAYER" and getattr(document, "raw_profile", None) is not None


def _insert_before_stretch(layout: QHBoxLayout, widget: QWidget) -> None:
    stretch_index = layout.count()
    for index in range(layout.count()):
        item = layout.itemAt(index)
        if item is not None and item.spacerItem() is not None:
            stretch_index = index
            break
    layout.insertWidget(stretch_index, widget)


def install_display_gain_control(window: Any) -> QComboBox:
    """Install Display Gain inline with the image-view command controls."""

    existing = getattr(window, "_display_gain_control", None)
    if isinstance(existing, _DisplayGainComboBox):
        return existing

    state = display_gain_state()
    state.reset()

    presentation_host = getattr(window, "presentation_controls", None)
    host_parent = (
        presentation_host if isinstance(presentation_host, QWidget) else window.main_toolbar
    )
    host = QWidget(host_parent)
    host.setObjectName("DisplayGainControl")
    layout = QHBoxLayout(host)
    layout.setContentsMargins(4, 0, 4, 0)
    layout.setSpacing(TOKENS.spacing_sm)

    label = QLabel("Display Gain", host)
    label.setObjectName("DisplayGainLabel")
    combo = _DisplayGainComboBox(state, host)
    combo.setObjectName("DisplayGainCombo")
    combo.setFixedWidth(70)
    combo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    for gain in DISPLAY_GAIN_OPTIONS:
        combo.addItem(f"{gain:g}×", gain)
    combo.setCurrentIndex(0)
    combo.setToolTip(
        "Viewer-only digital display gain. RAW is Black-anchored; ordinary images "
        "use a zero anchor. Native pixel values and analysis results are unchanged."
    )
    label.setToolTip(combo.toolTip())
    layout.addWidget(label)
    layout.addWidget(combo)

    def update_enabled(*_args: object) -> None:
        current = window.central_stack.currentWidget()
        documents: list[object] = []
        if current is window.viewer:
            documents = [window.viewer.presented_document]
        elif current is window.multi_compare_view:
            documents = [
                viewer.presented_document for viewer in window.multi_compare_view.visible_viewers
            ]
        enabled = any(is_display_gain_capable(document) for document in documents)
        label.setEnabled(enabled)
        combo.setEnabled(enabled)

    window.central_stack.currentChanged.connect(update_enabled)
    window.document_list.itemSelectionChanged.connect(update_enabled)
    for viewer in [window.viewer, *window.multi_compare_view.viewers]:
        viewer.document_changed.connect(update_enabled)

    presentation_layout = getattr(window, "presentation_controls_layout", None)
    if (
        isinstance(presentation_host, QWidget)
        and isinstance(presentation_layout, QHBoxLayout)
    ):
        separator = QFrame(presentation_host)
        separator.setObjectName("displayGainSeparator")
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Plain)
        separator.setFixedHeight(TOKENS.control_height - 4)
        separator.setStyleSheet(f"QFrame {{ color: {TOKENS.border}; }}")
        _insert_before_stretch(presentation_layout, separator)
        _insert_before_stretch(presentation_layout, host)
    else:
        window.main_toolbar.addSeparator()
        window.main_toolbar.addWidget(host)
    window._display_gain_control = combo
    window._display_gain_window_lifetime = _DisplayGainWindowLifetime(window, state, combo)
    update_enabled()
    return combo
