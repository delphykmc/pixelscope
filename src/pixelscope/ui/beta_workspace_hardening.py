from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QLabel,
    QListWidget,
    QMainWindow,
    QSizePolicy,
    QTabWidget,
    QWidget,
)

from pixelscope.ui.design_tokens import TOKENS
from pixelscope.ui.plots_dock_title import PlotsDockTitleBar
from pixelscope.ui.tile_header import TileHeader

_TILE_HEADER_COMPACT_ENTER_WIDTH = TileHeader.COMPACT_WIDTH
_TILE_HEADER_COMPACT_EXIT_WIDTH = TileHeader.COMPACT_WIDTH + 32
_DISABLED_ICON_COLOR = "#737980"


def tile_header_compact_for_width(*, compact: bool, width: int) -> bool:
    """Return a stable compact-mode decision with resize hysteresis."""

    if compact:
        return width < _TILE_HEADER_COMPACT_EXIT_WIDTH
    return width < _TILE_HEADER_COMPACT_ENTER_WIDTH


def _apply_tile_header_width(header: TileHeader, width: int) -> None:
    compact = tile_header_compact_for_width(compact=header._compact, width=width)
    if compact != header._compact:
        header._compact = compact
        header.meta.setVisible(not compact)
    header._elide_name()


class _TileHeaderResizeFilter(QObject):
    """Keep responsive header visibility from changing geometry at one threshold."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if isinstance(watched, TileHeader) and event.type() == QEvent.Type.Resize:
            resize_event = event
            size = getattr(resize_event, "size", None)
            width = int(size().width()) if callable(size) else watched.width()
            _apply_tile_header_width(watched, width)
            # QWidget.resizeEvent has no additional PixelScope behavior. Consuming
            # it prevents TileHeader's legacy single-threshold layout activation
            # from re-entering the splitter/layout geometry pass.
            return True
        return super().eventFilter(watched, event)


def _set_vertical_policy(widget: QWidget, policy: QSizePolicy.Policy) -> None:
    size_policy = widget.sizePolicy()
    size_policy.setVerticalPolicy(policy)
    widget.setSizePolicy(size_policy)


def _draw_iqa_pixmap(color_name: str) -> QPixmap:
    scale = 2
    logical_size = TOKENS.icon_size
    pixmap = QPixmap(logical_size * scale, logical_size * scale)
    pixmap.fill(Qt.GlobalColor.transparent)
    pixmap.setDevicePixelRatio(scale)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(QColor(color_name), 1.5)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRect(QRectF(2.0, 2.0, 12.0, 12.0))
    painter.drawLine(QPointF(4.0, 11.5), QPointF(4.0, 8.0))
    painter.drawLine(QPointF(7.0, 11.5), QPointF(7.0, 5.5))
    painter.drawLine(QPointF(10.0, 11.5), QPointF(10.0, 7.0))
    painter.drawEllipse(QRectF(10.5, 3.0, 2.0, 2.0))
    painter.end()
    return pixmap


def _iqa_toolbar_icon() -> QIcon:
    icon = QIcon()
    normal = _draw_iqa_pixmap(TOKENS.text_primary)
    active = _draw_iqa_pixmap(TOKENS.accent)
    disabled = _draw_iqa_pixmap(_DISABLED_ICON_COLOR)
    icon.addPixmap(normal, QIcon.Mode.Normal, QIcon.State.Off)
    icon.addPixmap(active, QIcon.Mode.Active, QIcon.State.Off)
    icon.addPixmap(active, QIcon.Mode.Normal, QIcon.State.On)
    icon.addPixmap(active, QIcon.Mode.Active, QIcon.State.On)
    icon.addPixmap(disabled, QIcon.Mode.Disabled, QIcon.State.Off)
    icon.addPixmap(disabled, QIcon.Mode.Disabled, QIcon.State.On)
    return icon


class _WorkspaceDockTopLevelController(QObject):
    """Normalize a floating QDockWidget to a regular native top-level workspace."""

    def __init__(self, dock: QDockWidget, *, docked_title_bar: QWidget | None = None) -> None:
        super().__init__(dock)
        self._dock = dock
        self._docked_title_bar = docked_title_bar
        self._normalizing = False
        dock.topLevelChanged.connect(self._top_level_changed)  # type: ignore[attr-defined]
        if dock.isFloating():
            self._top_level_changed(True)

    def _top_level_changed(self, floating: bool) -> None:
        if floating:
            # Run after QDockWidget and the existing geometry/title controllers
            # have completed their topLevelChanged handlers.
            QTimer.singleShot(0, self._normalize_floating)
            return
        self._restore_docked_title_bar()

    def _normalize_floating(self) -> None:
        if self._normalizing or not self._dock.isFloating():
            return
        self._normalizing = True
        try:
            title_bar = self._dock.titleBarWidget()
            if title_bar is not None:
                self._docked_title_bar = title_bar
                self._dock.setTitleBarWidget(None)

            flags = self._dock.windowFlags()
            flags = (flags & ~Qt.WindowType.WindowType_Mask) | Qt.WindowType.Window
            flags &= ~Qt.WindowType.Tool
            flags &= ~Qt.WindowType.FramelessWindowHint
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
            flags |= (
                Qt.WindowType.WindowTitleHint
                | Qt.WindowType.WindowSystemMenuHint
                | Qt.WindowType.WindowMinimizeButtonHint
                | Qt.WindowType.WindowMaximizeButtonHint
                | Qt.WindowType.WindowCloseButtonHint
            )
            if self._dock.windowFlags() != flags:
                self._dock.setWindowFlags(flags)
            self._dock.show()
            QTimer.singleShot(0, self._detach_transient_parent)
        finally:
            self._normalizing = False

    def _detach_transient_parent(self) -> None:
        if not self._dock.isFloating():
            return
        handle = self._dock.windowHandle()
        if handle is not None and handle.transientParent() is not None:
            handle.setTransientParent(None)

    def _restore_docked_title_bar(self) -> None:
        if self._dock.isFloating():
            return
        title_bar = self._docked_title_bar
        if title_bar is None:
            # IQA installs its title bar lazily on first show. It remains a dock
            # child when native chrome temporarily replaces it while floating.
            child = self._dock.findChild(PlotsDockTitleBar)
            if child is not None:
                title_bar = child
                self._docked_title_bar = child
        if title_bar is not None and self._dock.titleBarWidget() is not title_bar:
            self._dock.setTitleBarWidget(title_bar)
            title_bar.show()


class BetaWorkspaceHardeningController(QObject):
    """Production-only UI geometry/window hardening without new state authority."""

    def __init__(self, window: QMainWindow) -> None:
        super().__init__(window)
        self.window = window
        self._tile_header_filters: list[_TileHeaderResizeFilter] = []
        self._dock_controllers: list[_WorkspaceDockTopLevelController] = []
        self._install_layout_policy()
        self._install_tile_header_hysteresis()
        self._install_workspace_windows()
        self._install_iqa_toolbar_action()

    def _install_layout_policy(self) -> None:
        window = self.window
        main_splitter = getattr(window, "main_splitter", None)
        if main_splitter is not None and main_splitter.count() >= 2:
            sidebar = main_splitter.widget(0)
            presentation = main_splitter.widget(1)
            # Remove the legacy blanket 320 px floor. Child controls now provide
            # the functional minimum, so the sidebar can yield width to Two Image
            # + IQA without clipping controls by fiat.
            sidebar.setMinimumWidth(0)
            main_splitter.setCollapsible(0, False)
            main_splitter.setCollapsible(1, False)
            presentation.setMinimumWidth(0)

        for widget_name in ("document_list", "analysis_tabs"):
            widget = getattr(window, widget_name, None)
            if isinstance(widget, QWidget):
                widget.setMinimumWidth(0)

        workspace = getattr(window, "iqa_workspace", None)
        dock = getattr(window, "iqa_dock", None)
        if isinstance(workspace, QWidget):
            workspace.setMinimumWidth(0)
            workspace_policy = workspace.sizePolicy()
            workspace_policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
            workspace_policy.setVerticalPolicy(QSizePolicy.Policy.Expanding)
            workspace.setSizePolicy(workspace_policy)

            for label_name in (
                "status_label",
                "result_label",
                "dataset_label",
                "trend_label",
                "series_hint",
                "preview_caption",
            ):
                label = getattr(workspace, label_name, None)
                if isinstance(label, QLabel):
                    label.setMinimumWidth(0)
                    label.setWordWrap(True)

            for combo in workspace.findChildren(QComboBox):
                combo.setMinimumWidth(0)
                combo.setSizeAdjustPolicy(
                    QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
                )
                combo_policy = combo.sizePolicy()
                combo_policy.setHorizontalPolicy(QSizePolicy.Policy.Expanding)
                combo.setSizePolicy(combo_policy)

            attribute_filter = getattr(workspace, "attribute_filter", None)
            if isinstance(attribute_filter, QListWidget):
                attribute_filter.setMinimumWidth(0)

            pages = getattr(workspace, "pages", None)
            if isinstance(pages, QTabWidget):
                pages.setMinimumWidth(0)
                pages_policy = pages.sizePolicy()
                pages_policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
                pages.setSizePolicy(pages_policy)

        if isinstance(dock, QDockWidget):
            dock.setMinimumWidth(0)

        # Let the central viewer yield vertical space to a bottom Plots dock.
        # Fixed-height headers/status controls remain fixed; only the large
        # workspace surfaces participate in the flexible allocation.
        for widget_name in (
            "main_splitter",
            "presentation_panel",
            "central_stack",
            "viewer",
            "multi_compare_view",
            "bottom_tabs",
            "bottom_dock",
        ):
            widget = getattr(window, widget_name, None)
            if isinstance(widget, QWidget):
                widget.setMinimumHeight(0)
                _set_vertical_policy(widget, QSizePolicy.Policy.Expanding)

        if isinstance(main_splitter, QWidget):
            _set_vertical_policy(main_splitter, QSizePolicy.Policy.Ignored)

    def _install_tile_header_hysteresis(self) -> None:
        for header in self.window.findChildren(TileHeader):
            resize_filter = _TileHeaderResizeFilter(header)
            header.installEventFilter(resize_filter)
            self._tile_header_filters.append(resize_filter)
            _apply_tile_header_width(header, header.width())

    def _install_workspace_windows(self) -> None:
        plots = getattr(self.window, "bottom_dock", None)
        if isinstance(plots, QDockWidget):
            title_bar = getattr(self.window, "plots_dock_title", None)
            self._dock_controllers.append(
                _WorkspaceDockTopLevelController(
                    plots,
                    docked_title_bar=title_bar if isinstance(title_bar, QWidget) else None,
                )
            )

        iqa = getattr(self.window, "iqa_dock", None)
        if isinstance(iqa, QDockWidget):
            self._dock_controllers.append(_WorkspaceDockTopLevelController(iqa))

    def _install_iqa_toolbar_action(self) -> None:
        toolbar = getattr(self.window, "main_toolbar", None)
        action = getattr(self.window, "iqa_workspace_action", None)
        plots_action = getattr(self.window, "plots_action", None)
        if toolbar is None or action is None or plots_action is None:
            return
        if action in toolbar.actions():
            return
        action.setIcon(_iqa_toolbar_icon())
        action.setIconText("IQA")
        action.setToolTip("Show or hide the IQA workspace")
        toolbar.insertAction(plots_action, action)


def install_beta_workspace_hardening(window: QMainWindow) -> BetaWorkspaceHardeningController:
    """Install Beta layout/window hardening once on the production main window."""

    existing = window.__dict__.get("beta_workspace_hardening_controller")
    if isinstance(existing, BetaWorkspaceHardeningController):
        return existing
    controller = BetaWorkspaceHardeningController(window)
    window.__dict__["beta_workspace_hardening_controller"] = controller
    return controller
