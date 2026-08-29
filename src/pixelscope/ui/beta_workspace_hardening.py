from __future__ import annotations

import ctypes
import sys
from typing import cast

from PySide6.QtCore import QObject, QPointF, QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QWindow
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QLabel,
    QListWidget,
    QMainWindow,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QWidget,
)

from pixelscope.ui.design_tokens import TOKENS
from pixelscope.ui.plots_dock_title import PlotsDockTitleBar

_DISABLED_ICON_COLOR = "#737980"


def _set_vertical_policy(widget: QWidget, policy: QSizePolicy.Policy) -> None:
    size_policy = widget.sizePolicy()
    size_policy.setVerticalPolicy(policy)
    widget.setSizePolicy(size_policy)


def _apply_windows_native_workspace_frame(dock: QDockWidget) -> None:
    """Promote a floating dock's native Windows frame without changing Qt topology."""

    if sys.platform != "win32":
        return
    windll = getattr(ctypes, "windll", None)
    if windll is None:
        return

    from ctypes import wintypes

    try:
        user32 = windll.user32
        get_window_long = user32.GetWindowLongPtrW
        set_window_long = user32.SetWindowLongPtrW
        set_window_pos = user32.SetWindowPos
    except AttributeError:
        return

    get_window_long.argtypes = [wintypes.HWND, ctypes.c_int]
    get_window_long.restype = ctypes.c_ssize_t
    set_window_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    set_window_long.restype = ctypes.c_ssize_t
    set_window_pos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    set_window_pos.restype = wintypes.BOOL

    hwnd = wintypes.HWND(int(dock.winId()))
    gwl_style = -16
    gwl_exstyle = -20
    ws_caption = 0x00C00000
    ws_sysmenu = 0x00080000
    ws_thickframe = 0x00040000
    ws_minimizebox = 0x00020000
    ws_maximizebox = 0x00010000
    ws_ex_toolwindow = 0x00000080
    ws_ex_appwindow = 0x00040000
    swp_nosize = 0x0001
    swp_nomove = 0x0002
    swp_nozorder = 0x0004
    swp_noactivate = 0x0010
    swp_framechanged = 0x0020

    style = int(get_window_long(hwnd, gwl_style))
    ex_style = int(get_window_long(hwnd, gwl_exstyle))
    promoted_style = (
        style
        | ws_caption
        | ws_sysmenu
        | ws_thickframe
        | ws_minimizebox
        | ws_maximizebox
    )
    promoted_ex_style = (ex_style & ~ws_ex_toolwindow) | ws_ex_appwindow
    if promoted_style != style:
        set_window_long(hwnd, gwl_style, promoted_style)
    if promoted_ex_style != ex_style:
        set_window_long(hwnd, gwl_exstyle, promoted_ex_style)
    if promoted_style != style or promoted_ex_style != ex_style:
        set_window_pos(
            hwnd,
            wintypes.HWND(),
            0,
            0,
            0,
            0,
            swp_nosize
            | swp_nomove
            | swp_nozorder
            | swp_noactivate
            | swp_framechanged,
        )


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
    """Give floating QDockWidgets native chrome without changing dock topology."""

    def __init__(self, dock: QDockWidget, *, docked_title_bar: QWidget | None = None) -> None:
        super().__init__(dock)
        self._dock = dock
        self._docked_title_bar = docked_title_bar
        self._normalizing = False
        dock.topLevelChanged.connect(self._top_level_changed)  # type: ignore[attr-defined]
        dock.visibilityChanged.connect(self._visibility_changed)  # type: ignore[attr-defined]
        if dock.isFloating():
            self._top_level_changed(True)

    def _top_level_changed(self, floating: bool) -> None:
        if floating:
            # Run after QDockWidget and the existing geometry/title controllers
            # have completed their topLevelChanged handlers.
            QTimer.singleShot(0, self._normalize_floating)
            return
        self._restore_docked_title_bar()

    def _visibility_changed(self, visible: bool) -> None:
        if visible and self._dock.isFloating():
            # IQA installs its custom dock title lazily on first show. Normalize
            # again after that show so floating mode always returns to native chrome.
            QTimer.singleShot(0, self._normalize_floating)

    def _normalize_floating(self) -> None:
        if self._normalizing or not self._dock.isFloating():
            return
        self._normalizing = True
        try:
            was_hidden = self._dock.isHidden()
            title_bar = self._dock.titleBarWidget()
            if isinstance(title_bar, PlotsDockTitleBar):
                self._docked_title_bar = title_bar
                # Qt documents nullptr as the way to restore the default/native
                # dock title. PySide's type stub does not currently expose None.
                self._dock.setTitleBarWidget(cast(QWidget, None))

            # QDockWidget remains the dock/floating topology authority. The native
            # Windows frame is adjusted only after the dock is already floating so
            # drag-to-dock discovery and QMainWindow save/restore stay intact.
            if not was_hidden:
                QTimer.singleShot(0, self._finish_native_floating)
        finally:
            self._normalizing = False

    def _finish_native_floating(self) -> None:
        if not self._dock.isFloating() or self._dock.isHidden():
            return
        handle = self._dock.windowHandle()
        if handle is not None and handle.transientParent() is not None:
            # QWindow::setTransientParent accepts a null pointer to clear the
            # relation, although the PySide stub currently types it as non-null.
            handle.setTransientParent(cast(QWindow, None))
        _apply_windows_native_workspace_frame(self._dock)

    def _restore_docked_title_bar(self) -> None:
        if self._dock.isFloating():
            return
        title_bar = self._docked_title_bar or PlotsDockTitleBar.controller_for_dock(self._dock)
        if title_bar is not None:
            self._docked_title_bar = title_bar
        if title_bar is not None and self._dock.titleBarWidget() is not title_bar:
            self._dock.setTitleBarWidget(title_bar)
            title_bar.show()


