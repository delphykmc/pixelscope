from __future__ import annotations

from PySide6.QtCore import (
    QByteArray,
    QEvent,
    QObject,
    QPointF,
    QRectF,
    QSettings,
    QSize,
    Qt,
    QTimer,
)
from PySide6.QtGui import QColor, QIcon, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QToolButton,
    QWidget,
)

from pixelscope.ui.design_tokens import TOKENS, dock_title_button_style

PLOTS_FLOATING_GEOMETRY_SETTING = "ui/plots_floating_geometry"


def _title_icon(kind: str) -> QIcon:
    """Draw platform-independent dock controls with one consistent visual weight."""

    scale = 2
    pixmap = QPixmap(TOKENS.icon_size * scale, TOKENS.icon_size * scale)
    pixmap.fill(Qt.GlobalColor.transparent)
    pixmap.setDevicePixelRatio(scale)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(QColor(TOKENS.text_primary), 1.5)
    pen.setCapStyle(Qt.PenCapStyle.SquareCap)
    pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    if kind == "float":
        painter.drawRect(QRectF(3.0, 5.0, 8.0, 7.0))
        painter.drawLine(QPointF(6.0, 3.0), QPointF(13.0, 3.0))
        painter.drawLine(QPointF(13.0, 3.0), QPointF(13.0, 10.0))
    elif kind == "dock":
        painter.drawRect(QRectF(2.5, 2.5, 11.0, 11.0))
        painter.drawLine(QPointF(3.5, 10.5), QPointF(12.5, 10.5))
        painter.drawLine(QPointF(6.0, 8.0), QPointF(8.0, 10.0))
        painter.drawLine(QPointF(10.0, 8.0), QPointF(8.0, 10.0))
    elif kind == "maximize":
        painter.drawRect(QRectF(2.5, 2.5, 11.0, 11.0))
        painter.drawLine(QPointF(3.5, 5.0), QPointF(12.5, 5.0))
    elif kind == "restore":
        painter.drawRect(QRectF(2.5, 5.0, 8.5, 8.0))
        painter.drawLine(QPointF(5.0, 3.0), QPointF(13.5, 3.0))
        painter.drawLine(QPointF(13.5, 3.0), QPointF(13.5, 11.0))
        painter.drawLine(QPointF(5.0, 3.0), QPointF(5.0, 5.0))
    elif kind == "hide":
        painter.drawLine(QPointF(3.5, 3.5), QPointF(12.5, 12.5))
        painter.drawLine(QPointF(12.5, 3.5), QPointF(3.5, 12.5))
    else:
        raise ValueError(f"unsupported title icon: {kind}")
    painter.end()
    return QIcon(pixmap)


