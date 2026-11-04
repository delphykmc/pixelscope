"""W06 workspace-only presets over the existing QMainWindow/Dock/Splitter authority.

No source, selection, pair, ROI, numerical analysis or viewer state is stored here.
QMainWindow remains the sole owner of docks and the legacy ui/* settings.
"""

from __future__ import annotations

import weakref
from enum import Enum

from PySide6.QtCore import QByteArray, QEvent, QObject, QRect, QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSplitter,
    QToolBar,
    QWidget,
)

from pixelscope.ui.design_tokens import TOKENS


class WorkspacePreset(str, Enum):
    COMPARE = "Compare"
    ANALYZE = "Analyze"
    REVIEW = "Review"


WORKSPACE_PRESET_SETTING = "ui/workspace_preset"
_WORKSPACE_LAYOUT_ROOT = "ui/workspace_layouts/v1"
_MAX_QT_STATE_BYTES = 1024 * 1024


def _stored_bytes(settings: QSettings, key: str) -> QByteArray | None:
    value = settings.value(key)
    if not isinstance(value, QByteArray | bytes):
        return None
    result = QByteArray(value)
    if result.isEmpty() or result.size() > _MAX_QT_STATE_BYTES:
        return None
    return result


def _screen_recover(widget: QWidget) -> bool:
    """Only relocate a *fully* off-screen native window in logical screen coordinates."""

    available = [
        screen.availableGeometry()
        for screen in QGuiApplication.screens()
        if screen.availableGeometry().isValid()
    ]
    if not available:
        return False
    frame = widget.frameGeometry()
    if any(frame.intersects(rect) for rect in available):
        return False
    primary = QGuiApplication.primaryScreen()
    target = primary.availableGeometry() if primary is not None else available[0]
    width = min(max(1, frame.width()), target.width())
    height = min(max(1, frame.height()), target.height())
    x = target.x() + max(0, (target.width() - width) // 2)
    y = target.y() + max(0, (target.height() - height) // 2)
    widget.setGeometry(QRect(x, y, width, height))
    return True


class WorkspacePresetController(QObject):
    """Qt-owned, layout-only state; comparison presentation remains W05-owned."""

    def __init__(self, window: QMainWindow) -> None:
        super().__init__(window)
        self._window_ref = weakref.ref(window)
        self._settings = getattr(window, "settings", QSettings())
        self._saving = False
        self._applying = False
        self._quiescing = False
        self._capture_timer = QTimer(self)
        self._capture_timer.setSingleShot(True)
        self._capture_timer.timeout.connect(self._save_current)  # type: ignore[attr-defined]
        self._recover_timer = QTimer(self)
        self._recover_timer.setSingleShot(True)
        self._recover_timer.timeout.connect(self._recover_windows)  # type: ignore[attr-defined]

        stored_name = self._settings.value(WORKSPACE_PRESET_SETTING)
        try:
            self._preset = WorkspacePreset(str(stored_name))
            restore_selected = True
        except ValueError:
            self._preset = WorkspacePreset.COMPARE
            restore_selected = False

        self.selector = self._install_selector(window)
        self.selector.setCurrentIndex(self.selector.findData(self._preset.value))
        self.selector.currentIndexChanged.connect(self._choose)  # type: ignore[attr-defined]

        for name in ("main_splitter", "sidebar_splitter"):
            splitter = getattr(window, name, None)
            if isinstance(splitter, QSplitter):
                splitter.splitterMoved.connect(self._layout_changed)  # type: ignore[attr-defined]
        dock = getattr(window, "bottom_dock", None)
        if isinstance(dock, QDockWidget):
            dock.visibilityChanged.connect(self._layout_changed)  # type: ignore[attr-defined]
            dock.topLevelChanged.connect(self._dock_changed)  # type: ignore[attr-defined]
            dock.installEventFilter(self)
        window.installEventFilter(self)
        action_map = getattr(window, "action_map", {})
        reset = action_map.get("Reset Workspace Layout")
        if isinstance(reset, QAction):
            # MainWindow's existing reset slot was connected first.
            reset.triggered.connect(self._reset_after_main_window)  # type: ignore[attr-defined]
        self._install_recent_entry(window)
        if restore_selected:
            self._apply_preset(self._preset, prefer_saved=True)
        elif not (
            self._settings.contains("ui/main_splitter")
            or self._settings.contains("ui/sidebar_splitter")
            or self._settings.contains("ui/dock_state")
        ):
            # Fresh install: establish Compare's Files/Viewer ratio. Existing
            # pre-W06 users keep their legacy layout until an explicit switch.
            self._apply_preset(WorkspacePreset.COMPARE, prefer_saved=False)
        self._recover_timer.start(0)

    @property
    def preset(self) -> WorkspacePreset:
        return self._preset

    @property
    def window(self) -> QMainWindow:
        window = self._window_ref()
        if window is None:
            raise RuntimeError("Workspace owner was destroyed")
        return window

    @staticmethod
    def _install_selector(window: QMainWindow) -> QComboBox:
        toolbar = getattr(window, "main_toolbar", None)
        if not isinstance(toolbar, QToolBar):
            raise RuntimeError("Workspace preset requires the existing main toolbar")
        original_first = toolbar.actions()[0] if toolbar.actions() else None
        action_map = getattr(window, "action_map", {})
        open_images = action_map.get("Open Images...")
        if isinstance(open_images, QAction) and original_first is not None:
            # Reuse the existing File QAction and Ctrl+O; never clone it.
            open_images.setIconText("Open")
            open_images.setToolTip("Open Images (Ctrl+O); folders and Recent are in File")
            toolbar.insertAction(original_first, open_images)
            toolbar.insertSeparator(original_first)

        group = QWidget(toolbar)
        group.setObjectName("workspacePresetControl")
        row = QHBoxLayout(group)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(TOKENS.spacing_xs)
        caption = QLabel("Workspace", group)
        caption.setAccessibleName("Workspace layout preset")
        row.addWidget(caption)
        selector = QComboBox(group)
        selector.setObjectName("workspacePresetCombo")
        selector.setAccessibleName("Workspace layout preset")
        selector.setToolTip(
            "Compare: files and images; Analyze: statistics and plots; "
            "Review: inspection layout (Findings arrive with W09). "
            "Independent of Original 2/4 and A/B/Diff."
        )
        for preset in WorkspacePreset:
            selector.addItem(preset.value, preset.value)
        selector.setFixedHeight(TOKENS.control_height)
        selector.setMinimumWidth(0)
        selector.setMaximumWidth(max(110, selector.fontMetrics().horizontalAdvance("Analyze") + 42))
        row.addWidget(selector)
        if original_first is None:
            toolbar.addWidget(group)
        else:
            toolbar.insertWidget(original_first, group)
            toolbar.insertSeparator(original_first)
        window.__dict__["workspace_preset_control"] = group
        return selector

    @staticmethod
    def _install_recent_entry(window: QMainWindow) -> None:
        empty = getattr(window, "empty_workspace", None)
        recent = getattr(window, "recent_entries_controller", None)
        button = getattr(empty, "open_recent_button", None)
        if button is None or recent is None:
            return
        from PySide6.QtWidgets import QMenu

        menu = QMenu(button)
        for name in ("images_menu", "folders_menu", "sessions_menu"):
            entry = getattr(recent, name, None)
            if isinstance(entry, QMenu):
                menu.addMenu(entry)
        if menu.actions():
            button.setMenu(menu)
            button.setVisible(True)

    def _prefix(self, preset: WorkspacePreset) -> str:
        return f"{_WORKSPACE_LAYOUT_ROOT}/{preset.value.lower()}"

    def _choose(self, _index: int) -> None:
        if self._quiescing:
            return
        try:
            selected = WorkspacePreset(str(self.selector.currentData()))
        except ValueError:
            return
        self.select(selected)

    def select(self, preset: WorkspacePreset) -> None:
        """Explicit layout switch; never invokes a comparison/render/analysis API."""

        if self._quiescing or preset is self._preset:
            return
        self._capture_timer.stop()
        self._save_current()
        self._preset = preset
        self._settings.setValue(WORKSPACE_PRESET_SETTING, preset.value)
        self.selector.blockSignals(True)
        self.selector.setCurrentIndex(self.selector.findData(preset.value))
        self.selector.blockSignals(False)
        self._apply_preset(preset, prefer_saved=True)
        if preset is WorkspacePreset.REVIEW:
            self.window.statusBar().showMessage(
                "Review workspace: Findings and persistence will be added in W09", 5000
            )

    def _save_current(self) -> None:
        if self._quiescing or self._applying or self._saving:
            return
        window = self.window
        main = getattr(window, "main_splitter", None)
        sidebar = getattr(window, "sidebar_splitter", None)
        dock = getattr(window, "bottom_dock", None)
        if not (
            isinstance(main, QSplitter)
            and isinstance(sidebar, QSplitter)
            and isinstance(dock, QDockWidget)
        ):
            return
        self._saving = True
        try:
            root = self._prefix(self._preset)
            self._settings.setValue(f"{root}/dock_state", window.saveState())
            self._settings.setValue(f"{root}/main_splitter", main.saveState())
            self._settings.setValue(f"{root}/sidebar_splitter", sidebar.saveState())
            self._settings.setValue(f"{root}/plots_visible", not dock.isHidden())
            if dock.isFloating() and not dock.isHidden():
                self._settings.setValue(f"{root}/floating_geometry", dock.saveGeometry())
        finally:
            self._saving = False

    def _apply_preset(self, preset: WorkspacePreset, *, prefer_saved: bool) -> None:
        self._capture_timer.stop()
        self._applying = True
        try:
            if not prefer_saved or not self._restore_saved(preset):
                self._apply_default(preset)
        finally:
            self._applying = False
        self._recover_timer.start(0)

    def _restore_saved(self, preset: WorkspacePreset) -> bool:
        root = self._prefix(preset)
        dock_state = _stored_bytes(self._settings, f"{root}/dock_state")
        main_state = _stored_bytes(self._settings, f"{root}/main_splitter")
        sidebar_state = _stored_bytes(self._settings, f"{root}/sidebar_splitter")
        if dock_state is None or main_state is None or sidebar_state is None:
            return False
        window = self.window
        main = getattr(window, "main_splitter", None)
        sidebar = getattr(window, "sidebar_splitter", None)
        dock = getattr(window, "bottom_dock", None)
        if not (
            isinstance(main, QSplitter)
            and isinstance(sidebar, QSplitter)
            and isinstance(dock, QDockWidget)
        ):
            return False
        if not window.restoreState(dock_state):
            return False
        if not main.restoreState(main_state) or not sidebar.restoreState(sidebar_state):
            return False
        visible = self._settings.value(f"{root}/plots_visible")
        if isinstance(visible, bool):
            dock.setVisible(visible)
        elif isinstance(visible, str) and visible.lower() in ("true", "false"):
            dock.setVisible(visible.lower() == "true")
        else:
            return False
        if dock.isFloating():
            saved_geometry = _stored_bytes(self._settings, f"{root}/floating_geometry")
            if saved_geometry is not None:
                dock.restoreGeometry(saved_geometry)
        return True

    def _apply_default(self, preset: WorkspacePreset) -> None:
        window = self.window
        main = getattr(window, "main_splitter", None)
        sidebar = getattr(window, "sidebar_splitter", None)
        dock = getattr(window, "bottom_dock", None)
        if not (
            isinstance(main, QSplitter)
            and isinstance(sidebar, QSplitter)
            and isinstance(dock, QDockWidget)
        ):
            return
        # A new or corrupted preset must have a deterministic dock topology,
        # regardless of the previous preset's floating/maximized Plots state.
        # The previous preset was captured before this operation.
        if dock.isMaximized():
            dock.showNormal()
        if dock.isFloating():
            dock.hide()
            window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
            dock.setFloating(False)
        # Ratios are layout hints, not hard minimum sizes or a second geometry authority.
        width = max(1, main.width(), window.width())
        if preset is WorkspacePreset.ANALYZE:
            sidebar_ratio, files_ratio, plots = 0.34, 0.30, True
        elif preset is WorkspacePreset.REVIEW:
            sidebar_ratio, files_ratio, plots = 0.29, 0.52, False
        else:
            sidebar_ratio, files_ratio, plots = 0.27, 0.68, False
        main.setSizes([round(width * sidebar_ratio), round(width * (1 - sidebar_ratio))])
        height = max(1, sidebar.height(), window.height() - 120)
        sidebar.setSizes([round(height * files_ratio), round(height * (1 - files_ratio))])
        dock.setVisible(plots)
        if plots and not dock.isFloating():
            window.resizeDocks(
                [dock],
                [max(180, round(window.height() * 0.29))],
                Qt.Orientation.Vertical,
            )

    def _layout_changed(self, *_args: object) -> None:
        if not self._applying and not self._quiescing:
            self._capture_timer.start(150)

    def _dock_changed(self, *_args: object) -> None:
        self._layout_changed()
        if not self._quiescing:
            self._recover_timer.start(0)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if not self._quiescing:
            if watched is self.window and event.type() == QEvent.Type.Show:
                self._recover_timer.start(0)
            dock = getattr(self.window, "bottom_dock", None)
            if watched is dock:
                if event.type() in (
                    QEvent.Type.Move,
                    QEvent.Type.Resize,
                    QEvent.Type.WindowStateChange,
                ):
                    self._layout_changed()
                if event.type() == QEvent.Type.Show:
                    self._recover_timer.start(0)
        return super().eventFilter(watched, event)

    def _recover_windows(self) -> None:
        if self._quiescing:
            return
        window = self.window
        if window.isVisible():
            _screen_recover(window)
        dock = getattr(window, "bottom_dock", None)
        if isinstance(dock, QDockWidget) and dock.isFloating():
            _screen_recover(dock)

    def _reset_after_main_window(self, _checked: bool = False) -> None:
        if self._quiescing:
            return
        self._capture_timer.stop()
        self._settings.remove(_WORKSPACE_LAYOUT_ROOT)
        self._settings.remove(WORKSPACE_PRESET_SETTING)
        self._preset = WorkspacePreset.COMPARE
        self.selector.blockSignals(True)
        self.selector.setCurrentIndex(self.selector.findData(self._preset.value))
        self.selector.blockSignals(False)

    def quiesce_pending_callbacks(self) -> None:
        if self._quiescing:
            return
        self._capture_timer.stop()
        self._save_current()
        self._quiescing = True
        self._recover_timer.stop()
