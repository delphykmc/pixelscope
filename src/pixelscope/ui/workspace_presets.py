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
    QSizePolicy,
    QStyle,
    QSplitter,
    QTableWidget,
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
    # A sliver of the *content* is not enough: the native title/drag region
    # must remain accessible after a monitor is unplugged or DPI changes.
    caption_height = min(frame.height(), max(24, widget.fontMetrics().height() + 10))
    caption = QRect(frame.x(), frame.y(), frame.width(), caption_height)
    for screen_rect in available:
        visible = caption.intersected(screen_rect)
        if (
            visible.width() >= min(96, caption.width())
            and visible.height() >= min(16, caption.height())
        ):
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
        self._summary_original: tuple[
            QSizePolicy.Policy,
            QSizePolicy.Policy,
            QSizePolicy.Policy,
            QSizePolicy.Policy,
            Qt.ScrollBarPolicy,
            int,
        ] | None = None
        analysis = getattr(window, "comparison_analysis_panel", None)
        summary_group = getattr(analysis, "image_summary_group", None)
        summary = getattr(analysis, "image_summary", None)
        if isinstance(summary_group, QWidget) and isinstance(summary, QTableWidget):
            group_policy = summary_group.sizePolicy()
            table_policy = summary.sizePolicy()
            self._summary_original = (
                group_policy.horizontalPolicy(),
                group_policy.verticalPolicy(),
                table_policy.horizontalPolicy(),
                table_policy.verticalPolicy(),
                summary.verticalScrollBarPolicy(),
                summary_group.maximumHeight(),
            )
        self._quiescing = False
        self._capture_timer = QTimer(self)
        self._capture_timer.setSingleShot(True)
        self._capture_timer.timeout.connect(self._save_current)  # type: ignore[attr-defined]
        self._recover_timer = QTimer(self)
        self._recover_timer.setSingleShot(True)
        self._recover_timer.timeout.connect(self._recover_windows)  # type: ignore[attr-defined]
        self._density_timer = QTimer(self)
        self._density_timer.setSingleShot(True)
        self._density_timer.timeout.connect(  # type: ignore[attr-defined]
            self._sync_toolbar_density
        )
        self._density_updating = False

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
        toolbar = getattr(window, "main_toolbar", None)
        if isinstance(toolbar, QToolBar):
            toolbar.installEventFilter(self)
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
        self._density_timer.start(0)

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
            open_images.setIcon(
                window.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton)
            )
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
            # Qt dock visibility can reallocate the splitters after restoreState.
            # Preserve the user's sizes as an additional presentation-only hint.
            self._settings.setValue(f"{root}/main_sizes", main.sizes())
            self._settings.setValue(f"{root}/sidebar_sizes", sidebar.sizes())
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
        self._configure_statistics_space(preset is WorkspacePreset.ANALYZE)
        self._recover_timer.start(0)

    @staticmethod
    def _splitter_sizes(settings: QSettings, key: str, count: int) -> list[int] | None:
        """Accept only nonnegative, bounded Qt splitter sizes from settings."""

        value = settings.value(key)
        if not isinstance(value, list | tuple) or len(value) != count:
            return None
        result: list[int] = []
        for item in value:
            if isinstance(item, bool) or not (
                isinstance(item, int) or (isinstance(item, str) and item.isdecimal())
            ):
                return None
            number = int(item)
            if number < 0 or number > 100_000:
                return None
            result.append(number)
        return result if any(result) else None

    def _configure_statistics_space(self, analyze: bool) -> None:
        """Reserve real Statistics rows instead of an oversized Images summary.

        No metric, analysis snapshot or source state is changed. W07 still owns
        the entire Statistics data/model pipeline.
        """

        panel = getattr(self.window, "comparison_analysis_panel", None)
        group = getattr(panel, "image_summary_group", None)
        summary = getattr(panel, "image_summary", None)
        original = self._summary_original
        if not (
            isinstance(group, QWidget)
            and isinstance(summary, QTableWidget)
            and original is not None
        ):
            return
        if not analyze:
            group.setMaximumHeight(original[5])
            group.setSizePolicy(original[0], original[1])
            summary.setSizePolicy(original[2], original[3])
            summary.setVerticalScrollBarPolicy(original[4])
            return

        summary.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        summary.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        row_height = summary.verticalHeader().defaultSectionSize()
        header_height = summary.horizontalHeader().sizeHint().height()
        chrome = group.fontMetrics().height() + 4 * TOKENS.spacing_sm + 2 * summary.frameWidth()
        # Keep two summary rows visible; additional sources remain scrollable.
        readable_height = header_height + 2 * row_height + chrome
        group.setMaximumHeight(max(group.minimumSizeHint().height(), readable_height))

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
        # Qt can resize the central widget when restoring dock visibility.
        # Reapply user-defined splitter sizes *after* the dock settles.
        main_sizes = self._splitter_sizes(self._settings, f"{root}/main_sizes", main.count())
        sidebar_sizes = self._splitter_sizes(
            self._settings, f"{root}/sidebar_sizes", sidebar.count()
        )
        if main_sizes is not None:
            main.setSizes(main_sizes)
        if sidebar_sizes is not None:
            sidebar.setSizes(sidebar_sizes)
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
            sidebar_ratio, files_ratio, plots = 0.35, 0.16, True
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
                [max(180, round(window.height() * 0.24))],
                Qt.Orientation.Vertical,
            )
        # Apply the Files/Statistics ratio against the actual central height,
        # not the pre-dock height used for the initial layout request.
        available_height = max(1, sidebar.height())
        sidebar.setSizes(
            [
                round(available_height * files_ratio),
                round(available_height * (1 - files_ratio)),
            ]
        )

    def _layout_changed(self, *_args: object) -> None:
        if not self._applying and not self._quiescing:
            self._capture_timer.start(150)

    def _dock_changed(self, *_args: object) -> None:
        self._layout_changed()
        if not self._quiescing:
            self._recover_timer.start(0)

    def _sync_toolbar_density(self) -> None:
        """Keep source roles and core actions on the toolbar at narrow logical widths."""

        if self._quiescing or self._density_updating:
            return
        window = self.window
        toolbar = getattr(window, "main_toolbar", None)
        group = window.findChild(QWidget, "comparisonPresetControl")
        if not isinstance(toolbar, QToolBar) or not isinstance(group, QWidget):
            # W05 is installed after the W06 dock controller in bootstrap.
            return
        status = group.findChild(QLabel, "comparisonPresetStatus")
        caption = next(
            (label for label in group.findChildren(QLabel) if label.text() == "Preset"),
            None,
        )
        compact = window.width() <= 1240 or toolbar.width() <= 1120
        self._density_updating = True
        try:
            toolbar.setToolButtonStyle(
                Qt.ToolButtonStyle.ToolButtonIconOnly
                if compact
                else Qt.ToolButtonStyle.ToolButtonTextBesideIcon
            )
            if isinstance(caption, QLabel):
                caption.setVisible(not compact)
            if isinstance(status, QLabel):
                # Keep Difference status accessible via an eliding label and
                # its full tooltip; do not hide the A/B source controls.
                status.setMaximumWidth(48 if compact else 145)
            group.updateGeometry()
        finally:
            self._density_updating = False

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if not self._quiescing:
            window = self.window
            toolbar = getattr(window, "main_toolbar", None)
            if watched is window and event.type() == QEvent.Type.Show:
                self._recover_timer.start(0)
            if watched is window or watched is toolbar:
                if event.type() in (
                    QEvent.Type.Show,
                    QEvent.Type.Resize,
                    QEvent.Type.FontChange,
                    QEvent.Type.StyleChange,
                ):
                    self._density_timer.start(0)
            dock = getattr(window, "bottom_dock", None)
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
        # The canonical MainWindow Reset action applies its legacy geometry
        # first. Reapply Compare's actual dock/splitter layout, not just its name.
        self._apply_preset(WorkspacePreset.COMPARE, prefer_saved=False)

    def quiesce_pending_callbacks(self) -> None:
        if self._quiescing:
            return
        self._capture_timer.stop()
        self._save_current()
        self._quiescing = True
        self._recover_timer.stop()
        self._density_timer.stop()