class PlotsDockTitleBar(QWidget):
    """Compact controls for floating/docking and maximizing/restoring Plots."""

    def __init__(self, dock: QDockWidget) -> None:
        super().__init__(dock)
        self._dock = dock
        self._restore_to_docked = False
        self._restore_area = Qt.DockWidgetArea.BottomDockWidgetArea
        self._settings = QSettings()
        stored_geometry = self._settings.value(PLOTS_FLOATING_GEOMETRY_SETTING)
        self._floating_geometry = (
            QByteArray(stored_geometry)
            if isinstance(stored_geometry, QByteArray | bytes)
            else QByteArray()
        )
        self._restoring_floating_geometry = False
        self.title = QLabel("Plots")
        self.float_button = self._button("float")
        self.maximize_button = self._button("maximize")
        self.close_button = self._button("hide")
        self.float_button.clicked.connect(self._toggle_floating)  # type: ignore[attr-defined]
        self.maximize_button.clicked.connect(self._toggle_maximized)  # type: ignore[attr-defined]
        self.close_button.clicked.connect(dock.hide)  # type: ignore[attr-defined]
        self.close_button.setToolTip("Hide Plots")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(TOKENS.spacing_sm, 0, TOKENS.spacing_xs, 0)
        layout.setSpacing(TOKENS.spacing_xs)
        layout.addWidget(self.title, 1)
        layout.addWidget(self.float_button)
        layout.addWidget(self.maximize_button)
        layout.addWidget(self.close_button)
        self._dock.installEventFilter(self)
        self._dock.topLevelChanged.connect(self._floating_changed)  # type: ignore[attr-defined]
        self.sync(False)

    def _button(self, icon: str) -> QToolButton:
        button = QToolButton(self)
        button.setAutoRaise(True)
        button.setIcon(_title_icon(icon))
        button.setIconSize(QSize(TOKENS.icon_size, TOKENS.icon_size))
        button.setFixedSize(TOKENS.control_height, TOKENS.control_height)
        button.setStyleSheet(dock_title_button_style())
        return button

    def sync(self, floating: bool) -> None:
        self.float_button.setIcon(_title_icon("dock" if floating else "float"))
        self.float_button.setToolTip("Dock Plots" if floating else "Float Plots")
        if not floating and not self._dock.isMaximized():
            self._set_maximize_state(False)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if (
            watched is self._dock
            and event.type() in (QEvent.Type.Move, QEvent.Type.Resize)
            and self._dock.isFloating()
            and not self._dock.isMaximized()
            and not self._restoring_floating_geometry
        ):
            geometry = self._dock.saveGeometry()
            if not geometry.isEmpty():
                self._floating_geometry = geometry
                self._settings.setValue(PLOTS_FLOATING_GEOMETRY_SETTING, geometry)
        return super().eventFilter(watched, event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._dock.isFloating():
            self._toggle_maximized()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _toggle_floating(self) -> None:
        if self._dock.isMaximized():
            self._dock.showNormal()
        self._restore_to_docked = False
        self._dock.setFloating(not self._dock.isFloating())
        self._dock.show()

    def _toggle_maximized(self) -> None:
        maximized = self._dock.isMaximized()
        if maximized:
            self._dock.showNormal()
            if self._restore_to_docked:
                window = self._main_window()
                if window is not None:
                    window.addDockWidget(self._restore_area, self._dock)
                    self._dock.setFloating(False)
                    self._dock.show()
            self._restore_to_docked = False
        else:
            self._restore_to_docked = not self._dock.isFloating()
            window = self._main_window()
            if self._restore_to_docked and window is not None:
                self._restore_area = window.dockWidgetArea(self._dock)
                self._dock.setFloating(True)
            self._dock.showMaximized()
        self._set_maximize_state(not maximized)

    def _floating_changed(self, floating: bool) -> None:
        if not floating or self._floating_geometry.isEmpty():
            return
        self._restoring_floating_geometry = True
        self._dock.restoreGeometry(self._floating_geometry)
        QTimer.singleShot(0, self._finish_geometry_restore)

    def _finish_geometry_restore(self) -> None:
        self._restoring_floating_geometry = False
        if self._dock.isFloating() and not self._dock.isMaximized():
            geometry = self._dock.saveGeometry()
            if not geometry.isEmpty():
                self._floating_geometry = geometry
                self._settings.setValue(PLOTS_FLOATING_GEOMETRY_SETTING, geometry)

    def clear_persisted_geometry(self) -> None:
        """Forget the saved normal floating geometry."""
        self._settings.remove(PLOTS_FLOATING_GEOMETRY_SETTING)
        self._floating_geometry = QByteArray()

    def _main_window(self) -> QMainWindow | None:
        parent = self._dock.parentWidget()
        while parent is not None and not isinstance(parent, QMainWindow):
            parent = parent.parentWidget()
        return parent if isinstance(parent, QMainWindow) else None

    def _set_maximize_state(self, maximized: bool) -> None:
        self.maximize_button.setIcon(_title_icon("restore" if maximized else "maximize"))
        self.maximize_button.setToolTip("Restore Plots" if maximized else "Maximize Plots")
