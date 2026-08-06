from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLayout,
    QSizePolicy,
    QToolButton,
    QWidget,
)

from pixelscope.core.image_document import ImageDocument
from pixelscope.ui.design_tokens import TOKENS, tile_header_style
from pixelscope.ui.toolbar_icons import toolbar_icon


class TileHeader(QWidget):
    focus_requested = Signal()
    navigation_requested = Signal(str)
    COMPACT_WIDTH = 480

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("tileHeader")
        self.setFixedHeight(32)
        self.setMinimumWidth(0)
        self.setStyleSheet(tile_header_style())
        self._compat_text = ""
        self._full_name = ""
        self._display_name = ""
        self._navigation_count = 0
        self._compact = False

        self.badge = QLabel("1")
        self.badge.setObjectName("slotBadge")
        self.name = QLabel()
        self.name.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.name.setMinimumWidth(0)
        self.name.setToolTip("")
        self.meta = QLabel()
        self.meta.setObjectName("tileMeta")
        self.meta.setMinimumWidth(0)
        self.meta.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        self.zoom = QLabel("—")
        self.zoom.setObjectName("tileMeta")
        self.navigation = QWidget()
        self.navigation_layout = QHBoxLayout(self.navigation)
        self.navigation_layout.setContentsMargins(0, 0, 0, 0)
        self.navigation_layout.setSpacing(TOKENS.spacing_xs)
        self.navigation.hide()
        self.focus = QToolButton()
        self.focus.setObjectName("focusPin")
        self.focus.setIcon(toolbar_icon("pin"))
        self.focus.setIconSize(QSize(TOKENS.icon_size, TOKENS.icon_size))
        self.focus.setCheckable(True)
        self.focus.setToolTip("Pin to first tile")
        self.focus.setAutoRaise(True)
        self.focus.setFixedSize(TOKENS.control_height, TOKENS.control_height)
        self.focus.hide()
        self.focus.clicked.connect(self.focus_requested)  # type: ignore[attr-defined]
        layout = QHBoxLayout(self)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        layout.setContentsMargins(
            TOKENS.spacing_sm,
            TOKENS.spacing_xs,
            TOKENS.spacing_xs,
            TOKENS.spacing_xs,
        )
        layout.setSpacing(TOKENS.spacing_sm)
        layout.addWidget(self.badge)
        layout.addWidget(self.navigation)
        layout.addWidget(self.name, 1)
        layout.addWidget(self.meta)
        layout.addWidget(self.zoom)
        layout.addWidget(self.focus)

    @property
    def compact(self) -> bool:
        return self._compact

    def set_document(
        self,
        document: ImageDocument | None,
        slot: int = 1,
        role: str = "",
        compat_text: str = "",
    ) -> None:
        self._compat_text = compat_text
        self.badge.setText(role or str(slot))
        self.badge.setVisible(self._navigation_count <= 1)
        if document is None:
            self._full_name = ""
            self._display_name = ""
            self.name.clear()
            self.name.setToolTip("")
            self.meta.clear()
            self.zoom.setText("—")
            return
        self._display_name = document.display_name
        self._full_name = (
            f"{document.source_path.parent.name} / {document.display_name}"
            if document.source_path is not None
            else document.display_name
        )
        self.name.setToolTip(str(document.source_path or document.display_name))
        shape = document.shape
        resolution = f"{shape[1]}×{shape[0]}" if len(shape) >= 2 else "—"
        file_format = (document.source_path or Path(document.display_name)).suffix.upper().lstrip(
            "."
        ) or document.channel_layout
        self.meta.setText(
            f"{resolution}  {file_format} · {document.channel_layout} · "
            f"{document.bit_depth}-bit"
        )
        self._update_responsive_mode()

    def set_zoom(self, percent: float | None) -> None:
        self.zoom.setText("—" if percent is None else f"{percent:.0f}%")

    def set_focus(self, focused: bool) -> None:
        self.focus.blockSignals(True)
        self.focus.setChecked(focused)
        self.focus.blockSignals(False)
        self.focus.setAutoRaise(not focused)
        self.focus.setToolTip("First tile is pinned" if focused else "Pin to first tile")

    def set_focus_control_visible(self, visible: bool) -> None:
        self.focus.setVisible(visible)
        self._elide_name()

    def set_navigation_items(
        self,
        items: list[tuple[str, str, str]],
        current_key: str,
    ) -> None:
        while self.navigation_layout.count():
            item = self.navigation_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for key, label, tooltip in items:
            button = QToolButton()
            button.setText(label)
            button.setToolTip(tooltip)
            button.setCheckable(True)
            button.setChecked(key == current_key)
            button.setAutoRaise(key != current_key)
            button.clicked.connect(  # type: ignore[attr-defined]
                lambda _checked=False, selected_key=key: self.navigation_requested.emit(
                    selected_key
                )
            )
            self.navigation_layout.addWidget(button)
        self._navigation_count = len(items)
        self.badge.setVisible(len(items) <= 1)
        self.navigation.setVisible(len(items) > 1)
        self._elide_name()

    def text(self) -> str:
        """Compatibility accessor retained for clients that used the old QLabel."""

        return self._compat_text

    def setText(self, text: str) -> None:  # noqa: N802
        self._compat_text = text
        self._full_name = text
        self._display_name = text
        self._elide_name()

    def clear(self) -> None:
        self.set_document(None)

    def resizeEvent(self, event: object) -> None:  # noqa: N802
        super().resizeEvent(event)  # type: ignore[arg-type]
        size = getattr(event, "size", None)
        event_width = size().width() if callable(size) else self.width()
        self._update_responsive_mode(event_width)

    def _update_responsive_mode(self, available_width: int | None = None) -> None:
        width = self.width() if available_width is None else available_width
        compact = width < self.COMPACT_WIDTH
        if compact != self._compact:
            self._compact = compact
            self.meta.setVisible(not compact)
            layout = self.layout()
            if layout is not None:
                layout.activate()
        self._elide_name()

    def _elide_name(self) -> None:
        width = max(40, self.name.width())
        source = self._display_name if self._compact else self._full_name
        self.name.setText(
            QFontMetrics(self.name.font()).elidedText(
                source,
                Qt.TextElideMode.ElideMiddle,
                width,
            )
        )
