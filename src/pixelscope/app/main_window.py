from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray
from PySide6.QtCore import QByteArray, QItemSelectionModel, QSettings, QSize, Qt, QThreadPool
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDragEnterEvent,
    QDropEvent,
    QKeySequence,
    QShortcut,
)
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QToolBar,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pixelscope.app.settings import ApplicationSettings, SettingsRepository
from pixelscope.core.bayer import bayer_channel_at
from pixelscope.core.channel_views import split_document_channels
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineSelection, clamp_line
from pixelscope.core.performance_settings import PerformanceSettings
from pixelscope.core.roi import RoiBounds, clamp_roi
from pixelscope.io.path_discovery import (
    ImageInput,
    discover_image_inputs,
    natural_sort_key,
)
from pixelscope.io.raw_profile import RawProfile
from pixelscope.io.raw_reader import required_file_size
from pixelscope.ui.comparison_analysis_panel import ComparisonAnalysisPanel
from pixelscope.ui.design_tokens import (
    TOKENS,
    menu_style,
    panel_heading_style,
    toolbar_style,
)
from pixelscope.ui.difference_panel import DifferencePanel
from pixelscope.ui.document_list import DocumentListWidget
from pixelscope.ui.empty_state import EmptyWorkspace
from pixelscope.ui.image_viewer import ImageViewer
from pixelscope.ui.line_profile_panel import LineProfilePanel
from pixelscope.ui.multi_compare_view import MultiCompareView, MultiCompareViewState
from pixelscope.ui.plots_dock_title import PlotsDockTitleBar
from pixelscope.ui.raw_open_dialog import RawOpenDialog
from pixelscope.ui.settings_dialog import SettingsDialog
from pixelscope.ui.structured_status_bar import StructuredStatusBar
from pixelscope.ui.toolbar_icons import toolbar_icon
from pixelscope.workers.image_load_worker import ImageLoadWorker
from pixelscope.workers.task_worker import TaskError, TaskWorker

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class SixImageDiffRestoreState:
    """Workspace state hidden by the required six-source Diff-only view."""

    layout_mode: str
    focus_document_id: str | None
    active_document_id: str | None
    page_start: int
    current_index: int
    display_order: tuple[str, ...]
    view_state: MultiCompareViewState