class BetaWorkspaceHardeningController(QObject):
    """Production-only UI geometry/window hardening without new state authority."""

    def __init__(self, window: QMainWindow) -> None:
        super().__init__(window)
        self.window = window
        self._dock_controllers: list[_WorkspaceDockTopLevelController] = []
        self._install_layout_policy()
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
            workspace.setMinimumHeight(0)
            workspace_policy = workspace.sizePolicy()
            workspace_policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
            workspace_policy.setVerticalPolicy(QSizePolicy.Policy.Ignored)
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
                pages.setMinimumHeight(0)
                pages_policy = pages.sizePolicy()
                pages_policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
                pages_policy.setVerticalPolicy(QSizePolicy.Policy.Ignored)
                pages.setSizePolicy(pages_policy)

            # IQA's detail/tree/preview surfaces are inspectable regions, not
            # application-wide height floors. Let their local splitters compress
            # them so a bottom Plots dock can take useful vertical space.
            for widget_name in (
                "overview_page",
                "scene_page",
                "overview_chart_panel",
                "overview_detail_panel",
                "overview_plot",
                "hierarchy",
                "scene_trend_plot",
                "preview_scroll",
            ):
                child = getattr(workspace, widget_name, None)
                if isinstance(child, QWidget):
                    child.setMinimumHeight(0)
                    _set_vertical_policy(child, QSizePolicy.Policy.Ignored)

            for splitter_name in ("overview_splitter", "scene_splitter"):
                splitter = getattr(workspace, splitter_name, None)
                if isinstance(splitter, QSplitter):
                    splitter.setMinimumHeight(0)
                    _set_vertical_policy(splitter, QSizePolicy.Policy.Ignored)
                    splitter.setChildrenCollapsible(True)
                    for index in range(splitter.count()):
                        splitter.setCollapsible(index, True)

        if isinstance(dock, QDockWidget):
            dock.setMinimumWidth(0)

        # Give the bottom workspace both lower corners. Otherwise a left/right IQA
        # dock owns the full side height and its minimum can cap Plots growth.
        window.setCorner(
            Qt.Corner.BottomLeftCorner,
            Qt.DockWidgetArea.BottomDockWidgetArea,
        )
        window.setCorner(
            Qt.Corner.BottomRightCorner,
            Qt.DockWidgetArea.BottomDockWidgetArea,
        )

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
