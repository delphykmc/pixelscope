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
IQA_FLOATING_GEOMETRY_SETTING = "ui/iqa_floating_geometry"
_CONTROLLER_ATTRIBUTE = "_pixelscope_workspace_title_controller"


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
    """PixelScope-styled controls that preserve QDockWidget-native drag semantics."""

    _known_geometry_settings = {
        PLOTS_FLOATING_GEOMETRY_SETTING,
        IQA_FLOATING_GEOMETRY_SETTING,
    }

    @classmethod
    def register_geometry_setting(cls, setting: str) -> None:
        """Register a workspace dock geometry key so Reset clears it even while hidden."""

        cls._known_geometry_settings.add(setting)

    @classmethod
    def controller_for_dock(cls, dock: QDockWidget) -> PlotsDockTitleBar | None:
        """Return the retained title controller for either docked or floating state."""

        title_bar = dock.titleBarWidget()
        if isinstance(title_bar, cls):
            return title_bar
        retained = dock.__dict__.get(_CONTROLLER_ATTRIBUTE)
        if isinstance(retained, cls):
            return retained
        child = dock.findChild(cls)
        return child if isinstance(child, cls) else None

    def __init__(
        self,
        dock: QDockWidget,
        *,
        title: str = "Plots",
        geometry_setting: str = PLOTS_FLOATING_GEOMETRY_SETTING,
    ) -> None:
        super().__init__(dock)
        self._dock = dock
        self._panel_title = title
        self._geometry_setting = geometry_setting
        self.register_geometry_setting(geometry_setting)
        dock.__dict__[_CONTROLLER_ATTRIBUTE] = self
        self._restore_to_docked = False
        self._restore_area = Qt.DockWidgetArea.BottomDockWidgetArea
        self._settings = QSettings()
        stored_geometry = self._settings.value(self._geometry_setting)
        self._floating_geometry = (
            QByteArray(stored_geometry)
            if isinstance(stored_geometry, QByteArray | bytes)
            else QByteArray()
        )
        self._restoring_floating_geometry = False

        self.setObjectName("workspaceDockTitle")
        self.setStyleSheet(
            f"QWidget#workspaceDockTitle {{ background: {TOKENS.title_background}; "
            f"border-bottom: 1px solid {TOKENS.border}; }}"
            f"QLabel {{ color: {TOKENS.text_primary}; }}"
        )
        self.title = QLabel(title)
        self.float_button = self._button("float")
        self.maximize_button = self._button("maximize")
        self.close_button = self._button("hide")
        self.float_button.clicked.connect(self._toggle_floating)  # type: ignore[attr-defined]
        self.maximize_button.clicked.connect(self._toggle_maximized)  # type: ignore[attr-defined]
        self.close_button.clicked.connect(dock.hide)  # type: ignore[attr-defined]
        self.close_button.setToolTip(f"Hide {self._panel_title}")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(TOKENS.spacing_sm, 0, TOKENS.spacing_xs, 0)
        layout.setSpacing(TOKENS.spacing_xs)
        layout.addWidget(self.title, 1)
        layout.addWidget(self.float_button)
        layout.addWidget(self.maximize_button)
        layout.addWidget(self.close_button)
        self._dock.installEventFilter(self)
        self._dock.topLevelChanged.connect(self._floating_changed)  # type: ignore[attr-defined]
        self._remember_dock_area()
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
        self.float_button.setToolTip(
            f"Dock {self._panel_title}" if floating else f"Float {self._panel_title}"
        )
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
                self._settings.setValue(self._geometry_setting, geometry)
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        # Qt documents that unhandled custom-title mouse events must be ignored
        # so QDockWidget itself can own move/dock discovery and docking previews.
        event.ignore()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        event.ignore()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        event.ignore()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._dock.isFloating():
            if self._dock.isMaximized():
                self._dock.showNormal()
            self._restore_to_docked = False
            self._dock.setFloating(False)
            self._dock.show()
            event.accept()
            return
        # Docked double-click remains Qt-owned, including its standard float behavior.
        event.ignore()

    def _toggle_floating(self) -> None:
        if self._dock.isMaximized():
            self._dock.showNormal()
        if not self._dock.isFloating():
            self._remember_dock_area()
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
            if self._restore_to_docked:
                self._remember_dock_area()
                window = self._main_window()
                if window is not None:
                    self._dock.setFloating(True)
            self._dock.showMaximized()
        self._set_maximize_state(not maximized)

    def _floating_changed(self, floating: bool) -> None:
        self.sync(floating)
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
                self._settings.setValue(self._geometry_setting, geometry)

    def clear_persisted_geometry(self) -> None:
        """Clear registered workspace dock geometry and normalize managed floating docks."""

        for setting in self._known_geometry_settings:
            self._settings.remove(setting)
        window = self._main_window()
        if window is None:
            self._floating_geometry = QByteArray()
            return
        for dock in window.findChildren(QDockWidget):
            title_bar = self.controller_for_dock(dock)
            managed = isinstance(title_bar, PlotsDockTitleBar) or dock.objectName() in {
                "plotsPanel",
                "iqaWorkspaceDock",
            }
            if not managed:
                continue
            if isinstance(title_bar, PlotsDockTitleBar):
                title_bar._floating_geometry = QByteArray()
                title_bar._settings.remove(title_bar._geometry_setting)
                title_bar._remember_dock_area()
            if not dock.isFloating():
                continue
            was_hidden = dock.isHidden()
            area = (
                title_bar._restore_area
                if isinstance(title_bar, PlotsDockTitleBar)
                else _default_dock_area(dock)
            )
            window.addDockWidget(area, dock)
            dock.setFloating(False)
            dock.setVisible(not was_hidden)

    def _remember_dock_area(self) -> None:
        window = self._main_window()
        if window is None:
            return
        area = window.dockWidgetArea(self._dock)
        if area != Qt.DockWidgetArea.NoDockWidgetArea:
            self._restore_area = area

    def _main_window(self) -> QMainWindow | None:
        parent = self._dock.parentWidget()
        while parent is not None and not isinstance(parent, QMainWindow):
            parent = parent.parentWidget()
        return parent if isinstance(parent, QMainWindow) else None

    def _set_maximize_state(self, maximized: bool) -> None:
        self.maximize_button.setIcon(_title_icon("restore" if maximized else "maximize"))
        action = "Restore" if maximized else "Maximize"
        self.maximize_button.setToolTip(f"{action} {self._panel_title}")


def _default_dock_area(dock: QDockWidget) -> Qt.DockWidgetArea:
    allowed = dock.allowedAreas()
    for area in (
        Qt.DockWidgetArea.RightDockWidgetArea,
        Qt.DockWidgetArea.LeftDockWidgetArea,
        Qt.DockWidgetArea.BottomDockWidgetArea,
        Qt.DockWidgetArea.TopDockWidgetArea,
    ):
        if allowed & area:
            return area
    return Qt.DockWidgetArea.RightDockWidgetArea