class MainWindow(QMainWindow):
    """Document registration, selection-driven comparison, and analysis lifecycle."""

    def __init__(
        self,
        application_settings: ApplicationSettings | None = None,
        performance_settings: PerformanceSettings | None = None,
        settings_repository: SettingsRepository | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("PixelScope")
        self.resize(1400, 850)
        self.setAcceptDrops(True)
        self.settings = QSettings()
        self.settings_repository = settings_repository or SettingsRepository()
        self.application_settings = application_settings or self.settings_repository.load()
        self.performance_settings = (
            performance_settings or self.application_settings.performance_settings()
        )
        self._last_directory = str(self.settings.value("paths/last_directory", ""))
        self._dont_show_raw_json_profiles = self.application_settings.dont_show_raw_json_profiles

        self.documents: dict[str, ImageDocument] = {}
        self._document_id_by_path: dict[str, str] = {}
        self._raw_profile_paths: dict[str, Path] = {}
        self._raw_profiles: dict[str, RawProfile] = {}
        self._workers: dict[str, TaskWorker] = {}
        self._load_worker_targets: dict[str, str] = {}
        self._load_tokens: dict[str, int] = {}
        self._load_pool = QThreadPool(self)
        self._load_pool.setMaxThreadCount(2)
        self._resident_order: list[str] = []
        self._resident_document_limit = 7
        self._visible_document_ids: set[str] = set()
        self._selection_order: list[str] = []
        self._folder_documents: dict[str, list[str]] = {}
        self._folder_paths: dict[str, Path] = {}
        self._folder_indices: dict[str, int] = {}
        self._current_index = 0
        self._page_start = 0
        self._view_capacity = 1
        self._layout_mode = "Auto"
        self._focus_document_id: str | None = None
        self._multi_display_order: list[str] = []
        self._shared_roi: RoiBounds | None = None
        self._shared_line: LineSelection | None = None
        self._split_channels = False
        self._channel_split_active = False
        self._active_document_id: str | None = None
        self._difference_document: ImageDocument | None = None
        self._difference_source_ids: tuple[str, str] | None = None
        self._pending_pair_focus: int | str | None = None
        self._channel_view_cache: dict[tuple[str, int], list[ImageDocument]] = {}
        self._six_image_diff_restore_state: SixImageDiffRestoreState | None = None

        pool = QThreadPool.globalInstance()
        pool.setMaxThreadCount(min(4, max(1, pool.maxThreadCount())))

        self.viewer = ImageViewer()
        self.multi_compare_view = MultiCompareView()
        self.empty_workspace = EmptyWorkspace()
        self.central_stack = QStackedWidget()
        self.central_stack.addWidget(self.empty_workspace)
        self.central_stack.addWidget(self.viewer)
        self.central_stack.addWidget(self.multi_compare_view)
        self.central_stack.setCurrentWidget(self.empty_workspace)

        self.document_list = DocumentListWidget()
        self.document_list.itemSelectionChanged.connect(  # type: ignore[attr-defined]
            self._selection_changed
        )
        self.document_list.paths_dropped.connect(self._handle_dropped_paths)
        self.document_list.previous_pair_requested.connect(self.previous_folder_pair)
        self.document_list.next_pair_requested.connect(self.next_folder_pair)
        self.document_list.activate_requested.connect(
            lambda document_id: self._select_document_ids([document_id])
        )
        self.document_list.remove_requested.connect(self._remove_document_ids)
        self.document_list.compare_requested.connect(self.compare_selection)
        self.document_list.focus_requested.connect(self._set_focus_document)

        self.comparison_analysis_panel = ComparisonAnalysisPanel()
        self.line_profile_panel = LineProfilePanel()
        self.difference_panel = DifferencePanel(self.performance_settings.difference_cache_bytes)
        self.difference_panel.set_display_defaults(
            self.application_settings.difference_threshold,
            self.application_settings.difference_gain,
        )
        self.analysis_tabs = QTabWidget()
        self.analysis_tabs.addTab(self.comparison_analysis_panel, "Statistics")
        self.analysis_tabs.addTab(self.difference_panel, "Difference")
        self._build_layout()

        self.viewer.cursor_moved.connect(self._inspect_pixel)
        self.viewer.roi_changed.connect(self._shared_roi_changed)
        self.viewer.roi_cleared.connect(self.clear_roi)
        self.viewer.line_changed.connect(self._shared_line_changed)
        self.viewer.line_cleared.connect(self.clear_line)
        self.multi_compare_view.cursor_moved.connect(self._inspect_multi_pixel)
        self.multi_compare_view.roi_changed.connect(self._shared_roi_changed)
        self.multi_compare_view.roi_cleared.connect(self.clear_roi)
        self.multi_compare_view.line_changed.connect(self._shared_line_changed)
        self.multi_compare_view.line_cleared.connect(self.clear_line)
        self.multi_compare_view.active_document_changed.connect(self._active_tile_changed)
        self.multi_compare_view.zoom_changed.connect(self._set_zoom_status)
        self.multi_compare_view.focus_document_requested.connect(self._set_focus_document)
        self.viewer.activated.connect(
            lambda _viewer: self._set_active_document(self.viewer.document)
        )
        self.viewer.zoom_changed.connect(self._set_zoom_status)
        self.viewer.navigation_requested.connect(self._navigate_single_view)
        self.comparison_analysis_panel.scope_changed.connect(self._analysis_scope_changed)
        self.difference_panel.result_ready.connect(self._difference_panel_ready)
        self.difference_panel.preview_updated.connect(self._difference_preview_updated)
        self.empty_workspace.open_images_requested.connect(self.open_images)
        self.empty_workspace.open_folder_requested.connect(self.open_folder)
        self.empty_workspace.open_raw_requested.connect(self.open_raw)
        self._create_actions()
        self._create_toolbar()
        self._create_selection_shortcuts()

        self.structured_status = StructuredStatusBar()
        self.pixel_status = self.structured_status.coordinate
        self.statusBar().addPermanentWidget(self.structured_status, 1)
        self.statusBar().showMessage("Drop images or folders, or use File > Open")
        self._restore_ui_state()

    def _build_layout(self) -> None:
        self.sidebar_splitter = QSplitter(Qt.Orientation.Vertical)
        documents_container = QWidget()
        documents_layout = QVBoxLayout(documents_container)
        documents_layout.setContentsMargins(4, 4, 4, 4)
        self.files_label = QLabel("Files")
        self.files_label.setStyleSheet(panel_heading_style())
        documents_layout.addWidget(self.files_label)
        documents_layout.addWidget(self.document_list)

        analysis_container = QWidget()
        analysis_layout = QVBoxLayout(analysis_container)
        analysis_layout.setContentsMargins(4, 4, 4, 4)
        analysis_label = QLabel("Analysis")
        analysis_label.setStyleSheet(panel_heading_style())
        analysis_layout.addWidget(analysis_label)
        analysis_layout.addWidget(self.analysis_tabs)
        self.sidebar_splitter.addWidget(documents_container)
        self.sidebar_splitter.addWidget(analysis_container)
        self.sidebar_splitter.setStretchFactor(0, 2)
        self.sidebar_splitter.setStretchFactor(1, 3)

        sidebar = QWidget()
        sidebar.setMinimumWidth(320)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.addWidget(self.sidebar_splitter)
        self.bottom_tabs = QTabWidget()
        self.bottom_tabs.addTab(self.comparison_analysis_panel.histogram_panel, "Histogram")
        self.bottom_tabs.addTab(self.line_profile_panel, "Line Profile")
        self.bottom_dock = QDockWidget("Plots", self)
        self.bottom_dock.setObjectName("plotsPanel")
        self.bottom_dock.setWidget(self.bottom_tabs)
        self.bottom_dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)
        self.bottom_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.plots_dock_title = PlotsDockTitleBar(self.bottom_dock)
        self.bottom_dock.setTitleBarWidget(self.plots_dock_title)
        self.bottom_dock.hide()

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.addWidget(sidebar)
        self.main_splitter.addWidget(self.central_stack)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([390, 1010])
        self.setCentralWidget(self.main_splitter)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.bottom_dock)

    def _create_actions(self) -> None:
        self.action_map: dict[str, QAction] = {}

        def add_action(
            menu_name: str,
            text: str,
            callback: Any,
            shortcut: str | None = None,
        ) -> QAction:
            action = QAction(text, self)
            action.triggered.connect(callback)  # type: ignore[attr-defined]
            if shortcut is not None:
                action.setShortcut(shortcut)
            menus[menu_name].addAction(action)
            self.action_map[text] = action
            return action

        menu_bar = self.menuBar()
        menu_bar.setStyleSheet(menu_style())
        menus = {
            "File": menu_bar.addMenu("&File"),
            "Edit": menu_bar.addMenu("&Edit"),
            "Selection": menu_bar.addMenu("&Selection"),
            "View": menu_bar.addMenu("&View"),
        }
        for menu in menus.values():
            menu.setStyleSheet(menu_style())
        add_action("File", "Open Images...", self.open_images, "Ctrl+O")
        add_action("File", "Open Folder...", self.open_folder, "Ctrl+Shift+O")
        add_action("File", "Open RAW with Profile...", self.open_raw)
        menus["File"].addSeparator()
        add_action("File", "Export Statistics CSV...", self.export_statistics)
        menus["File"].addSeparator()
        add_action("File", "Exit", self.close, "Alt+F4")

        add_action("Edit", "Remove Selected", self.remove_selected, "Delete")
        add_action("Edit", "Clear ROI", self._escape_action, "Esc")
        add_action("Edit", "Clear Line Profile", self.clear_line, "Shift+Esc")
        menus["Edit"].addSeparator()
        add_action("Edit", "Settings...", self.open_settings)

        add_action(
            "Selection",
            "Show Selected in Multi View",
            self.compare_selection,
            "M",
        )
        add_action("Selection", "Select All", self.select_all_documents, "Ctrl+A")
        menus["Selection"].addSeparator()
        previous_image = add_action("Selection", "Previous Image", self.previous_image)
        next_image = add_action("Selection", "Next Image", self.next_image)
        previous_image.setText("Previous Image\tLeft")
        next_image.setText("Next Image\tRight")
        previous_pair = add_action("Selection", "Previous Folder Pair", self.previous_folder_pair)
        next_pair = add_action("Selection", "Next Folder Pair", self.next_folder_pair)
        previous_pair.setText("Previous Folder Pair\tPageUp")
        next_pair.setText("Next Folder Pair\tPageDown")

        add_action("View", "Auto Layout", lambda: self.set_layout_mode("Auto"))
        add_action("View", "Single View", lambda: self.set_layout_mode("Single View"), "Ctrl+1")
        add_action("View", "Multi View", lambda: self.set_layout_mode("Multi View"), "Ctrl+2")
        menus["View"].addSeparator()
        self.split_channels_action = add_action(
            "View",
            "Split Channels",
            self._set_split_channels,
        )
        self.split_channels_action.setCheckable(True)
        self.split_channels_action.setIcon(toolbar_icon("split_channels"))
        self.split_channels_action.setIconText("Split")
        self.split_channels_action.setToolTip(
            "Split the selected RGB or Bayer image into channel views"
        )
        self.split_channels_action.setStatusTip(self.split_channels_action.toolTip())
        menus["View"].addSeparator()
        add_action("View", "Fit Image", self.fit_image, "F")
        add_action("View", "100% Zoom", self.zoom_100_percent, "Ctrl+0")
        menus["View"].addSeparator()
        show_results = add_action("View", "Show Plots", self._toggle_plots)
        show_results.setCheckable(True)
        self.plots_action = show_results
        self.bottom_dock.visibilityChanged.connect(  # type: ignore[attr-defined]
            self._plots_visibility_changed
        )
        self.bottom_dock.topLevelChanged.connect(  # type: ignore[attr-defined]
            self._plots_top_level_changed
        )
        self.redock_plots_action = add_action("View", "Dock Plots", self._redock_plots)
        self.redock_plots_action.setIcon(toolbar_icon("dock"))
        self.redock_plots_action.setToolTip("Dock the floating Plots panel")
        self.redock_plots_action.setStatusTip(self.redock_plots_action.toolTip())
        self.redock_plots_action.setEnabled(False)
        add_action("View", "Reset Workspace Layout", self.reset_workspace_layout)
        self._update_action_states()

    def create_settings_dialog(self) -> SettingsDialog:
        dialog = SettingsDialog(
            self.settings_repository,
            self.application_settings,
            self.performance_settings,
            self,
        )
        dialog.settings_saved.connect(self._application_settings_saved)
        return dialog

    def open_settings(self) -> None:
        dialog = self.create_settings_dialog()
        dialog.exec()

    def _application_settings_saved(self, settings: object) -> None:
        if not isinstance(settings, ApplicationSettings):
            return
        self.application_settings = settings
        self._dont_show_raw_json_profiles = settings.dont_show_raw_json_profiles
        self.difference_panel.set_display_defaults(
            settings.difference_threshold,
            settings.difference_gain,
        )

    def _create_toolbar(self) -> None:
        toolbar = QToolBar("Main", self)
        toolbar.setObjectName("mainToolbar")
        toolbar.setAccessibleName("PixelScope main toolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(TOKENS.icon_size, TOKENS.icon_size))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        toolbar.setStyleSheet(toolbar_style())
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
        self.main_toolbar = toolbar

        self.layout_selector = QComboBox()
        self.layout_selector.addItems(("Auto", "Single View", "Multi View"))
        self.layout_selector.setFixedHeight(TOKENS.control_height)
        self.layout_selector.currentTextChanged.connect(  # type: ignore[attr-defined]
            self.set_layout_mode
        )
        layout_group = QWidget()
        layout_group_layout = QHBoxLayout(layout_group)
        layout_group_layout.setContentsMargins(
            TOKENS.spacing_sm,
            0,
            TOKENS.spacing_md,
            0,
        )
        layout_group_layout.setSpacing(TOKENS.spacing_sm)
        layout_group_layout.addWidget(QLabel("Layout"))
        layout_group_layout.addWidget(self.layout_selector)
        toolbar.addWidget(layout_group)
        toolbar.addAction(self.split_channels_action)
        toolbar.addSeparator()

        fit_action = self.action_map["Fit Image"]
        fit_action.setIcon(toolbar_icon("fit"))
        fit_action.setIconText("Fit")
        fit_action.setToolTip("Fit the active image to the current view (F)")
        fit_action.setStatusTip(fit_action.toolTip())
        toolbar.addAction(fit_action)

        zoom_100 = self.action_map["100% Zoom"]
        zoom_100.setIcon(toolbar_icon("actual_size"))
        zoom_100.setIconText("1:1")
        zoom_100.setToolTip("Show the active image at one image pixel per screen pixel (Ctrl+0)")
        zoom_100.setStatusTip(zoom_100.toolTip())
        toolbar.addAction(zoom_100)

        self.zoom_in_action = QAction(toolbar_icon("zoom_in"), "Zoom In", self)
        self.zoom_in_action.setIconText("Zoom +")
        self.zoom_in_action.setToolTip("Zoom in around the current view center")
        self.zoom_in_action.setStatusTip(self.zoom_in_action.toolTip())
        self.zoom_in_action.triggered.connect(  # type: ignore[attr-defined]
            lambda: self.zoom_by(0.8)
        )
        toolbar.addAction(self.zoom_in_action)

        self.zoom_out_action = QAction(toolbar_icon("zoom_out"), "Zoom Out", self)
        self.zoom_out_action.setIconText("Zoom −")
        self.zoom_out_action.setToolTip("Zoom out around the current view center")
        self.zoom_out_action.setStatusTip(self.zoom_out_action.toolTip())
        self.zoom_out_action.triggered.connect(  # type: ignore[attr-defined]
            lambda: self.zoom_by(1.25)
        )
        toolbar.addAction(self.zoom_out_action)
        toolbar.addSeparator()

        self.sync_action = QAction(toolbar_icon("sync"), "Sync View", self)
        self.sync_action.setIconText("Sync")
        self.sync_action.setCheckable(True)
        self.sync_action.setChecked(True)
        self.sync_action.toggled.connect(  # type: ignore[attr-defined]
            self.multi_compare_view.set_sync_enabled
        )
        self.sync_action.toggled.connect(  # type: ignore[attr-defined]
            lambda _checked: self._update_action_states()
        )
        toolbar.addAction(self.sync_action)

        self.diff_action = QAction(toolbar_icon("difference"), "Diff", self)
        self.diff_action.setIconText("Diff")
        self.diff_action.setCheckable(True)
        self.diff_action.setEnabled(False)
        self.diff_action.toggled.connect(self._set_difference_visible)  # type: ignore[attr-defined]
        toolbar.addAction(self.diff_action)

        self.plots_action.setIcon(toolbar_icon("plots"))
        self.plots_action.setText("Plots")
        self.plots_action.setIconText("Plots")
        toolbar.addAction(self.plots_action)
        toolbar.addSeparator()

        self.export_toolbar_action = QAction(toolbar_icon("export"), "Export", self)
        self.export_toolbar_action.setIconText("Export")
        self.export_toolbar_action.triggered.connect(  # type: ignore[attr-defined]
            self.export_statistics
        )
        toolbar.addAction(self.export_toolbar_action)

        for selector in (self.difference_panel.a_selector, self.difference_panel.b_selector):
            selector.currentIndexChanged.connect(  # type: ignore[attr-defined]
                lambda _index: self._update_action_states()
            )
        self._update_action_states()

    def _escape_action(self) -> None:
        self.clear_roi()

    def _show_bottom_results(self) -> None:
        self.bottom_dock.show()
        self.bottom_dock.raise_()
        if not self.bottom_dock.isFloating():
            self.resizeDocks([self.bottom_dock], [280], Qt.Orientation.Vertical)

    def _toggle_plots(self) -> None:
        self._set_plots_visible(self.plots_action.isChecked())

    def _set_plots_visible(self, visible: bool) -> None:
        if visible:
            self._show_bottom_results()
        else:
            self.bottom_dock.hide()
        self.plots_action.blockSignals(True)
        self.plots_action.setChecked(visible)
        self.plots_action.blockSignals(False)
        self._update_action_states()

    def _plots_visibility_changed(self, visible: bool) -> None:
        self.plots_action.blockSignals(True)
        self.plots_action.setChecked(visible)
        self.plots_action.blockSignals(False)
        self._update_action_states()

    def _plots_top_level_changed(self, floating: bool) -> None:
        self.redock_plots_action.setEnabled(floating)
        self.plots_dock_title.sync(floating)
        self.bottom_dock.setWindowTitle(
            "Plots — use View > Dock Plots to re-dock" if floating else "Plots"
        )

    def _redock_plots(self) -> None:
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.bottom_dock)
        self.bottom_dock.setFloating(False)
        self.bottom_dock.show()
        self.resizeDocks([self.bottom_dock], [280], Qt.Orientation.Vertical)

    def _show_plot_tab(self, index: int) -> None:
        self.bottom_tabs.setCurrentIndex(index)
        self.plots_action.setChecked(True)
        self._set_plots_visible(True)

    def export_statistics(self) -> None:
        if self.comparison_analysis_panel.table.columnCount() == 0:
            self.statusBar().showMessage("No statistics to export", 3000)
            return
        export_directory = self._export_dialog_directory()
        initial_path = (
            str(Path(export_directory) / "pixelscope_statistics.csv")
            if export_directory
            else "pixelscope_statistics.csv"
        )
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export statistics",
            initial_path,
            "CSV (*.csv)",
        )
        if not path:
            return
        target = Path(path)
        self._remember_directory(target.parent)
        self.comparison_analysis_panel.export_csv(target)
        self.statusBar().showMessage(f"Exported {target.name}", 4000)

    def _create_selection_shortcuts(self) -> None:
        self._selection_shortcuts: list[QShortcut] = []
        for index in range(6):
            shortcut = QShortcut(QKeySequence(str(index + 1)), self)
            shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
            shortcut.activated.connect(  # type: ignore[attr-defined]
                lambda selected_index=index: self.show_selected_image(selected_index)
            )
            self._selection_shortcuts.append(shortcut)
        for key, callback in (
            (Qt.Key.Key_PageUp, self.previous_folder_pair),
            (Qt.Key.Key_PageDown, self.next_folder_pair),
        ):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
            shortcut.activated.connect(callback)  # type: ignore[attr-defined]
            self._selection_shortcuts.append(shortcut)
        for key, callback in (
            (Qt.Key.Key_Left, self.previous_image),
            (Qt.Key.Key_Right, self.next_image),
        ):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
            shortcut.activated.connect(callback)  # type: ignore[attr-defined]
            self._selection_shortcuts.append(shortcut)

    def _update_action_states(self) -> None:
        documents = self.selected_documents
        six_image_diff = self._six_image_diff_locked()
        split_action = self.action_map.get("Split Channels")
        if split_action is not None:
            split_available = (
                len(documents) == 1
                and documents[0].source is not None
                and documents[0].channel_layout in ("RGB", "RGBA", "BAYER")
            )
            split_action.setEnabled(split_available)
            if split_available and split_action.isChecked():
                split_tooltip = "Return to the combined image view"
            elif split_available:
                split_tooltip = "Split the selected RGB or Bayer image into channel views"
            elif len(documents) != 1:
                split_tooltip = "Split Channels requires exactly one selected image"
            elif documents[0].source is None:
                split_tooltip = "Split Channels will be available when the image finishes loading"
            else:
                split_tooltip = "Split Channels supports RGB, RGBA, and Bayer images"
            split_action.setToolTip(split_tooltip)
            split_action.setStatusTip(split_tooltip)

        current_widget = self.central_stack.currentWidget()
        visible_viewers = self.multi_compare_view.occupied_viewers
        view_ready = (current_widget is self.viewer and self.viewer.document is not None) or (
            current_widget is self.multi_compare_view and bool(visible_viewers)
        )
        for name in ("Fit Image", "100% Zoom"):
            action = self.action_map.get(name)
            if action is not None:
                action.setEnabled(view_ready)
        for name in ("zoom_in_action", "zoom_out_action"):
            action = getattr(self, name, None)
            if isinstance(action, QAction):
                action.setEnabled(view_ready)

        if hasattr(self, "sync_action"):
            sync_available = current_widget is self.multi_compare_view and len(visible_viewers) >= 2
            self.sync_action.setEnabled(sync_available)
            if not sync_available:
                sync_tooltip = "Sync View is available in Multi View with two or more images"
            elif self.sync_action.isChecked():
                sync_tooltip = "Disable synchronized zoom, pan, and cursor"
            else:
                sync_tooltip = "Synchronize zoom, pan, and cursor across visible images"
            self.sync_action.setToolTip(sync_tooltip)
            self.sync_action.setStatusTip(sync_tooltip)

        statistics_available = (
            bool(documents) and self.comparison_analysis_panel.table.columnCount() > 0
        )
        menu_export = self.action_map.get("Export Statistics CSV...")
        if menu_export is not None:
            menu_export.setEnabled(statistics_available)
            menu_export.setToolTip(
                "Export the current Statistics table as CSV"
                if statistics_available
                else "No statistics are available to export"
            )
        if hasattr(self, "export_toolbar_action"):
            self.export_toolbar_action.setEnabled(statistics_available)
            export_tooltip = (
                "Export the current Statistics table as CSV"
                if statistics_available
                else "No statistics are available to export"
            )
            self.export_toolbar_action.setToolTip(export_tooltip)
            self.export_toolbar_action.setStatusTip(export_tooltip)

        if hasattr(self, "diff_action"):
            pair = self.difference_panel.selected_documents()
            pair_ids = (
                frozenset((pair[0].document_id, pair[1].document_id)) if pair is not None else None
            )
            result_ids = (
                frozenset(self._difference_source_ids)
                if self._difference_source_ids is not None
                else None
            )
            cached = pair_ids is not None and self.difference_panel.has_cached_map()
            checked = self.diff_action.isChecked()
            self.diff_action.setEnabled(checked or cached)
            if checked and (cached or (pair_ids is not None and pair_ids == result_ids)):
                diff_tooltip = "Hide Difference"
            elif checked or (
                pair_ids is not None and result_ids is not None and pair_ids != result_ids
            ):
                diff_tooltip = "Difference is not calculated for the selected pair"
            elif cached:
                diff_tooltip = "Show the cached Difference for the selected image pair"
            else:
                diff_tooltip = "Calculate Difference in Analysis first"
            self.diff_action.setToolTip(diff_tooltip)
            self.diff_action.setStatusTip(diff_tooltip)

        if hasattr(self, "plots_action"):
            plots_visible = self.plots_action.isChecked()
            plots_tooltip = (
                "Hide Histogram and Line Profile plots"
                if plots_visible
                else "Show Histogram and Line Profile plots"
            )
            self.plots_action.setToolTip(plots_tooltip)
            self.plots_action.setStatusTip(plots_tooltip)

        multi_action = self.action_map.get("Multi View")
        if multi_action is not None:
            multi_action.setEnabled(not six_image_diff)
        if hasattr(self, "layout_selector"):
            model = self.layout_selector.model()
            for mode in ("Auto", "Multi View"):
                index = self.layout_selector.findText(mode)
                item = model.item(index) if index >= 0 and hasattr(model, "item") else None
                if item is not None:
                    item.setEnabled(not six_image_diff)

    def _six_image_diff_locked(self) -> bool:
        return (
            len(self.selected_documents) >= 6
            and self._difference_document is not None
            and hasattr(self, "diff_action")
            and self.diff_action.isChecked()
        )

    @property
    def selected_documents(self) -> list[ImageDocument]:
        selected_ids = {
            str(item.data(0, Qt.ItemDataRole.UserRole))
            for item in self.document_list.selected_document_items()
        }
        ordered_ids = [item for item in self._selection_order if item in selected_ids]
        return [
            self.documents[document_id]
            for document_id in ordered_ids
            if document_id in self.documents
        ]

    @property
    def current_document(self) -> ImageDocument | None:
        documents = self.selected_documents
        if not documents:
            return None
        return documents[min(self._current_index, len(documents) - 1)]

    def add_document(self, document: ImageDocument, select: bool = True) -> None:
        """Add a ready/error document; primarily useful for programmatic clients and tests."""

        self.documents[document.document_id] = document
        if document.source_path is not None:
            self._document_id_by_path[self._path_key(document.source_path)] = document.document_id
            self._add_document_to_folder(document.document_id, document.source_path)
        self.document_list.add_document_item(
            document.document_id,
            self._document_item_text(document),
            document.source_path,
            document.error_state or str(document.source_path or ""),
            loading_state=document.loading_state,
            resident=document.source is not None,
        )
        if select:
            self._select_document_ids([document.document_id])

    def open_images(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Open images",
            self._open_dialog_directory(),
            "Images (*.png *.bmp *.jpg *.jpeg *.raw);;All files (*)",
        )
        if paths:
            supplied_paths = [Path(path) for path in paths]
            self._remember_directory(supplied_paths[0].parent)
            session = self._active_folder_selection()
            if session is not None:
                self._register_paths_during_pair(supplied_paths, session)
                return
            inputs = discover_image_inputs(supplied_paths)
            self._register_inputs(inputs, select_all=True)

    def open_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Open image folder",
            self._open_dialog_directory(),
        )
        if path:
            folder = Path(path)
            self._remember_directory(folder)
            session = self._active_folder_selection()
            if session is not None:
                self._register_paths_during_pair([folder], session)
                return
            inputs = discover_image_inputs((folder,))
            self._register_inputs(inputs, select_all=False)

    def compare_two_folders(self) -> None:
        first = QFileDialog.getExistingDirectory(
            self,
            "Select first image folder",
            self._open_dialog_directory(),
        )
        if not first:
            return
        second = QFileDialog.getExistingDirectory(
            self,
            "Select second image folder",
            self._open_dialog_directory(),
        )
        if second:
            self.register_folder_pair(Path(first), Path(second))

    def register_folder_pair(self, folder_a: Path, folder_b: Path) -> None:
        inputs_a = discover_image_inputs((folder_a,))
        inputs_b = discover_image_inputs((folder_b,))
        ids_a = [
            document_id
            for image_input in inputs_a
            if (document_id := self._register_input(image_input)) is not None
        ]
        ids_b = [
            document_id
            for image_input in inputs_b
            if (document_id := self._register_input(image_input)) is not None
        ]
        if ids_a and ids_b:
            self.set_view_capacity(2)
            self._select_document_ids([ids_a[0], ids_b[0]])
            self.statusBar().showMessage(
                f"Folder comparison ready · {min(len(ids_a), len(ids_b))} aligned position(s)",
                5000,
            )
        else:
            self.statusBar().showMessage("No supported image pairs found", 5000)

    def open_raw(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open RAW",
            self._open_dialog_directory(),
            "RAW files (*.*)",
        )
        if not path:
            return
        raw_path = Path(path).resolve()
        self._remember_directory(raw_path.parent)
        sidecar = raw_path.with_suffix(".json")
        self._register_inputs(
            (ImageInput(raw_path, sidecar if sidecar.is_file() else None),),
            select_all=True,
        )

    def _register_inputs(
        self,
        inputs: tuple[ImageInput, ...],
        select_all: bool,
        append_selection: bool = False,
    ) -> list[str]:
        document_ids = list(
            dict.fromkeys(
                document_id
                for image_input in inputs
                if (document_id := self._register_input(image_input)) is not None
            )
        )
        if document_ids:
            if append_selection and self.selected_documents:
                existing_ids = [document.document_id for document in self.selected_documents]
                combined_ids = list(dict.fromkeys([*existing_ids, *document_ids]))
                if self._view_capacity > 1 and len(combined_ids) > self._view_capacity:
                    self._view_capacity = 4 if len(combined_ids) <= 4 else 6
                self._select_document_ids(
                    combined_ids,
                    preserve_view=True,
                    preserve_overlays=True,
                )
            else:
                self._select_document_ids(document_ids if select_all else document_ids[:1])
            self.statusBar().showMessage(f"Registered {len(document_ids)} image(s)", 4000)
        else:
            self.statusBar().showMessage("No supported images found", 4000)
        return document_ids

    def _register_input(self, image_input: ImageInput) -> str | None:
        key = self._path_key(image_input.path)
        existing = self._document_id_by_path.get(key)
        raw_profile: RawProfile | None = None
        if image_input.path.suffix.casefold() == ".raw":
            raw_profile = self._confirm_raw_profile(image_input, existing)
            if raw_profile is None:
                return None
        if existing is not None:
            if raw_profile is not None:
                self._raw_profiles[existing] = raw_profile
                if image_input.raw_profile_path is not None:
                    self._raw_profile_paths[existing] = image_input.raw_profile_path
                self._mark_raw_for_reload(existing, raw_profile)
            return existing
        document = ImageDocument.pending_document(image_input.path)
        self.documents[document.document_id] = document
        self._document_id_by_path[key] = document.document_id
        self._add_document_to_folder(document.document_id, image_input.path)
        if image_input.raw_profile_path is not None:
            self._raw_profile_paths[document.document_id] = image_input.raw_profile_path
        if raw_profile is not None:
            self._raw_profiles[document.document_id] = raw_profile
        self.document_list.add_document_item(
            document.document_id,
            self._document_item_text(document),
            image_input.path,
            str(image_input.path),
            loading_state=document.loading_state,
            resident=False,
        )
        return document.document_id

    def _set_dont_show_raw_json_profiles(self, enabled: bool) -> None:
        settings = replace(
            self.application_settings,
            dont_show_raw_json_profiles=bool(enabled),
        )
        self.settings_repository.save(settings)
        self._application_settings_saved(settings)

    def _confirm_raw_profile(
        self,
        image_input: ImageInput,
        existing_id: str | None,
    ) -> RawProfile | None:
        initial_profile: RawProfile | None = None
        profile_from_json = False
        if image_input.raw_profile_path is not None:
            try:
                initial_profile = RawProfile.load_json(image_input.raw_profile_path)
                profile_from_json = True
            except Exception as exc:  # noqa: BLE001 - user may correct it in the dialog
                QMessageBox.warning(
                    self,
                    "Cannot load RAW sidecar",
                    f"{image_input.raw_profile_path.name}: {exc}\nUsing editable defaults.",
                )
        elif existing_id is not None:
            initial_profile = self._raw_profiles.get(existing_id)
            if initial_profile is None:
                existing_document = self.documents.get(existing_id)
                if existing_document is not None and isinstance(
                    existing_document.raw_profile, RawProfile
                ):
                    initial_profile = existing_document.raw_profile

        source_matches_profile = False
        if initial_profile is not None:
            try:
                actual_size = image_input.path.stat().st_size
                required_size = required_file_size(initial_profile)
                source_matches_profile = (
                    actual_size == required_size
                    if self.application_settings.require_exact_raw_file_size
                    else actual_size >= required_size
                )
            except OSError:
                source_matches_profile = False
        if (
            profile_from_json
            and initial_profile is not None
            and self._dont_show_raw_json_profiles
            and source_matches_profile
        ):
            return initial_profile

        dialog = RawOpenDialog(self)
        set_source_path = getattr(dialog, "set_source_path", None)
        if callable(set_source_path):
            set_source_path(image_input.path)
        if initial_profile is not None:
            dialog.set_profile(initial_profile)
        set_option_visible = getattr(
            dialog,
            "set_json_confirmation_option_visible",
            None,
        )
        if callable(set_option_visible):
            set_option_visible(profile_from_json)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        profile = dialog.profile()
        dont_show_requested = getattr(
            dialog,
            "dont_show_json_profiles_requested",
            None,
        )
        if not callable(dont_show_requested):
            dont_show_requested = getattr(
                dialog,
                "skip_json_confirmation_requested",
                None,
            )
        if profile_from_json and callable(dont_show_requested) and dont_show_requested():
            self._set_dont_show_raw_json_profiles(True)
        return profile

    def _mark_raw_for_reload(self, document_id: str, profile: RawProfile) -> None:
        document = self.documents.get(document_id)
        if document is None:
            return
        self._load_tokens[document_id] = self._load_tokens.get(document_id, 0) + 1
        document.source = None
        document.preview = None
        document.channel_layout = profile.channel_layout
        document.bit_depth = profile.bit_depth
        document.raw_profile = profile
        document.loading_state = "pending"
        document.error_state = None
        document.generation += 1
        document.statistics_cache.clear()
        document.histogram_cache.clear()
        self._update_document_item(document)

    def _ensure_loaded(self, document: ImageDocument) -> None:
        if document.loading_state != "pending" or document.source_path is None:
            return
        document.loading_state = "loading"
        self._update_document_item(document)
        profile = self._raw_profiles.get(document.document_id)
        profile_path = self._raw_profile_paths.get(document.document_id)
        if profile is None and profile_path is not None:
            try:
                profile = RawProfile.load_json(profile_path)
            except Exception as exc:  # noqa: BLE001 - profile error becomes a document error
                self._load_failed(
                    document.document_id,
                    document.source_path,
                    TaskError(
                        task_id="profile",
                        document_id=document.document_id,
                        generation=0,
                        message=str(exc),
                        exception_type=type(exc).__name__,
                        traceback_text="",
                    ),
                )
                return
        self._start_load(document.document_id, document.source_path, profile)

    def _start_load(self, target_id: str, path: Path, raw_profile: RawProfile | None) -> None:
        request_token = self._load_tokens.get(target_id, 0) + 1
        self._load_tokens[target_id] = request_token
        worker = ImageLoadWorker(
            path,
            raw_profile,
            require_exact_raw_size=self.application_settings.require_exact_raw_file_size,
        )
        worker.signals.started.connect(
            lambda _task_id, _document_id, _generation: self._load_started(path)
        )
        worker.signals.succeeded.connect(
            lambda _task_id, _document_id, _generation, result: self._load_succeeded(
                target_id, request_token, result
            )
        )
        worker.signals.failed.connect(
            lambda _task_id, _document_id, _generation, error: self._load_failed(
                target_id, path, error, request_token
            )
        )
        worker.signals.finished.connect(self._worker_finished)
        self._workers[worker.task_id] = worker
        self._load_worker_targets[worker.task_id] = target_id
        self._load_pool.start(worker)

    def _load_started(self, path: Path) -> None:
        self.structured_status.task.setText(f"Loading {path.name}…")
        self.statusBar().showMessage(f"Loading {path.name}...")

    def _load_succeeded(self, target_id: str, request_token: int, result: object) -> None:
        if (
            not isinstance(result, ImageDocument)
            or target_id not in self.documents
            or self._load_tokens.get(target_id) != request_token
        ):
            return
        previous_generation = self.documents[target_id].generation
        result.document_id = target_id
        result.generation = previous_generation
        self.documents[target_id] = result
        self._touch_resident(target_id)
        self._update_document_item(result)
        if self._selected_load_batch_complete():
            self._render_selection(preserve_view=True)
        self._evict_resident_documents()
        self.structured_status.task.setText("Ready")
        self.statusBar().showMessage(f"Loaded {result.display_name}", 2500)

    def _load_failed(
        self,
        target_id: str,
        path: Path,
        error: TaskError,
        request_token: int | None = None,
    ) -> None:
        if request_token is not None and self._load_tokens.get(target_id) != request_token:
            return
        LOGGER.error("Image load failed: %s\n%s", error.message, error.traceback_text)
        document = ImageDocument.error_document(path.name, error.message, path)
        document.document_id = target_id
        self.documents[target_id] = document
        self._update_document_item(document)
        if self._selected_load_batch_complete():
            self._render_selection(preserve_view=True)
        self.structured_status.task.setText("Error")
        self.statusBar().showMessage(f"Failed to load {path.name}: {error.message}", 5000)

    def _selected_load_batch_complete(self) -> bool:
        """Avoid presenting partially replaced pages during asynchronous pair loads."""

        return all(
            document.loading_state not in ("pending", "loading")
            for document in self.selected_documents[:6]
        )

    def _worker_finished(self, task_id: str) -> None:
        self._workers.pop(task_id, None)
        self._load_worker_targets.pop(task_id, None)
        if not self._workers:
            self.structured_status.task.setText("Ready")

    def _cancel_obsolete_loads(self, required_ids: set[str]) -> None:
        """Invalidate queued loads that rapid navigation has moved away from."""

        for task_id, target_id in tuple(self._load_worker_targets.items()):
            if target_id in required_ids:
                continue
            worker = self._workers.get(task_id)
            if worker is not None:
                worker.cancel()
            self._load_tokens[target_id] = self._load_tokens.get(target_id, 0) + 1
            document = self.documents.get(target_id)
            if document is not None and document.loading_state == "loading":
                document.loading_state = "pending"
                self._update_document_item(document)

    def _touch_resident(self, document_id: str) -> None:
        if document_id in self._resident_order:
            self._resident_order.remove(document_id)
        self._resident_order.append(document_id)

    def _evict_resident_documents(self) -> None:
        """Keep only a small reloadable working set of decoded image arrays."""

        resident = [
            document_id
            for document_id in self._resident_order
            if (document := self.documents.get(document_id)) is not None
            and document.source_path is not None
            and document.source is not None
        ]
        excess = len(resident) - self._resident_document_limit
        if excess <= 0:
            return
        protected = self._visible_document_ids | set(self._load_worker_targets.values())
        for document_id in resident:
            if excess <= 0:
                break
            if document_id in protected:
                continue
            document = self.documents.get(document_id)
            if document is None or document.source_path is None:
                continue
            document.source = None
            document.preview = None
            document.statistics_cache.clear()
            document.histogram_cache.clear()
            document.loading_state = "pending"
            self._channel_view_cache = {
                key: value
                for key, value in self._channel_view_cache.items()
                if key[0] != document_id
            }
            self._resident_order.remove(document_id)
            self._update_document_item(document)
            excess -= 1

    def _selection_changed(self) -> None:
        selected_ids = [
            str(item.data(0, Qt.ItemDataRole.UserRole))
            for item in self.document_list.document_items()
            if item.isSelected()
        ]
        selected_set = set(selected_ids)
        if (
            self._difference_source_ids is not None
            and not set(self._difference_source_ids).issubset(selected_set)
            and not (
                len(selected_ids) >= 2
                and hasattr(self, "diff_action")
                and self.diff_action.isChecked()
            )
        ):
            self._difference_document = None
            self._difference_source_ids = None
        self._selection_order = [
            document_id for document_id in self._selection_order if document_id in selected_set
        ]
        self._selection_order.extend(
            document_id for document_id in selected_ids if document_id not in self._selection_order
        )
        for document_id in selected_ids:
            self._remember_folder_index(document_id)
        self._current_index = 0
        self._page_start = 0
        self._shared_roi = None
        self.comparison_analysis_panel.set_roi_available(False)
        self._shared_line = None
        self._reset_pixel_status()
        self._render_selection()

    def _render_selection(self, preserve_view: bool = False) -> None:
        documents = self.selected_documents
        selected_ids = {document.document_id for document in documents}
        if (
            self._difference_source_ids is not None
            and not set(self._difference_source_ids).issubset(selected_ids)
            and not (
                len(documents) >= 2
                and hasattr(self, "diff_action")
                and self.diff_action.isChecked()
            )
        ):
            self._difference_document = None
            self._difference_source_ids = None
        self._update_action_states()
        self._update_layout_options(len(documents))
        self._channel_split_active = False
        if not documents:
            self._visible_document_ids.clear()
            self._cancel_obsolete_loads(set())
            self.viewer.set_document(None)
            self.viewer.set_navigation_items([], "")
            self.multi_compare_view.set_documents([], 0, 0, None, None, preserve_view)
            self.comparison_analysis_panel.clear()
            self.line_profile_panel.clear()
            self._reset_pixel_status()
            self.central_stack.setCurrentWidget(self.empty_workspace)
            self._active_document_id = None
            self.structured_status.set_active_document()
            self._update_file_states([], None)
            return

        analysis_candidates = documents[:6]
        for document in analysis_candidates:
            self._ensure_loaded(document)
        analysis_ready = [
            document for document in analysis_candidates if document.source is not None
        ]

        self.difference_panel.set_documents(
            analysis_ready,
            None,
            self._shared_roi,
        )
        cached_display = self.difference_panel.cached_display_for_current()
        if cached_display is not None:
            self._store_difference_document(*cached_display, switch_to_result=False)
        elif (
            len(documents) >= 2
            and len(analysis_ready) >= 2
            and hasattr(self, "diff_action")
            and self.diff_action.isChecked()
        ):
            self.difference_panel.calculate_difference()
        self._update_action_states()

        display_documents = documents
        difference_document = self._difference_document
        show_difference = (
            len(documents) >= 2
            and difference_document is not None
            and hasattr(self, "diff_action")
            and self.diff_action.isChecked()
        )
        if show_difference and self._layout_mode != "Single View":
            assert difference_document is not None
            if difference_document.document_id not in self._multi_display_order:
                self._promote_multi_document(difference_document.document_id)
            display_documents = [difference_document, *documents]

        if self._layout_mode != "Single View":
            display_documents = self._ordered_multi_documents(display_documents)

        effective_layout, capacity = self._effective_layout(len(display_documents))
        self._view_capacity = capacity
        if len(display_documents) in (3, 5) and self._focus_document_id not in {
            document.document_id for document in display_documents
        }:
            self._focus_document_id = display_documents[0].document_id

        self._current_index = min(self._current_index, len(documents) - 1)
        if self._view_capacity == 1:
            self._page_start = (self._current_index // 6) * 6
        else:
            last_page = ((len(display_documents) - 1) // self._view_capacity) * self._view_capacity
            self._page_start = min(self._page_start, last_page)
        if self._view_capacity == 1:
            document = documents[self._current_index]
            self._ensure_loaded(document)
            self.viewer.set_document(document, fit=not preserve_view)
            self.viewer.set_tile_context(self._current_index + 1, "")
            self.viewer.set_header(
                f"[{self._current_index + 1}/{len(documents)}] {document.display_name}"
            )
            self._set_single_navigation(document.document_id)
            self.viewer.set_roi_bounds(self._shared_roi)
            self.viewer.set_line_selection(self._shared_line)
            self.central_stack.setCurrentWidget(self.viewer)
            visible_state = [document]
        elif self._view_capacity == 4 and self._split_channels and len(documents) == 1:
            document = documents[0]
            channel_documents, split_active = self._split_display_documents(document)
            self._channel_split_active = split_active
            self.multi_compare_view.set_capacity(4)
            self.multi_compare_view.set_documents(
                channel_documents,
                0,
                len(channel_documents),
                None,
                None,
                preserve_view,
            )
            self.central_stack.setCurrentWidget(self.multi_compare_view)
            visible_state = [document]
        else:
            start = self._page_start
            self._page_start = start
            visible = display_documents[start : start + self._view_capacity]
            for document in visible:
                self._ensure_loaded(document)
            self.multi_compare_view.set_capacity(self._view_capacity)
            self.multi_compare_view.set_layout_kind(
                effective_layout,
                self._focus_document_id,
            )
            self.multi_compare_view.set_documents(
                visible,
                start,
                len(display_documents),
                self._shared_roi,
                self._shared_line,
                preserve_view,
                {document.document_id: index + 1 for index, document in enumerate(documents)},
            )
            self.central_stack.setCurrentWidget(self.multi_compare_view)
            visible_state = [
                document for document in visible if document is not self._difference_document
            ]

        self._visible_document_ids = {document.document_id for document in visible_state}
        analysis_ids = {document.document_id for document in analysis_candidates}
        self._cancel_obsolete_loads(self._visible_document_ids | analysis_ids)
        for document in visible_state:
            if document.source is not None:
                self._touch_resident(document.document_id)
        self._evict_resident_documents()

        visible_ready = [document for document in visible_state if document.source is not None]
        self._normalize_shared_roi(visible_ready)
        self._normalize_shared_line(visible_ready)
        region_name = self.comparison_analysis_panel.region_scope.currentText()
        analysis_bounds = self._shared_roi if region_name == "Active ROI" else None
        self.comparison_analysis_panel.set_documents(
            analysis_ready,
            analysis_bounds,
            region_name,
        )
        active = self.current_document
        if self._view_capacity > 1 and self._focus_document_id is not None:
            active = next(
                (
                    document
                    for document in visible_state
                    if document.document_id == self._focus_document_id
                ),
                active,
            )
        line_sources = self._line_source_documents()
        self.line_profile_panel.set_documents(
            line_sources,
            self._shared_line,
            reference_priority_ids=self._line_reference_priority_ids(
                visible_state,
                active,
            ),
        )
        if cached_display is not None and self._view_capacity == 1 and active is not None:
            self._set_single_navigation(active.document_id)
        self._set_active_document(active)
        self._update_file_states(visible_state, active)

    def _split_display_documents(
        self,
        document: ImageDocument,
    ) -> tuple[list[ImageDocument], bool]:
        """Return real channel views or stable loading placeholders for split mode."""

        if document.source is not None:
            cache_key = (document.document_id, document.generation)
            channel_documents = self._channel_view_cache.get(cache_key)
            if channel_documents is None:
                channel_documents = split_document_channels(document)
                self._channel_view_cache = {cache_key: channel_documents}
            if channel_documents:
                return channel_documents, True
            return [document], False

        profile = document.raw_profile or self._raw_profiles.get(document.document_id)
        is_bayer = (
            document.channel_layout == "BAYER"
            or getattr(
                profile,
                "channel_layout",
                None,
            )
            == "BAYER"
        )
        labels = ("R", "Gr", "Gb", "B") if is_bayer else ("R", "G", "B")
        placeholders = [
            ImageDocument(
                source_path=document.source_path,
                display_name=f"{document.display_name} · {label}",
                source=None,
                channel_layout=f"CHANNEL_{label}",
                bit_depth=document.bit_depth,
                raw_profile=profile,
                display_transform=document.display_transform,
                document_id=f"{document.document_id}:split:{label}",
                loading_state=document.loading_state,
                error_state=document.error_state,
                generation=document.generation,
            )
            for label in labels
        ]
        return placeholders, False

    def _set_split_channels(self, enabled: bool) -> None:
        self._split_channels = enabled
        if enabled:
            self._layout_mode = "Multi View"
            self._view_capacity = 4
        self._reset_pixel_status()
        self._render_selection(preserve_view=False)

    def compare_selection(self) -> None:
        count = len(self.selected_documents)
        if count < 2:
            QMessageBox.information(
                self, "Comparison selection", "Select two or more documents in the list."
            )
            return

    def set_view_capacity(self, capacity: int) -> None:
        if capacity not in (1, 2, 4, 6):
            raise ValueError("viewer capacity must be 1, 2, 4, or 6")
        mode = "Single View" if capacity == 1 else "Multi View"
        self.set_layout_mode(mode)

    def set_layout_mode(self, mode: str) -> None:
        if mode not in ("Auto", "Single View", "Multi View"):
            raise ValueError(f"unsupported layout: {mode}")
        if mode in ("Auto", "Multi View") and self._six_image_diff_locked():
            self.statusBar().showMessage(
                "Multi View is unavailable while six images and Diff are displayed.", 3500
            )
            self.layout_selector.blockSignals(True)
            self.layout_selector.setCurrentText("Single View")
            self.layout_selector.blockSignals(False)
            return
        if mode == self._layout_mode and self._layout_mode_is_presented(mode):
            return
        previous_active_id = self._active_document_id
        previous_was_difference = (
            self._difference_document is not None
            and previous_active_id == self._difference_document.document_id
        )
        changed = mode != self._layout_mode
        self._layout_mode = mode
        self.settings.setValue("ui/layout", mode)
        _effective, capacity = self._effective_layout(len(self.selected_documents))
        self._view_capacity = capacity
        if hasattr(self, "layout_selector"):
            self.layout_selector.blockSignals(True)
            self.layout_selector.setCurrentText(mode)
            self.layout_selector.blockSignals(False)
        self._page_start = (
            self._current_index if capacity == 1 else (self._current_index // capacity) * capacity
        )
        if mode == "Single View" and previous_active_id is not None:
            selected_index = next(
                (
                    index
                    for index, document in enumerate(self.selected_documents)
                    if document.document_id == previous_active_id
                ),
                None,
            )
            if selected_index is not None:
                self._current_index = selected_index
                self._page_start = 0
        if changed:
            self._reset_pixel_status()
        self._render_selection(preserve_view=not changed)
        if mode == "Single View" and previous_was_difference:
            self._navigate_single_view("difference")

    def _layout_mode_is_presented(self, mode: str) -> bool:
        """Return whether the stacked workspace already represents the requested mode."""

        document_count = len(self.selected_documents)
        expects_multi = mode != "Single View" and (document_count > 1 or self._split_channels)
        expected_widget = self.multi_compare_view if expects_multi else self.viewer
        if document_count == 0:
            expected_widget = self.empty_workspace
        if self.central_stack.currentWidget() is not expected_widget:
            return False
        if expects_multi:
            display_count = document_count
            if self.diff_action.isChecked() and self._difference_document is not None:
                display_count += 1
            expected_capacity = self._effective_layout(display_count)[1]
            return self.multi_compare_view.capacity == expected_capacity and bool(
                self.multi_compare_view.occupied_viewers
            )
        return True

    def _effective_layout(self, count: int) -> tuple[str, int]:
        if self._layout_mode == "Single View":
            return "Single", 1
        if count <= 1:
            return ("Grid 2x2", 4) if self._split_channels else ("Single", 1)
        if count == 2:
            return "Side by Side", 2
        if count == 3:
            return "Focus + 2", 4
        if count == 4:
            return "Grid 2x2", 4
        return "Grid 3x2", 6

    def _update_layout_options(self, count: int) -> None:
        del count
        if not hasattr(self, "layout_selector"):
            return
        self.layout_selector.blockSignals(True)
        self.layout_selector.setCurrentText(self._layout_mode)
        self.layout_selector.blockSignals(False)

    def _set_focus_document(self, document: object) -> None:
        document_id = document.document_id if isinstance(document, ImageDocument) else str(document)
        allowed_ids = {item.document_id for item in self.selected_documents}
        if self.diff_action.isChecked() and self._difference_document is not None:
            allowed_ids.add(self._difference_document.document_id)
        if document_id not in allowed_ids:
            return
        self._promote_multi_document(document_id)
        self._focus_document_id = document_id
        self._render_selection(preserve_view=True)

    def _ordered_multi_documents(self, documents: list[ImageDocument]) -> list[ImageDocument]:
        by_id = {document.document_id: document for document in documents}
        retained = [
            document_id for document_id in self._multi_display_order if document_id in by_id
        ]
        retained.extend(
            document.document_id for document in documents if document.document_id not in retained
        )
        self._multi_display_order = retained
        return [by_id[document_id] for document_id in retained]

    def _promote_multi_document(self, document_id: str) -> None:
        self._multi_display_order = [
            document_id,
            *[item for item in self._multi_display_order if item != document_id],
        ]

    def _analysis_scope_changed(self) -> None:
        region = self.comparison_analysis_panel.region_scope.currentText()
        bounds = self._shared_roi
        if region != "Full image" and bounds is None:
            self.comparison_analysis_panel.region_scope.blockSignals(True)
            self.comparison_analysis_panel.region_scope.setCurrentText("Full image")
            self.comparison_analysis_panel.region_scope.blockSignals(False)
            self.statusBar().showMessage(f"{region} is not available.", 3000)
        self._render_selection(preserve_view=True)

    def _line_source_documents(
        self, visible_documents: list[ImageDocument] | None = None
    ) -> list[ImageDocument]:
        del visible_documents
        return [document for document in self.selected_documents[:6] if document.source is not None]

    def _line_reference_priority_ids(
        self,
        visible_documents: Sequence[ImageDocument],
        active_document: ImageDocument | None,
    ) -> tuple[str, ...]:
        source_ids = {document.document_id for document in self._line_source_documents()}
        first_displayed_id = next(
            (
                document.document_id
                for document in visible_documents
                if document.document_id in source_ids
            ),
            None,
        )
        candidates = (
            self._focus_document_id,
            active_document.document_id if active_document is not None else None,
            first_displayed_id,
        )
        ordered: list[str] = []
        for document_id in candidates:
            if document_id is not None and document_id in source_ids and document_id not in ordered:
                ordered.append(document_id)
        return tuple(ordered)

    def _set_active_document(self, document: object) -> None:
        if not isinstance(document, ImageDocument):
            self.structured_status.set_active_document()
            return
        self._active_document_id = document.document_id
        shape = document.shape
        resolution = f"{shape[1]}×{shape[0]}" if len(shape) >= 2 else "—"
        file_format = (document.source_path or Path(document.display_name)).suffix.upper().lstrip(
            "."
        ) or document.channel_layout
        self.structured_status.set_active_document(
            document.display_name,
            f"{resolution} · {file_format} · {document.bit_depth}-bit",
        )
        self._update_action_states()

    def _active_tile_changed(self, document: object) -> None:
        self._set_active_document(document)
        if not isinstance(document, ImageDocument):
            return
        visible = [
            viewer.document
            for viewer in self.multi_compare_view.occupied_viewers
            if viewer.document is not None
        ]
        self.line_profile_panel.set_reference_priority_ids(
            self._line_reference_priority_ids(visible, document)
        )
        self._update_file_states(visible, document)

    def _set_zoom_status(self, percent: float) -> None:
        self.structured_status.zoom.setText(f"Zoom {percent:.0f}%")

    def _update_file_states(
        self,
        visible_documents: Sequence[ImageDocument],
        active_document: ImageDocument | None,
    ) -> None:
        visible_ids = {document.document_id for document in visible_documents}
        for document_id, document in self.documents.items():
            self.document_list.set_document_state(
                document_id,
                visible=document_id in visible_ids,
                active=active_document is not None and document_id == active_document.document_id,
                loading_state=document.loading_state,
                resident=document.source is not None,
            )

    def show_selected_image(self, selected_index: int) -> None:
        documents = self.selected_documents
        if (
            self._view_capacity == 1
            and selected_index == len(documents)
            and len(documents) >= 2
            and self._difference_document is not None
            and self.diff_action.isChecked()
        ):
            self._navigate_single_view("difference")
            return
        if (
            self._view_capacity != 1
            or selected_index < 0
            or selected_index >= min(6, len(documents))
        ):
            return
        self._current_index = selected_index
        self._page_start = 0
        self._reset_pixel_status()
        self._render_selection(preserve_view=True)

    def _set_single_navigation(self, current_key: str) -> None:
        items = [
            (document.document_id, str(index + 1), document.display_name)
            for index, document in enumerate(self.selected_documents[:6])
        ]
        if (
            self._difference_document is not None
            and hasattr(self, "diff_action")
            and self.diff_action.isChecked()
        ):
            items.append(("difference", "Diff", self._difference_document.display_name))
        self.viewer.set_navigation_items(items, current_key)

    def _set_difference_visible(self, enabled: bool) -> None:
        if enabled:
            cached = self.difference_panel.cached_display_for_current()
            if cached is None:
                self.diff_action.blockSignals(True)
                self.diff_action.setChecked(False)
                self.diff_action.blockSignals(False)
                return
            self._store_difference_document(*cached, switch_to_result=False)
            if len(self.selected_documents) >= 6:
                self._capture_six_image_diff_restore_state()
                self._navigate_single_view("difference")
                self._update_action_states()
                return
            if self._layout_mode == "Single View":
                self._navigate_single_view("difference")
                if self._difference_document is not None:
                    self._set_active_document(self._difference_document)
                self._update_action_states()
                return
            self._layout_mode = "Multi View"
            if self._difference_document is not None:
                self._focus_document_id = self._difference_document.document_id
                self._promote_multi_document(self._difference_document.document_id)
            self.layout_selector.blockSignals(True)
            self.layout_selector.setCurrentText("Multi View")
            self.layout_selector.blockSignals(False)
        elif self._six_image_diff_restore_state is not None:
            self._restore_six_image_diff_workspace()
            return
        elif self.viewer.document is self._difference_document:
            self._current_index = 0
        self._render_selection(preserve_view=True)
        self._update_action_states()

    def _capture_six_image_diff_restore_state(self) -> None:
        if self._six_image_diff_restore_state is not None:
            return
        self._six_image_diff_restore_state = SixImageDiffRestoreState(
            layout_mode=self._layout_mode,
            focus_document_id=self._focus_document_id,
            active_document_id=self._active_document_id,
            page_start=self._page_start,
            current_index=self._current_index,
            display_order=tuple(self._multi_display_order),
            view_state=self.multi_compare_view.capture_view_state(),
        )

    def _restore_six_image_diff_workspace(self) -> None:
        state = self._six_image_diff_restore_state
        if state is None:
            return
        self._six_image_diff_restore_state = None
        self._layout_mode = state.layout_mode
        self._focus_document_id = state.focus_document_id
        self._active_document_id = state.active_document_id
        self._page_start = state.page_start
        self._current_index = state.current_index
        self._multi_display_order = list(state.display_order)
        self.layout_selector.blockSignals(True)
        self.layout_selector.setCurrentText(state.layout_mode)
        self.layout_selector.blockSignals(False)
        self._render_selection(preserve_view=True)
        self.multi_compare_view.restore_view_state(state.view_state)
        self._update_action_states()

    def _navigate_single_view(self, key: str) -> None:
        if key == "difference":
            difference = self._difference_document
            if difference is None:
                return
            self._layout_mode = "Single View"
            self._view_capacity = 1
            self.layout_selector.blockSignals(True)
            self.layout_selector.setCurrentText("Single View")
            self.layout_selector.blockSignals(False)
            self.viewer.set_document(difference, fit=False)
            self.viewer.set_tile_context(1, "Diff")
            self.viewer.set_header(difference.display_name)
            self._set_single_navigation("difference")
            self.central_stack.setCurrentWidget(self.viewer)
            self._reset_pixel_status()
            return
        documents = self.selected_documents
        selected_index = next(
            (index for index, document in enumerate(documents) if document.document_id == key),
            None,
        )
        if selected_index is None:
            return
        self._show_single_document(documents[selected_index], selected_index)

    def _show_single_document(self, document: ImageDocument, selected_index: int) -> None:
        """Switch a single tile without rebuilding the complete comparison workspace."""

        self._layout_mode = "Single View"
        self._view_capacity = 1
        self._current_index = selected_index
        self.layout_selector.blockSignals(True)
        self.layout_selector.setCurrentText("Single View")
        self.layout_selector.blockSignals(False)
        self._ensure_loaded(document)
        self.viewer.set_document(document, fit=False)
        self.viewer.set_tile_context(selected_index + 1, "")
        self.viewer.set_header(
            f"[{selected_index + 1}/{len(self.selected_documents)}] {document.display_name}"
        )
        self._set_single_navigation(document.document_id)
        self.viewer.set_roi_bounds(self._shared_roi)
        self.viewer.set_line_selection(self._shared_line)
        self.central_stack.setCurrentWidget(self.viewer)
        self._set_active_document(document)
        self._update_file_states([document], document)
        region_name = self.comparison_analysis_panel.region_scope.currentText()
        analysis_bounds = self._shared_roi if region_name == "Active ROI" else None
        self.comparison_analysis_panel.set_documents([document], analysis_bounds, region_name)
        self.line_profile_panel.set_documents(
            self._line_source_documents([document]),
            self._shared_line,
        )
        self._reset_pixel_status()

    def next_image(self) -> None:
        documents = self.selected_documents
        if not documents:
            return
        if self._view_capacity == 1:
            if self._cycle_single_navigation(1):
                return
            self._current_index = 0
        elif self._cycle_visible_focus(1):
            return
        else:
            next_start = self._page_start + self._view_capacity
            self._page_start = next_start if next_start < len(documents) else 0
            self._current_index = self._page_start
        self._reset_pixel_status()
        self._render_selection(preserve_view=True)

    def previous_image(self) -> None:
        documents = self.selected_documents
        if not documents:
            return
        if self._view_capacity == 1:
            if self._cycle_single_navigation(-1):
                return
            self._current_index = 0
        elif self._cycle_visible_focus(-1):
            return
        else:
            self._page_start = (
                self._page_start - self._view_capacity
                if self._page_start >= self._view_capacity
                else ((len(documents) - 1) // self._view_capacity) * self._view_capacity
            )
            self._current_index = self._page_start
        self._reset_pixel_status()
        self._render_selection(preserve_view=True)

    def _cycle_single_navigation(self, step: int) -> bool:
        documents = self.selected_documents
        keys = [document.document_id for document in documents]
        if self.diff_action.isChecked() and self._difference_document is not None:
            keys.append("difference")
        if len(keys) < 2:
            return False
        current_key = (
            "difference"
            if self.viewer.document is self._difference_document
            else self.viewer.document.document_id
            if self.viewer.document is not None
            else keys[0]
        )
        current = keys.index(current_key) if current_key in keys else 0
        self._navigate_single_view(keys[(current + step) % len(keys)])
        return True

    def _cycle_visible_focus(self, step: int) -> bool:
        documents = self.selected_documents
        candidates = list(documents)
        if (
            self.diff_action.isChecked()
            and self._difference_document is not None
            and len(documents) >= 2
        ):
            candidates = [self._difference_document, *documents]
        if len(candidates) > self._view_capacity or len(candidates) < 2:
            return False
        ids = [document.document_id for document in candidates]
        current = ids.index(self._focus_document_id) if self._focus_document_id in ids else 0
        self._focus_document_id = ids[(current + step) % len(ids)]
        self._promote_multi_document(self._focus_document_id)
        self._reset_pixel_status()
        self._render_selection(preserve_view=True)
        return True

    def next_folder_pair(self) -> None:
        self._navigate_folder_pair(1)

    def previous_folder_pair(self) -> None:
        self._navigate_folder_pair(-1)

    def _navigate_folder_pair(self, step: int) -> None:
        session = self._active_folder_selection()
        if session is None:
            self.statusBar().showMessage(
                "Pair navigation requires one selected file from each different folder",
                5000,
            )
            return
        target_ids: list[str] = []
        target_indices: list[int] = []
        for folder_key, current_id in session:
            folder_documents = self._folder_documents.get(folder_key, [])
            try:
                current_index = folder_documents.index(current_id)
            except ValueError:
                return
            target_index = current_index + step
            if target_index < 0 or target_index >= len(folder_documents):
                direction = "previous" if step < 0 else "next"
                folder_name = self._folder_paths[folder_key].name
                self.statusBar().showMessage(
                    f"No {direction} image in {folder_name}; pair was not changed",
                    5000,
                )
                return
            target_ids.append(folder_documents[target_index])
            target_indices.append(target_index)
        if self.diff_action.isChecked() and len(self.selected_documents) == 2:
            current_ids = [document.document_id for document in self.selected_documents]
            if self._focus_document_id in current_ids:
                self._pending_pair_focus = current_ids.index(self._focus_document_id)
            else:
                self._pending_pair_focus = "difference"
        for (folder_key, _current_id), index in zip(session, target_indices, strict=True):
            self._folder_indices[folder_key] = index
        if isinstance(self._pending_pair_focus, int):
            self._focus_document_id = target_ids[self._pending_pair_focus]
            self._promote_multi_document(self._focus_document_id)
        self._select_document_ids(
            target_ids,
            preserve_view=True,
            preserve_overlays=True,
        )
        positions = ", ".join(
            f"{index + 1}/{len(self._folder_documents[folder_key])}"
            for (folder_key, _current_id), index in zip(session, target_indices, strict=True)
        )
        self.statusBar().showMessage(f"Folder positions · {positions}", 3000)

    def select_all_documents(self) -> None:
        self.document_list.selectAll()

    def remove_selected(self) -> None:
        selected_ids = [
            str(item.data(0, Qt.ItemDataRole.UserRole))
            for item in self.document_list.selected_document_items()
        ]
        self._remove_document_ids(selected_ids)

    def _remove_document_ids(self, selected_ids: object) -> None:
        if not isinstance(selected_ids, list):
            return
        self.document_list.blockSignals(True)
        try:
            for document_id in selected_ids:
                document = self.documents.pop(document_id, None)
                if document is not None and document.source_path is not None:
                    self._document_id_by_path.pop(self._path_key(document.source_path), None)
                    self._remove_document_from_folder(document_id, document.source_path)
                self.document_list.remove_document_item(document_id)
        finally:
            self.document_list.blockSignals(False)
        selected_set = set(selected_ids)
        self._selection_order = [
            document_id for document_id in self._selection_order if document_id not in selected_set
        ]
        self._render_selection()

    def _select_document_ids(
        self,
        document_ids: list[str],
        preserve_view: bool = False,
        preserve_overlays: bool = False,
    ) -> None:
        selected = set(document_ids)
        self.document_list.blockSignals(True)
        self.document_list.clearSelection()
        first_item: QTreeWidgetItem | None = None
        for item in self.document_list.document_items():
            if str(item.data(0, Qt.ItemDataRole.UserRole)) in selected:
                item.setSelected(True)
                if first_item is None:
                    first_item = item
        if first_item is not None:
            self.document_list.setCurrentItem(
                first_item,
                0,
                QItemSelectionModel.SelectionFlag.NoUpdate,
            )
        self.document_list.blockSignals(False)
        self._selection_order = [
            document_id for document_id in document_ids if document_id in self.documents
        ]
        self._cancel_obsolete_loads(set(self._selection_order))
        for document_id in self._selection_order:
            self._remember_folder_index(document_id)
        if not preserve_view:
            self._current_index = 0
            self._page_start = 0
        if not preserve_overlays:
            self._shared_roi = None
            self.comparison_analysis_panel.set_roi_available(False)
            self._shared_line = None
        self._reset_pixel_status()
        self._render_selection(preserve_view=preserve_view)

    def _shared_roi_changed(self, bounds: object) -> None:
        if self._channel_split_active:
            return
        if not isinstance(bounds, RoiBounds):
            return
        self.comparison_analysis_panel.set_roi_available(True)
        ready = [
            document
            for document in self.selected_documents[
                self._page_start : self._page_start
                + (6 if self._view_capacity == 1 else self._view_capacity)
            ]
            if document.source is not None
        ]
        if not ready:
            return
        common_height = min(document.shape[0] for document in ready)
        common_width = min(document.shape[1] for document in ready)
        try:
            self._shared_roi = clamp_roi(
                (common_height, common_width),
                bounds.x,
                bounds.y,
                bounds.width,
                bounds.height,
            )
        except ValueError:
            return
        self.viewer.set_roi_bounds(self._shared_roi)
        self.multi_compare_view.set_shared_roi(self._shared_roi)
        self.comparison_analysis_panel.set_documents(ready[:6], self._shared_roi)
        self.difference_panel.set_active_roi(self._shared_roi)
        roi = self._shared_roi
        self.statusBar().showMessage(f"ROI x={roi.x}, y={roi.y}, {roi.width} x {roi.height}", 3000)

    def _normalize_shared_roi(self, documents: list[ImageDocument]) -> None:
        bounds = self._shared_roi
        if bounds is None or not documents:
            return
        common_height = min(document.shape[0] for document in documents)
        common_width = min(document.shape[1] for document in documents)
        try:
            self._shared_roi = clamp_roi(
                (common_height, common_width),
                bounds.x,
                bounds.y,
                bounds.width,
                bounds.height,
            )
        except ValueError:
            self._shared_roi = None
            self.comparison_analysis_panel.set_roi_available(False)

    def _shared_line_changed(self, selection: object) -> None:
        if self._channel_split_active:
            return
        if not isinstance(selection, LineSelection):
            return
        ready = [
            document
            for document in self.selected_documents[
                self._page_start : self._page_start
                + (6 if self._view_capacity == 1 else self._view_capacity)
            ]
            if document.source is not None
        ]
        if not ready:
            return
        common_height = min(document.shape[0] for document in ready)
        common_width = min(document.shape[1] for document in ready)
        try:
            self._shared_line = clamp_line(
                (common_height, common_width),
                selection.x1,
                selection.y1,
                selection.x2,
                selection.y2,
            )
        except ValueError:
            return
        self.viewer.set_line_selection(self._shared_line)
        self.multi_compare_view.set_shared_line(self._shared_line)
        self.line_profile_panel.set_documents(
            self._line_source_documents(ready),
            self._shared_line,
        )
        self.bottom_tabs.setCurrentIndex(1)
        self._show_bottom_results()

    def _normalize_shared_line(self, documents: list[ImageDocument]) -> None:
        selection = self._shared_line
        if selection is None or not documents:
            return
        common_height = min(document.shape[0] for document in documents)
        common_width = min(document.shape[1] for document in documents)
        try:
            self._shared_line = clamp_line(
                (common_height, common_width),
                selection.x1,
                selection.y1,
                selection.x2,
                selection.y2,
            )
        except ValueError:
            self._shared_line = None

    def clear_roi(self) -> None:
        self._shared_roi = None
        self.comparison_analysis_panel.set_roi_available(False)
        self.viewer.set_roi_bounds(None)
        self.multi_compare_view.clear_roi()
        ready = [
            document
            for document in self.selected_documents[
                self._page_start : self._page_start
                + (6 if self._view_capacity == 1 else self._view_capacity)
            ]
            if document.source is not None
        ]
        self.comparison_analysis_panel.set_documents(ready, None)
        self.difference_panel.set_active_roi(None)

    def clear_line(self) -> None:
        self._shared_line = None
        self.viewer.set_line_selection(None)
        self.multi_compare_view.clear_line()
        self.line_profile_panel.clear_selection()

    def _difference_panel_ready(
        self,
        title: object,
        numerical: object,
        preview: object,
    ) -> None:
        if (
            not isinstance(title, str)
            or not isinstance(numerical, np.ndarray)
            or not isinstance(preview, np.ndarray)
        ):
            return
        force_single = len(self.selected_documents) >= 6
        if force_single:
            self._capture_six_image_diff_restore_state()
        stay_single = force_single or self._layout_mode == "Single View"
        self._store_difference_document(
            title,
            numerical,
            preview,
            switch_to_result=stay_single,
        )
        self.diff_action.blockSignals(True)
        self.diff_action.setChecked(True)
        self.diff_action.blockSignals(False)
        if stay_single:
            self._set_single_navigation("difference")
            if self._difference_document is not None:
                self._set_active_document(self._difference_document)
            self._update_action_states()
            self.statusBar().showMessage(f"Ready: {title}", 4000)
            return

        self._layout_mode = "Multi View"
        if self._difference_document is not None:
            self._focus_document_id = self._difference_document.document_id
            self._promote_multi_document(self._difference_document.document_id)
        self._pending_pair_focus = None
        self.layout_selector.blockSignals(True)
        self.layout_selector.setCurrentText("Multi View")
        self.layout_selector.blockSignals(False)
        self._render_selection(preserve_view=True)
        self.statusBar().showMessage(f"Ready: {title}", 4000)

    def _difference_preview_updated(
        self,
        title: object,
        numerical: object,
        preview: object,
    ) -> None:
        if (
            not isinstance(title, str)
            or not isinstance(numerical, np.ndarray)
            or not isinstance(preview, np.ndarray)
        ):
            return
        showing_single_difference = (
            self.central_stack.currentWidget() is self.viewer
            and self.viewer.document is self._difference_document
        )
        visible = self.diff_action.isChecked()
        self._store_difference_document(title, numerical, preview, switch_to_result=False)
        if showing_single_difference and self._difference_document is not None:
            self.viewer.set_document(self._difference_document, fit=False)
            self.viewer.set_tile_context(1, "Diff")
            self.viewer.set_header(title)
            self._set_single_navigation("difference")
        elif visible:
            assert self._difference_document is not None
            self.multi_compare_view.refresh_document(self._difference_document)

    def _store_difference_document(
        self,
        title: str,
        numerical: NDArray[np.generic],
        preview: NDArray[np.uint8],
        *,
        switch_to_result: bool,
    ) -> None:
        previous_difference = self._difference_document
        preserve_view = (
            self.viewer.document is previous_difference and previous_difference is not None
        )
        pair = self.difference_panel.selected_documents()
        source_ids = (pair[0].document_id, pair[1].document_id) if pair is not None else None
        if (
            previous_difference is not None
            and self._difference_source_ids is not None
            and source_ids is not None
            and set(self._difference_source_ids) == set(source_ids)
        ):
            difference = previous_difference
            difference.display_name = title
            difference.source = numerical
            difference.preview = preview
            difference.bit_depth = numerical.dtype.itemsize * 8
            difference.generation += 1
            difference.statistics_cache.clear()
            difference.histogram_cache.clear()
        else:
            difference = ImageDocument.from_array(
                numerical,
                title,
                channel_layout="DIFFERENCE",
                prepared_preview=preview,
            )
        self._difference_document = difference
        self._difference_source_ids = source_ids
        if not switch_to_result:
            return
        self._layout_mode = "Single View"
        self._view_capacity = 1
        self.layout_selector.blockSignals(True)
        self.layout_selector.setCurrentText("Single View")
        self.layout_selector.blockSignals(False)
        self.viewer.set_document(difference, fit=not preserve_view)
        self.viewer.set_tile_context(1, "Diff")
        self.viewer.set_header(title)
        self._set_single_navigation("difference")
        self.central_stack.setCurrentWidget(self.viewer)
        self._set_active_document(difference)
        self.statusBar().showMessage(f"Ready: {title}", 4000)

    def fit_image(self) -> None:
        if self.central_stack.currentWidget() is self.multi_compare_view:
            self.multi_compare_view.fit_images()
        else:
            self.viewer.fit_image()

    def zoom_100_percent(self) -> None:
        if self.central_stack.currentWidget() is self.multi_compare_view:
            self.multi_compare_view.zoom_100_percent()
        else:
            self.viewer.zoom_100_percent()

    def zoom_by(self, factor: float) -> None:
        if self.central_stack.currentWidget() is self.multi_compare_view:
            self.multi_compare_view.zoom_by(factor)
        else:
            self.viewer.zoom_by(factor)

    def _inspect_pixel(self, x: int, y: int, value: object) -> None:
        document = self.viewer.document
        if document is None:
            return
        self._set_pixel_status(self._pixel_status_text(x, y, [value], [document]))
        self._set_active_document(document)

    def _inspect_multi_pixel(self, document: object, x: int, y: int, value: object) -> None:
        if isinstance(document, ImageDocument):
            del value
            values = [
                viewer.document.pixel_at(x, y)
                for viewer in self.multi_compare_view.visible_viewers
                if viewer.document is not None
            ]
            documents = [
                viewer.document
                for viewer in self.multi_compare_view.visible_viewers
                if viewer.document is not None
            ]
            self._set_pixel_status(self._pixel_status_text(x, y, values, documents))
            self._set_active_document(document)

    @staticmethod
    def _pixel_status_text(
        x: int,
        y: int,
        values: Sequence[object],
        documents: Sequence[ImageDocument] | None = None,
    ) -> str:
        entries: list[str] = []
        for index, value in enumerate(values):
            document = (
                documents[index] if documents is not None and index < len(documents) else None
            )
            if isinstance(value, tuple):
                if len(value) == 4:
                    value = value[:3]
                labels = ("R", "G", "B")
                formatted = ", ".join(
                    (
                        f"{label}{component:4d}"
                        if isinstance(component, int)
                        else f"{label}{component:>7.4g}"
                    )
                    for label, component in zip(labels, value, strict=False)
                )
                value_text = f"({formatted})"
            elif isinstance(value, int):
                channel_name = MainWindow._scalar_channel_name(document, x, y)
                value_text = (
                    f"{channel_name} {value:4d}" if channel_name is not None else f"{value:4d}"
                )
            elif isinstance(value, float):
                channel_name = MainWindow._scalar_channel_name(document, x, y)
                value_text = (
                    f"{channel_name} {value:>7.4g}"
                    if channel_name is not None
                    else f"{value:>7.4g}"
                )
            else:
                value_text = "   —"
            entries.append(f"{index + 1} {value_text}")
        suffix = "  |  " + "  |  ".join(entries) if entries else ""
        return f"Position ({x:4d}, {y:4d}){suffix}"

    @staticmethod
    def _scalar_channel_name(
        document: ImageDocument | None,
        x: int,
        y: int,
    ) -> str | None:
        if document is None:
            return None
        if document.channel_layout.startswith("CHANNEL_"):
            return document.channel_layout.removeprefix("CHANNEL_")
        pattern = getattr(document.raw_profile, "bayer_pattern", None)
        if document.channel_layout == "BAYER" and isinstance(pattern, str):
            return bayer_channel_at(pattern, x, y)
        return None

    def _reset_pixel_status(self) -> None:
        self.structured_status.reset_cursor()

    def _set_pixel_status(self, text: str) -> None:
        coordinate, separator, values = text.partition("  |  ")
        self.structured_status.coordinate.setText(coordinate)
        self.structured_status.pixel_value.setText(values if separator else "—")

    @staticmethod
    def _rgb_comparison_source(document: ImageDocument) -> np.ndarray[Any, Any]:
        source = document.source
        if source is None:
            raise ValueError("comparison requires a loaded document")
        if source.ndim == 3 and source.shape[-1] == 4:
            return source[..., :3]
        return source

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            event.acceptProposedAction()
            self._handle_dropped_paths(paths)
            return
        super().dropEvent(event)

    def _handle_dropped_paths(self, paths: object) -> None:
        if not isinstance(paths, list) or not all(isinstance(path, Path) for path in paths):
            return
        folders = [path for path in paths if path.is_dir()]
        if len(paths) == 2 and len(folders) == 2:
            self.register_folder_pair(folders[0], folders[1])
            return
        session = self._active_folder_selection()
        if session is not None:
            self._register_paths_during_pair(paths, session)
            return
        inputs = discover_image_inputs(paths)
        self._register_inputs(
            inputs,
            select_all=len(paths) > 1 and not folders,
            append_selection=self._view_capacity > 1 and bool(self.selected_documents),
        )

    def _register_paths_during_pair(
        self,
        paths: list[Path],
        session: list[tuple[str, str]],
    ) -> None:
        active_by_folder = dict(session)
        grouped: dict[str, tuple[list[ImageInput], ImageInput, bool]] = {}
        for path in paths:
            resolved = path.resolve()
            is_folder = resolved.is_dir()
            inputs = list(discover_image_inputs((resolved,)))
            if not inputs:
                continue
            folder_key = self._folder_key(inputs[0].path)
            existing = grouped.get(folder_key)
            if existing is None:
                grouped[folder_key] = (inputs, inputs[0], is_folder)
            else:
                merged = list(
                    {self._path_key(item.path): item for item in [*existing[0], *inputs]}.values()
                )
                merged.sort(key=lambda item: natural_sort_key(item.path))
                grouped[folder_key] = (
                    merged,
                    existing[1],
                    existing[2] or is_folder,
                )

        selected_ids = [document_id for _folder_key, document_id in session]
        for folder_key, (supplied_inputs, primary_input, explicit_folder) in grouped.items():
            inputs_to_register = supplied_inputs
            if folder_key not in active_by_folder and not explicit_folder:
                siblings = list(discover_image_inputs((primary_input.path.parent,)))
                supplied_keys = {
                    self._path_key(image_input.path) for image_input in supplied_inputs
                }
                has_more_images = any(
                    self._path_key(image_input.path) not in supplied_keys
                    for image_input in siblings
                )
                if has_more_images:
                    answer = QMessageBox.question(
                        self,
                        "Include folder images?",
                        f"{primary_input.path.parent.name} contains other images. "
                        "Register all images from this folder?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.Yes,
                    )
                    if answer == QMessageBox.StandardButton.Yes:
                        inputs_to_register = siblings

            registered_ids: dict[str, str] = {}
            for image_input in inputs_to_register:
                registered_id = self._register_input(image_input)
                if registered_id is not None:
                    registered_ids[self._path_key(image_input.path)] = registered_id
            primary_id = registered_ids.get(self._path_key(primary_input.path))
            if primary_id is None:
                continue
            if folder_key in active_by_folder:
                current_id = active_by_folder[folder_key]
                if primary_id != current_id:
                    answer = QMessageBox.question(
                        self,
                        "Replace folder position?",
                        f"A file from {primary_input.path.parent.name} is already visible. "
                        f"Replace it with {primary_input.path.name}?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    if answer == QMessageBox.StandardButton.Yes:
                        selected_ids[selected_ids.index(current_id)] = primary_id
            else:
                if len(selected_ids) < 6:
                    selected_ids.append(primary_id)

        if len(selected_ids) > self._view_capacity and self._view_capacity > 1:
            self._view_capacity = 4 if len(selected_ids) <= 4 else 6
        self._select_document_ids(
            selected_ids,
            preserve_view=True,
            preserve_overlays=True,
        )
        self.statusBar().showMessage(
            "Files registered; folder positions updated where requested",
            4000,
        )

    def _update_document_item(self, document: ImageDocument) -> None:
        self.document_list.update_document_item(
            document.document_id,
            self._document_item_text(document),
            document.error_state or str(document.source_path or ""),
        )

    @staticmethod
    def _document_item_text(document: ImageDocument) -> str:
        return document.display_name

    @staticmethod
    def _path_key(path: Path) -> str:
        return str(path.resolve()).casefold()

    @classmethod
    def _folder_key(cls, path: Path) -> str:
        return cls._path_key(path.resolve().parent)

    def _add_document_to_folder(self, document_id: str, path: Path) -> None:
        folder_key = self._folder_key(path)
        folder_documents = self._folder_documents.setdefault(folder_key, [])
        current_id = None
        current_index = self._folder_indices.get(folder_key)
        if current_index is not None and 0 <= current_index < len(folder_documents):
            current_id = folder_documents[current_index]
        if document_id not in folder_documents:
            folder_documents.append(document_id)
        folder_documents.sort(
            key=lambda candidate_id: natural_sort_key(
                self.documents[candidate_id].source_path or Path("")
            )
        )
        self._folder_paths[folder_key] = path.resolve().parent
        if current_id in folder_documents:
            self._folder_indices[folder_key] = folder_documents.index(current_id)
        else:
            self._folder_indices.setdefault(folder_key, 0)

    def _remove_document_from_folder(self, document_id: str, path: Path) -> None:
        folder_key = self._folder_key(path)
        folder_documents = self._folder_documents.get(folder_key)
        if folder_documents is None:
            return
        current_index = self._folder_indices.get(folder_key, 0)
        if document_id in folder_documents:
            removed_index = folder_documents.index(document_id)
            folder_documents.remove(document_id)
            if removed_index < current_index:
                current_index -= 1
        if folder_documents:
            self._folder_indices[folder_key] = min(current_index, len(folder_documents) - 1)
        else:
            self._folder_documents.pop(folder_key, None)
            self._folder_paths.pop(folder_key, None)
            self._folder_indices.pop(folder_key, None)

    def _remember_folder_index(self, document_id: str) -> None:
        document = self.documents.get(document_id)
        if document is None or document.source_path is None:
            return
        folder_key = self._folder_key(document.source_path)
        folder_documents = self._folder_documents.get(folder_key, [])
        if document_id in folder_documents:
            self._folder_indices[folder_key] = folder_documents.index(document_id)

    def _active_folder_selection(self) -> list[tuple[str, str]] | None:
        documents = self.selected_documents
        if len(documents) < 2 or len(documents) > 6:
            return None
        session: list[tuple[str, str]] = []
        seen_folders: set[str] = set()
        for document in documents:
            if document.source_path is None:
                return None
            folder_key = self._folder_key(document.source_path)
            if folder_key in seen_folders:
                return None
            seen_folders.add(folder_key)
            session.append((folder_key, document.document_id))
        return session

    def _preferred_dialog_directory(self, configured: str) -> str:
        configured = configured.strip()
        if configured:
            path = Path(configured).expanduser()
            if path.is_dir():
                return str(path)
        return self._last_directory

    def _open_dialog_directory(self) -> str:
        return self._preferred_dialog_directory(
            self.application_settings.default_open_directory
        )

    def _export_dialog_directory(self) -> str:
        return self._preferred_dialog_directory(
            self.application_settings.default_export_directory
        )

    def _remember_directory(self, directory: Path) -> None:
        self._last_directory = str(directory)
        self.settings.setValue("paths/last_directory", self._last_directory)

    def _restore_ui_state(self) -> None:
        geometry = self.settings.value("ui/window_geometry")
        if isinstance(geometry, QByteArray | bytes):
            self.restoreGeometry(geometry)
        dock_state = self.settings.value("ui/dock_state")
        if isinstance(dock_state, QByteArray | bytes):
            self.restoreState(dock_state)
        main_state = self.settings.value("ui/main_splitter")
        if isinstance(main_state, QByteArray | bytes):
            self.main_splitter.restoreState(main_state)
        sidebar_state = self.settings.value("ui/sidebar_splitter")
        if isinstance(sidebar_state, QByteArray | bytes):
            self.sidebar_splitter.restoreState(sidebar_state)
        plots_visible = str(self.settings.value("ui/plots_visible", "false")).lower() == "true"
        self.bottom_dock.setVisible(plots_visible)
        layout = str(self.settings.value("ui/layout", "Auto"))
        layout = {
            "Single": "Single View",
            "Side by Side": "Multi View",
            "Focus + 2": "Multi View",
            "Grid 2x2": "Multi View",
            "Grid 3x2": "Multi View",
        }.get(layout, layout)
        if self.layout_selector.findText(layout) >= 0:
            self._layout_mode = layout
            self.layout_selector.blockSignals(True)
            self.layout_selector.setCurrentText(layout)
            self.layout_selector.blockSignals(False)
        tab_index = int(cast(int | str, self.settings.value("analysis/bottom_tab", 0)))
        self.bottom_tabs.setCurrentIndex(max(0, min(tab_index, self.bottom_tabs.count() - 1)))

    def _save_ui_state(self) -> None:
        self.settings.setValue("ui/window_geometry", self.saveGeometry())
        self.settings.setValue("ui/dock_state", self.saveState())
        self.settings.setValue("ui/main_splitter", self.main_splitter.saveState())
        self.settings.setValue("ui/sidebar_splitter", self.sidebar_splitter.saveState())
        self.settings.setValue("ui/plots_visible", not self.bottom_dock.isHidden())
        self.settings.setValue("ui/layout", self._layout_mode)
        self.settings.setValue("analysis/bottom_tab", self.bottom_tabs.currentIndex())

    def reset_workspace_layout(self) -> None:
        self.plots_dock_title.clear_persisted_geometry()
        for key in (
            "ui/window_geometry",
            "ui/dock_state",
            "ui/main_splitter",
            "ui/sidebar_splitter",
            "ui/plots_visible",
            "ui/layout",
            "ui/multiview_arrangement",
            "analysis/bottom_tab",
        ):
            self.settings.remove(key)
        self.resize(1400, 850)
        self.main_splitter.setSizes([390, 1010])
        self.sidebar_splitter.setSizes([330, 500])
        self._redock_plots()
        self.bottom_dock.hide()
        self.set_layout_mode("Auto")
        self.statusBar().showMessage("Workspace layout reset", 3000)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._save_ui_state()
        self.comparison_analysis_panel.shutdown()
        self.line_profile_panel.shutdown()
        self.difference_panel.shutdown()
        for worker in tuple(self._workers.values()):
            worker.cancel()
        if not self._load_pool.waitForDone(3000):
            LOGGER.warning("Image loads did not finish within the shutdown grace period")
        if not QThreadPool.globalInstance().waitForDone(3000):
            LOGGER.warning("Background tasks did not finish within the shutdown grace period")
        self._workers.clear()
        event.accept()
