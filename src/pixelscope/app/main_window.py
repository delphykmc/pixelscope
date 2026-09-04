from __future__ import annotations

import logging
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray
from PySide6.QtCore import (
    QByteArray,
    QItemSelectionModel,
    QSettings,
    QSize,
    Qt,
    QThreadPool,
)
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDragEnterEvent,
    QDropEvent,
    QKeySequence,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDockWidget,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
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
from pixelscope.core.diagnostics import (
    MAX_RECENT_FAILURES,
    DifferenceCacheDiagnostics,
    FailureDiagnostic,
    RuntimeDiagnosticsSnapshot,
    SourceResidencyDiagnostics,
    WorkerDiagnostics,
    WorkerPoolDiagnostics,
    format_runtime_diagnostics,
)
from pixelscope.core.folder_navigation import (
    FolderNavigationPlan,
    plan_folder_navigation,
)
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineSelection, clamp_line
from pixelscope.core.performance_settings import PerformanceSettings
from pixelscope.core.preload import PreloadController, PreloadMemberRequest
from pixelscope.core.residency import ResidencyManager
from pixelscope.core.roi import RoiBounds, clamp_roi
from pixelscope.core.spatial_sampling import SpatialSampling
from pixelscope.io.path_discovery import (
    SUPPORTED_IMAGE_FILTER,
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
from pixelscope.ui.difference_panel import DifferencePanel, DifferenceSamplingSnapshot
from pixelscope.ui.document_list import DocumentListWidget
from pixelscope.ui.empty_state import EmptyWorkspace
from pixelscope.ui.image_viewer import ImageViewer
from pixelscope.ui.iqa_workspace import IqaWorkspaceController, IqaWorkspaceWidget
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

COMPARISON_PAGE_SIZE = 6


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


@dataclass(frozen=True)
class FolderRegistrationResult:
    """Summary of one registration-oriented folder input operation."""

    folder_count: int
    image_count: int
    empty_folder_count: int
    registered_folders: tuple[Path, ...]


class MainWindow(QMainWindow):
    """Document registration, selection-driven comparison, and analysis lifecycle."""

    def __init__(
        self,
        application_settings: ApplicationSettings | None = None,
        performance_settings: PerformanceSettings | None = None,
        settings_repository: SettingsRepository | None = None,
        *,
        iqa_result_pool: QThreadPool | None = None,
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
        self._raw_profile_prompt_suppressed: set[str] = set()
        self._workers: dict[str, TaskWorker] = {}
        self._load_worker_targets: dict[str, str] = {}
        self._load_tokens: dict[str, int] = {}
        self._load_pool = QThreadPool(self)
        self._load_pool.setMaxThreadCount(2)
        self._preload_pool = QThreadPool(self)
        self._preload_pool.setMaxThreadCount(1)
        self.preload_controller = PreloadController(self.performance_settings.preload_enabled)
        self._preload_workers: dict[str, TaskWorker] = {}
        self._preload_worker_requests: dict[str, PreloadMemberRequest] = {}
        self._promoted_preload_tokens: dict[str, int] = {}
        self._normal_load_stale_drop_count = 0
        self._recent_failures: deque[FailureDiagnostic] = deque(maxlen=MAX_RECENT_FAILURES)
        self._closing = False
        self.residency_manager = ResidencyManager(self.performance_settings.source_residency_bytes)
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
        self._primary_page_slot = 0
        self._split_focus_document_id: str | None = None
        self._split_active_document_id: str | None = None
        self._multi_display_order: list[str] = []
        self._shared_roi: RoiBounds | None = None
        self._shared_line: LineSelection | None = None
        self._split_channels = False
        self._channel_split_active = False
        self._active_document_id: str | None = None
        self._difference_document: ImageDocument | None = None
        self._difference_source_ids: tuple[str, str] | None = None
        self._pending_position_focus: int | str | None = None
        self._channel_view_cache: dict[tuple[str, int], list[ImageDocument]] = {}
        self._six_image_diff_restore_state: SixImageDiffRestoreState | None = None
        self._comparison_page_controls_state: tuple[object, ...] | None = None

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
        self.document_list.previous_position_requested.connect(self.previous_folder_position)
        self.document_list.next_position_requested.connect(self.next_folder_position)
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
        self.iqa_workspace = IqaWorkspaceWidget()
        self.iqa_controller = IqaWorkspaceController(
            self.iqa_workspace,
            self,
            pool=iqa_result_pool,
        )
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
        self.empty_workspace.open_folders_requested.connect(self.open_folders)
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

        self.presentation_panel = QWidget()
        self.presentation_panel.setObjectName("presentationPanel")
        presentation_layout = QVBoxLayout(self.presentation_panel)
        presentation_layout.setContentsMargins(0, 0, 0, 0)
        presentation_layout.setSpacing(0)

        self.presentation_controls = QWidget(self.presentation_panel)
        self.presentation_controls.setObjectName("presentationControls")
        self.presentation_controls_layout = QHBoxLayout(self.presentation_controls)
        self.presentation_controls_layout.setContentsMargins(
            TOKENS.spacing_sm,
            TOKENS.spacing_xs,
            TOKENS.spacing_sm,
            TOKENS.spacing_xs,
        )
        self.presentation_controls_layout.setSpacing(TOKENS.spacing_md)
        presentation_layout.addWidget(self.presentation_controls)
        presentation_layout.addWidget(self.central_stack, 1)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.addWidget(sidebar)
        self.main_splitter.addWidget(self.presentation_panel)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([390, 1010])
        self.setCentralWidget(self.main_splitter)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.bottom_dock)

        self.iqa_dock = QDockWidget("IQA", self)
        self.iqa_dock.setObjectName("iqaWorkspaceDock")
        self.iqa_dock.setWidget(self.iqa_workspace)
        self.iqa_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.iqa_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.iqa_dock)
        self.iqa_dock.hide()

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
            "Help": menu_bar.addMenu("&Help"),
        }
        for menu in menus.values():
            menu.setStyleSheet(menu_style())
        add_action("File", "Open Images...", self.open_images, "Ctrl+O")
        add_action("File", "Open Folder...", self.open_folders, "Ctrl+Shift+O")
        add_action("File", "Open IQA Result...", self.open_iqa_result)
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
        previous_image = add_action("Selection", "Previous Selected Image", self.previous_image)
        next_image = add_action("Selection", "Next Selected Image", self.next_image)
        previous_image.setText("Previous Selected Image\tLeft")
        next_image.setText("Next Selected Image\tRight")
        previous_page = add_action(
            "Selection",
            "Previous Comparison Page",
            self.previous_comparison_page,
        )
        next_page = add_action(
            "Selection",
            "Next Comparison Page",
            self.next_comparison_page,
        )
        previous_page.setText("Previous Comparison Page\tCtrl+Left")
        next_page.setText("Next Comparison Page\tCtrl+Right")
        previous_position = add_action(
            "Selection",
            "Previous Folder Position",
            self.previous_folder_position,
        )
        next_position = add_action(
            "Selection",
            "Next Folder Position",
            self.next_folder_position,
        )
        previous_position.setText("Previous Folder Position\tPageUp")
        next_position.setText("Next Folder Position\tPageDown")

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
        self.iqa_workspace_action = add_action("View", "Show IQA Workspace", self._toggle_iqa)
        self.iqa_workspace_action.setCheckable(True)
        self.iqa_dock.visibilityChanged.connect(  # type: ignore[attr-defined]
            self.iqa_workspace_action.setChecked
        )
        add_action("View", "Reset Workspace Layout", self.reset_workspace_layout)
        add_action("Help", "Copy Diagnostics", self.copy_diagnostics)
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

    def copy_diagnostics(self) -> None:
        text = format_runtime_diagnostics(self.runtime_diagnostics_snapshot())
        QApplication.clipboard().setText(text)
        self.statusBar().showMessage("Diagnostics copied to clipboard", 3000)

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

        self.layout_selector = QComboBox(self.presentation_controls)
        self.layout_selector.addItems(("Auto", "Single View", "Multi View"))
        self.layout_selector.setFixedHeight(TOKENS.control_height)
        self.layout_selector.currentTextChanged.connect(  # type: ignore[attr-defined]
            self.set_layout_mode
        )
        layout_group = QWidget(self.presentation_controls)
        layout_group_layout = QHBoxLayout(layout_group)
        layout_group_layout.setContentsMargins(0, 0, 0, 0)
        layout_group_layout.setSpacing(TOKENS.spacing_sm)
        layout_group_layout.addWidget(QLabel("Layout"))
        layout_group_layout.addWidget(self.layout_selector)
        self.presentation_controls_layout.addWidget(layout_group)

        self.presentation_control_separator = QFrame(self.presentation_controls)
        self.presentation_control_separator.setObjectName("presentationControlSeparator")
        self.presentation_control_separator.setFrameShape(QFrame.Shape.VLine)
        self.presentation_control_separator.setFrameShadow(QFrame.Shadow.Plain)
        self.presentation_control_separator.setFixedHeight(TOKENS.control_height - 4)
        self.presentation_control_separator.setStyleSheet(f"QFrame {{ color: {TOKENS.border}; }}")
        self.presentation_controls_layout.addWidget(self.presentation_control_separator)

        self.comparison_page_group = QWidget(self.presentation_controls)
        self.comparison_page_group.setObjectName("comparisonPageGroup")
        page_layout = QHBoxLayout(self.comparison_page_group)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(TOKENS.spacing_sm)
        page_caption = QLabel("Page", self.comparison_page_group)
        page_caption.setObjectName("comparisonPageCaption")
        self.previous_comparison_page_button = QPushButton("‹")
        self.previous_comparison_page_button.setObjectName("previousComparisonPage")
        self.previous_comparison_page_button.setToolTip("Previous Comparison Page (Ctrl+Left)")
        self.previous_comparison_page_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.previous_comparison_page_button.clicked.connect(  # type: ignore[attr-defined]
            self.previous_comparison_page
        )
        self.comparison_page_label = QLabel("", self.comparison_page_group)
        self.comparison_page_label.setObjectName("comparisonPageStatus")
        self.comparison_page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.comparison_page_label.setFixedWidth(
            self.comparison_page_label.fontMetrics().horizontalAdvance("8888 / 8888")
            + 2 * TOKENS.spacing_sm
        )
        self.comparison_page_range_label = QLabel("", self.comparison_page_group)
        self.comparison_page_range_label.setObjectName("comparisonPageRange")
        self.comparison_page_range_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.comparison_page_range_label.setFixedWidth(
            self.comparison_page_range_label.fontMetrics().horizontalAdvance("99999–99999 of 99999")
            + 2 * TOKENS.spacing_sm
        )
        self.next_comparison_page_button = QPushButton("›")
        self.next_comparison_page_button.setObjectName("nextComparisonPage")
        self.next_comparison_page_button.setToolTip("Next Comparison Page (Ctrl+Right)")
        self.next_comparison_page_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.next_comparison_page_button.clicked.connect(  # type: ignore[attr-defined]
            self.next_comparison_page
        )
        for button in (
            self.previous_comparison_page_button,
            self.next_comparison_page_button,
        ):
            button.setFixedHeight(TOKENS.control_height)
            button.setFixedWidth(TOKENS.control_height)
        page_layout.addWidget(page_caption)
        page_layout.addWidget(self.previous_comparison_page_button)
        page_layout.addWidget(self.comparison_page_label)
        page_layout.addWidget(self.next_comparison_page_button)
        page_layout.addWidget(self.comparison_page_range_label)
        self.presentation_controls_layout.addWidget(self.comparison_page_group)
        self.presentation_controls_layout.addStretch(1)
        self._update_comparison_page_controls()

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

    def _toggle_iqa(self) -> None:
        self.iqa_dock.setVisible(self.iqa_workspace_action.isChecked())
        if self.iqa_workspace_action.isChecked():
            self.iqa_dock.raise_()

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
        for index in range(COMPARISON_PAGE_SIZE):
            shortcut = QShortcut(QKeySequence(str(index + 1)), self)
            shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
            shortcut.activated.connect(  # type: ignore[attr-defined]
                lambda local_index=index: self.show_selected_image(local_index)
            )
            self._selection_shortcuts.append(shortcut)
        for key, callback in (
            (Qt.Key.Key_PageUp, self.previous_folder_position),
            (Qt.Key.Key_PageDown, self.next_folder_position),
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

        self._comparison_page_shortcuts: list[QShortcut] = []
        for sequence, callback in (
            ("Ctrl+Left", self.previous_comparison_page),
            ("Ctrl+Right", self.next_comparison_page),
        ):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
            shortcut.activated.connect(callback)  # type: ignore[attr-defined]
            self._comparison_page_shortcuts.append(shortcut)
        self._update_comparison_page_controls()

    def _update_comparison_page_controls(self) -> None:
        start, end, total = self._comparison_page_range()
        page_count = (total + COMPARISON_PAGE_SIZE - 1) // COMPARISON_PAGE_SIZE
        current_page = start // COMPARISON_PAGE_SIZE + 1 if total else 0
        has_previous = total > 0 and start > 0
        has_next = total > 0 and end < total
        page_text = f"{current_page} / {page_count}" if total else ""
        range_text = f"{start + 1}–{end} of {total}" if total else ""
        state = (total > 0, has_previous, has_next, page_text, range_text)
        if hasattr(self, "_comparison_page_shortcuts"):
            for shortcut, enabled in zip(
                self._comparison_page_shortcuts,
                (has_previous, has_next),
                strict=True,
            ):
                shortcut.setEnabled(enabled)
        if state == self._comparison_page_controls_state:
            return
        self._comparison_page_controls_state = state

        if hasattr(self, "comparison_page_group"):
            self.comparison_page_group.setVisible(total > 0)
            self.comparison_page_label.setText(page_text)
            self.comparison_page_range_label.setText(range_text)
            for button in (
                self.previous_comparison_page_button,
                self.next_comparison_page_button,
            ):
                button.setVisible(True)
            self.previous_comparison_page_button.setEnabled(has_previous)
            self.next_comparison_page_button.setEnabled(has_next)

        previous_action = self.action_map.get("Previous Comparison Page")
        next_action = self.action_map.get("Next Comparison Page")
        if previous_action is not None:
            previous_action.setEnabled(has_previous)
        if next_action is not None:
            next_action.setEnabled(has_next)

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
        self._update_comparison_page_controls()

    def _six_image_diff_locked(self) -> bool:
        return (
            len(self.current_comparison_documents()) >= COMPARISON_PAGE_SIZE
            and self._difference_result_matches_current_pair()
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

    def _normalized_comparison_page_start(
        self,
        documents: Sequence[ImageDocument] | None = None,
    ) -> int:
        selected = list(documents) if documents is not None else self.selected_documents
        if not selected:
            return 0
        last_start = ((len(selected) - 1) // COMPARISON_PAGE_SIZE) * COMPARISON_PAGE_SIZE
        aligned = (max(0, self._page_start) // COMPARISON_PAGE_SIZE) * COMPARISON_PAGE_SIZE
        return min(aligned, last_start)

    def current_comparison_documents(self) -> list[ImageDocument]:
        """Return the selected working page; this is the analysis/presentation authority."""

        documents = self.selected_documents
        start = self._normalized_comparison_page_start(documents)
        return documents[start : start + COMPARISON_PAGE_SIZE]

    def _comparison_page_range(self) -> tuple[int, int, int]:
        documents = self.selected_documents
        if not documents:
            return 0, 0, 0
        start = self._normalized_comparison_page_start(documents)
        return start, min(start + COMPARISON_PAGE_SIZE, len(documents)), len(documents)

    def _sync_comparison_page_to_index(self, selected_index: int) -> None:
        if not self.selected_documents:
            self._page_start = 0
            return
        self._page_start = (max(0, selected_index) // COMPARISON_PAGE_SIZE) * COMPARISON_PAGE_SIZE

    def _current_page_local_index(self) -> int:
        page = self.current_comparison_documents()
        if not page:
            return 0
        start = self._normalized_comparison_page_start()
        if start <= self._current_index < start + len(page):
            return self._current_index - start
        return 0

    def _allow_raw_profile_retry(self, document_ids: Sequence[str]) -> None:
        self._raw_profile_prompt_suppressed.difference_update(document_ids)

    def _current_page_required_ids(self) -> set[str]:
        required = {document.document_id for document in self.current_comparison_documents()}
        required.update(self._visible_document_ids)
        if self._difference_source_ids is not None:
            required.update(self._difference_source_ids)
        return {document_id for document_id in required if document_id in self.documents}

    def _primary_document_for_page(
        self,
        page: Sequence[ImageDocument],
    ) -> ImageDocument | None:
        if not page:
            return None
        page_ids = [document.document_id for document in page]
        if self._focus_document_id in page_ids:
            self._primary_page_slot = page_ids.index(self._focus_document_id)
            return page[self._primary_page_slot]
        self._primary_page_slot = min(self._primary_page_slot, len(page) - 1)
        return page[self._primary_page_slot]

    def _difference_result_matches_current_pair(self) -> bool:
        if self._difference_document is None or self._difference_source_ids is None:
            return False
        pair = self.difference_panel.selected_documents()
        if pair is None:
            return False
        pair_ids = (pair[0].document_id, pair[1].document_id)
        page_ids = {document.document_id for document in self.current_comparison_documents()}
        return frozenset(pair_ids) == frozenset(self._difference_source_ids) and set(
            pair_ids
        ).issubset(page_ids)

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
        self._record_resident_source(document)
        if select:
            self._select_document_ids([document.document_id])
        else:
            self._update_empty_workspace_state()
            self._evict_resident_documents()

    def open_images(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Open images",
            self._open_dialog_directory(),
            SUPPORTED_IMAGE_FILTER,
        )
        if not paths:
            return
        supplied_paths = [Path(path) for path in paths]
        self._remember_directory(supplied_paths[0].parent)
        document_ids = self._register_inputs(
            discover_image_inputs(supplied_paths),
            resolve_raw_profiles=True,
        )
        if document_ids:
            self._select_document_ids(document_ids)
            self.statusBar().showMessage(f"Opened {len(document_ids)} image(s)", 4000)
        else:
            self.statusBar().showMessage("No supported images opened", 4000)

    def open_iqa_result(self) -> None:
        root = QFileDialog.getExistingDirectory(
            self,
            "Open IQA Result",
            self._open_dialog_directory(),
        )
        if not root:
            return
        self.iqa_dock.show()
        self.iqa_dock.raise_()
        self.iqa_controller.open_result(Path(root))
        self.statusBar().showMessage(f"Opening IQA result · {Path(root).name}")

    def open_folders(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Open image folder",
            self._open_dialog_directory(),
        )
        if not path:
            return
        folder = Path(path)
        self._remember_directory(folder)
        result = self.register_folders((folder,))
        self.statusBar().showMessage(self._folder_registration_message(result), 5000)

    def register_folders(self, folders: Sequence[Path]) -> FolderRegistrationResult:
        """Register supported folder contents without changing selection or presentation."""

        unique: dict[str, Path] = {}
        for folder in folders:
            resolved = folder.resolve()
            if resolved.is_dir():
                unique.setdefault(str(resolved).casefold(), resolved)
        ordered_folders = [unique[key] for key in sorted(unique)]

        registered_ids: set[str] = set()
        registered_folders: list[Path] = []
        empty_folder_count = 0
        for folder in ordered_folders:
            inputs = discover_image_inputs((folder,))
            if not inputs:
                empty_folder_count += 1
                continue
            folder_ids = self._register_inputs(inputs, resolve_raw_profiles=False)
            if folder_ids:
                registered_folders.append(folder)
                registered_ids.update(folder_ids)
        self._update_empty_workspace_state()
        return FolderRegistrationResult(
            folder_count=len(ordered_folders),
            image_count=len(registered_ids),
            empty_folder_count=empty_folder_count,
            registered_folders=tuple(registered_folders),
        )

    @staticmethod
    def _folder_registration_message(result: FolderRegistrationResult) -> str:
        if result.folder_count == 0:
            return "No folders registered"
        if result.image_count == 0:
            return f"No supported images found in {result.folder_count} folder(s)"
        message = f"Registered {result.image_count} image(s) from {result.folder_count} folder(s)"
        if result.empty_folder_count:
            message += f" · {result.empty_folder_count} contained no supported images"
        return message

    def _register_inputs(
        self,
        inputs: tuple[ImageInput, ...],
        *,
        resolve_raw_profiles: bool,
    ) -> list[str]:
        """Register inputs only; callers own any selection or presentation change."""

        document_ids = list(
            dict.fromkeys(
                document_id
                for image_input in inputs
                if (
                    document_id := self._register_input(
                        image_input,
                        resolve_raw_profile=resolve_raw_profiles,
                    )
                )
                is not None
            )
        )
        self._update_empty_workspace_state()
        return document_ids

    def _register_input(
        self,
        image_input: ImageInput,
        *,
        resolve_raw_profile: bool = True,
    ) -> str | None:
        key = self._path_key(image_input.path)
        existing = self._document_id_by_path.get(key)
        is_raw = image_input.path.suffix.casefold() == ".raw"
        raw_profile: RawProfile | None = None
        if is_raw and resolve_raw_profile:
            raw_profile = self._confirm_raw_profile(image_input, existing)
            if raw_profile is None:
                return None
        if existing is not None:
            if image_input.raw_profile_path is not None:
                self._raw_profile_paths[existing] = image_input.raw_profile_path
            if raw_profile is not None:
                self._raw_profiles[existing] = raw_profile
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
        self._invalidate_preload_plan()
        document = self.documents.get(document_id)
        if document is None:
            return
        self._load_tokens[document_id] = self._load_tokens.get(document_id, 0) + 1
        self.residency_manager.remove(document_id)
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
        self._invalidate_channel_views(document_id)
        self._update_document_item(document)

    def _ensure_loaded(self, document: ImageDocument) -> None:
        if document.loading_state != "pending" or document.source_path is None:
            return
        profile = self._raw_profiles.get(document.document_id)
        is_raw = document.source_path.suffix.casefold() == ".raw"
        if is_raw and profile is None:
            if document.document_id in self._raw_profile_prompt_suppressed:
                return
            profile = self._confirm_raw_profile(
                ImageInput(
                    document.source_path,
                    self._raw_profile_paths.get(document.document_id),
                ),
                document.document_id,
            )
            if profile is None:
                self._raw_profile_prompt_suppressed.add(document.document_id)
                self.statusBar().showMessage(
                    f"RAW profile required to load {document.display_name}",
                    4000,
                )
                return
            self._raw_profile_prompt_suppressed.discard(document.document_id)
            self._raw_profiles[document.document_id] = profile
            document.channel_layout = profile.channel_layout
            document.bit_depth = profile.bit_depth
            document.raw_profile = profile
        if self._preload_workers:
            self._invalidate_preload_plan()
        document.loading_state = "loading"
        self._update_document_item(document)
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
        if target_id not in self.documents or self._load_tokens.get(target_id) != request_token:
            self._normal_load_stale_drop_count += 1
            return
        if not isinstance(result, ImageDocument):
            return
        previous_generation = self.documents[target_id].generation
        result.document_id = target_id
        result.generation = previous_generation
        self.documents[target_id] = result
        self._record_resident_source(result)
        self.residency_manager.touch(target_id)
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
            self._normal_load_stale_drop_count += 1
            return
        self._record_runtime_failure("foreground-load", "decode", error)
        LOGGER.error("Image load failed: %s\n%s", error.message, error.traceback_text)
        self.residency_manager.remove(target_id)
        document = ImageDocument.error_document(path.name, error.message, path)
        document.document_id = target_id
        self.documents[target_id] = document
        self._update_document_item(document)
        if self._selected_load_batch_complete():
            self._render_selection(preserve_view=True)
        self.structured_status.task.setText("Error")
        self.statusBar().showMessage(f"Failed to load {path.name}: {error.message}", 5000)

    def _selected_load_batch_complete(self) -> bool:
        """Treat one Current Comparison Page as the foreground replacement batch."""

        return all(
            document.document_id in self._raw_profile_prompt_suppressed
            or document.loading_state not in ("pending", "loading")
            for document in self.current_comparison_documents()
        )

    def _worker_finished(self, task_id: str) -> None:
        self._workers.pop(task_id, None)
        self._load_worker_targets.pop(task_id, None)
        self._evict_resident_documents()
        if not self._workers and not self._promoted_preload_tokens:
            self.structured_status.task.setText("Ready")
            self._refresh_preload_plan()

    def _refresh_preload_plan(self) -> None:
        """Reconcile and start exactly the predicted next position when idle."""

        if self._closing:
            self._invalidate_preload_plan()
            return
        navigation_plan = (
            self._plan_folder_navigation(1) if self.preload_controller.enabled else None
        )
        target_ids = navigation_plan.document_ids if navigation_plan is not None else ()
        previous = self.preload_controller.current_plan
        current = self.preload_controller.set_plan(target_ids)
        if previous is not current:
            self._cancel_preload_workers()
        if current is None or self._workers or self._preload_workers:
            return

        for document_id in self.preload_controller.pending_document_ids:
            document = self.documents.get(document_id)
            if document is None:
                self.preload_controller.complete_available_member(current.generation, document_id)
                continue
            if document.source is not None or document.loading_state == "error":
                self.preload_controller.complete_available_member(current.generation, document_id)
                continue
            if document.source_path is None or document.loading_state != "pending":
                self.preload_controller.complete_available_member(current.generation, document_id)
                continue

            profile = self._raw_profiles.get(document_id)
            if document.source_path.suffix.casefold() == ".raw" and profile is None:
                self.preload_controller.complete_available_member(current.generation, document_id)
                continue
            self._start_preload(current.generation, document, profile)
            return

    def _start_preload(
        self,
        plan_generation: int,
        document: ImageDocument,
        raw_profile: RawProfile | None,
    ) -> None:
        source_path = document.source_path
        if source_path is None:
            return
        request = PreloadMemberRequest(
            plan_generation=plan_generation,
            document_id=document.document_id,
            document_generation=document.generation,
            source_path_identity=self._path_key(source_path),
            profile_identity=self._raw_profile_identity(raw_profile),
            require_exact_raw_size=self.application_settings.require_exact_raw_file_size,
            normal_load_token=self._load_tokens.get(document.document_id, 0),
        )
        if not self.preload_controller.start_member(request):
            return
        worker = ImageLoadWorker(
            source_path,
            raw_profile,
            require_exact_raw_size=request.require_exact_raw_size,
        )
        worker.signals.started.connect(
            lambda task_id, _document_id, _generation: self._preload_started(task_id)
        )
        worker.signals.succeeded.connect(
            lambda task_id, _document_id, _generation, result: self._preload_succeeded(
                task_id, result
            )
        )
        worker.signals.failed.connect(
            lambda task_id, _document_id, _generation, error: self._preload_failed(task_id, error)
        )
        worker.signals.finished.connect(self._preload_worker_finished)
        self._preload_workers[worker.task_id] = worker
        self._preload_worker_requests[worker.task_id] = request
        self._preload_pool.start(worker)

    def _preload_started(self, task_id: str) -> None:
        request = self._preload_worker_requests.get(task_id)
        if request is not None:
            self.preload_controller.mark_running(request)

    def _promote_running_preloads(self, required_ids: Sequence[str]) -> None:
        required = set(required_ids)
        for task_id, request in tuple(self._preload_worker_requests.items()):
            if request.document_id in required:
                self._promote_preload_worker(task_id)

    def _promote_preload_worker(self, task_id: str) -> bool:
        request = self._preload_worker_requests.get(task_id)
        worker = self._preload_workers.get(task_id)
        if request is None or worker is None or worker.is_cancelled:
            return False
        if not self.preload_controller.request_is_current(request):
            return False
        if not self.preload_controller.request_is_running(request):
            return False
        document = self.documents.get(request.document_id)
        if document is None or document.source_path is None:
            return False
        source_path = document.source_path
        profile = self._raw_profiles.get(request.document_id)
        valid = (
            document.source is None
            and document.loading_state == "pending"
            and document.generation == request.document_generation
            and self._path_key(source_path) == request.source_path_identity
            and self._raw_profile_identity(profile) == request.profile_identity
            and self.application_settings.require_exact_raw_file_size
            == request.require_exact_raw_size
            and self._load_tokens.get(request.document_id, 0) == request.normal_load_token
            and request.document_id not in self._load_worker_targets.values()
        )
        if not valid or not self.preload_controller.promote(request):
            return False

        foreground_token = request.normal_load_token + 1
        self._load_tokens[request.document_id] = foreground_token
        self._promoted_preload_tokens[task_id] = foreground_token
        document.loading_state = "loading"
        document.error_state = None
        self._update_document_item(document)
        self._load_started(source_path)
        return True

    def _promoted_preload_is_current(
        self,
        task_id: str,
        request: PreloadMemberRequest,
        *,
        require_result: ImageDocument | None = None,
    ) -> bool:
        foreground_token = self._promoted_preload_tokens.get(task_id)
        if foreground_token is None or not self.preload_controller.request_is_promoted(request):
            return False
        document = self.documents.get(request.document_id)
        profile = self._raw_profiles.get(request.document_id)
        if not (
            document is not None
            and document.source is None
            and document.loading_state == "loading"
            and document.source_path is not None
            and document.generation == request.document_generation
            and self._path_key(document.source_path) == request.source_path_identity
            and self._raw_profile_identity(profile) == request.profile_identity
            and self.application_settings.require_exact_raw_file_size
            == request.require_exact_raw_size
            and self._load_tokens.get(request.document_id) == foreground_token
            and request.document_id not in self._load_worker_targets.values()
        ):
            return False
        if require_result is None:
            return True
        return (
            require_result.source_path is not None
            and self._path_key(require_result.source_path) == request.source_path_identity
            and self._raw_profile_identity(
                require_result.raw_profile
                if isinstance(require_result.raw_profile, RawProfile)
                else None
            )
            == request.profile_identity
        )

    def _preload_succeeded(self, task_id: str, result: object) -> None:
        request = self._preload_worker_requests.get(task_id)
        promoted_token = self._promoted_preload_tokens.get(task_id)
        if request is None:
            if promoted_token is not None:
                self._normal_load_stale_drop_count += 1
            else:
                self.preload_controller.record_stale_drop()
            return
        if promoted_token is not None:
            if not isinstance(result, ImageDocument) or not self._promoted_preload_is_current(
                task_id,
                request,
                require_result=result,
            ):
                self._normal_load_stale_drop_count += 1
                return
            self._load_succeeded(request.document_id, promoted_token, result)
            return
        if not isinstance(result, ImageDocument):
            self.preload_controller.record_stale_drop()
            return
        document = self.documents.get(request.document_id)
        current_plan = self.preload_controller.current_plan
        profile = self._raw_profiles.get(request.document_id)
        valid = (
            current_plan is not None
            and current_plan.generation == request.plan_generation
            and request.document_id in current_plan.document_ids
            and self.preload_controller.request_is_current(request)
            and document is not None
            and document.source is None
            and document.source_path is not None
            and document.generation == request.document_generation
            and self._path_key(document.source_path) == request.source_path_identity
            and result.source_path is not None
            and self._path_key(result.source_path) == request.source_path_identity
            and self._raw_profile_identity(profile) == request.profile_identity
            and self._raw_profile_identity(
                result.raw_profile if isinstance(result.raw_profile, RawProfile) else None
            )
            == request.profile_identity
            and self.application_settings.require_exact_raw_file_size
            == request.require_exact_raw_size
            and self._load_tokens.get(request.document_id, 0) == request.normal_load_token
            and request.document_id not in self._load_worker_targets.values()
        )
        if not valid:
            self.preload_controller.record_stale_drop()
            return

        result.document_id = request.document_id
        result.generation = request.document_generation
        self.documents[request.document_id] = result
        self._record_resident_source(result)
        self.residency_manager.touch(request.document_id)
        self._update_document_item(result)
        self._evict_resident_documents()
        retained = self.documents[request.document_id].source is not None
        self.preload_controller.accept_success(
            request.plan_generation,
            request.document_id,
            retained=retained,
        )

    def _preload_failed(self, task_id: str, error: object) -> None:
        request = self._preload_worker_requests.get(task_id)
        if request is None:
            return
        promoted_token = self._promoted_preload_tokens.get(task_id)
        if promoted_token is not None:
            document = self.documents.get(request.document_id)
            if (
                isinstance(error, TaskError)
                and self._promoted_preload_is_current(task_id, request)
                and document is not None
                and document.source_path is not None
            ):
                self._load_failed(
                    request.document_id,
                    document.source_path,
                    error,
                    promoted_token,
                )
            else:
                self._normal_load_stale_drop_count += 1
            return
        accepted = self.preload_controller.record_failure(
            request.plan_generation,
            request.document_id,
        )
        if accepted:
            self._record_runtime_failure("preload", "decode", error)

    def _preload_worker_finished(self, task_id: str) -> None:
        request = self._preload_worker_requests.pop(task_id, None)
        self._preload_workers.pop(task_id, None)
        self._promoted_preload_tokens.pop(task_id, None)
        if request is not None:
            self.preload_controller.finish_worker(request)
        if not self._workers and not self._promoted_preload_tokens:
            self.structured_status.task.setText("Ready")
        self._refresh_preload_plan()

    def _cancel_preload_workers(self, *, include_promoted: bool = False) -> None:
        for task_id, worker in tuple(self._preload_workers.items()):
            request = self._preload_worker_requests.get(task_id)
            if request is not None and self.preload_controller.request_is_promoted(request):
                if include_promoted:
                    worker.cancel()
                continue
            if request is not None:
                self.preload_controller.record_cancellation_request(request)
            worker.cancel()

    def _invalidate_preload_plan(self, *, include_promoted: bool = False) -> None:
        self.preload_controller.invalidate()
        self._cancel_preload_workers(include_promoted=include_promoted)

    def runtime_diagnostics_snapshot(self) -> RuntimeDiagnosticsSnapshot:
        """Read current bounded runtime state without triggering work or LRU access."""

        source = self.residency_manager
        difference = self.difference_panel.difference_cache
        promoted_count = len(self._promoted_preload_tokens)
        speculative_preload_count = sum(
            task_id not in self._promoted_preload_tokens for task_id in self._preload_workers
        )
        return RuntimeDiagnosticsSnapshot(
            source=SourceResidencyDiagnostics(
                used_bytes=source.used_bytes,
                budget_bytes=source.budget_bytes,
                resident_count=source.resident_count,
                over_budget_bytes=source.over_budget_bytes,
            ),
            difference=DifferenceCacheDiagnostics(
                used_bytes=difference.used_bytes,
                budget_bytes=difference.budget_bytes,
                entry_count=difference.entry_count,
            ),
            workers=WorkerDiagnostics(
                foreground_loads=WorkerPoolDiagnostics(
                    active_count=len(self._workers) + promoted_count,
                    max_count=self._load_pool.maxThreadCount(),
                ),
                preload=WorkerPoolDiagnostics(
                    active_count=speculative_preload_count,
                    max_count=self._preload_pool.maxThreadCount(),
                ),
            ),
            preload=self.preload_controller.diagnostics,
            normal_load_stale_drop_count=self._normal_load_stale_drop_count,
            recent_failures=tuple(self._recent_failures),
        )

    def _record_runtime_failure(self, subsystem: str, category: str, error: object) -> None:
        if isinstance(error, TaskError):
            exception_type = error.exception_type
            message = error.message
        elif isinstance(error, BaseException):
            exception_type = type(error).__name__
            message = str(error)
        else:
            exception_type = type(error).__name__
            message = str(error)
        self._recent_failures.append(
            FailureDiagnostic(
                subsystem=subsystem,
                category=category,
                exception_type=exception_type,
                message=message,
            )
        )

    @staticmethod
    def _raw_profile_identity(profile: RawProfile | None) -> str:
        return "" if profile is None else profile.json(sort_keys=True)

    def _cancel_obsolete_loads(self, required_ids: set[str]) -> None:
        """Invalidate queued or promoted loads that rapid navigation moved away from."""

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

        for task_id, foreground_token in tuple(self._promoted_preload_tokens.items()):
            request = self._preload_worker_requests.get(task_id)
            if request is None or request.document_id in required_ids:
                continue
            worker = self._preload_workers.get(task_id)
            if worker is not None:
                worker.cancel()
            if self._load_tokens.get(request.document_id) == foreground_token:
                self._load_tokens[request.document_id] = foreground_token + 1
            document = self.documents.get(request.document_id)
            if document is not None and document.loading_state == "loading":
                document.loading_state = "pending"
                self._update_document_item(document)

    def _record_resident_source(self, document: ImageDocument) -> None:
        """Synchronize exact native-source accounting for one reloadable document."""

        if document.source is None:
            self.residency_manager.remove(document.document_id)
            return
        self.residency_manager.record(document.document_id, int(document.source.nbytes))

    def _residency_protected_document_ids(self) -> set[str]:
        """Protect only current-page and correctness-required native sources."""

        protected = set(self._visible_document_ids)
        if self._active_document_id is not None:
            protected.add(self._active_document_id)
        protected.update(document.document_id for document in self.current_comparison_documents())
        protected.update(self._load_worker_targets.values())
        protected.update(
            request.document_id
            for task_id, request in self._preload_worker_requests.items()
            if task_id in self._promoted_preload_tokens
        )
        if self._difference_source_ids is not None:
            protected.update(self._difference_source_ids)
        if hasattr(self, "difference_panel"):
            pair = self.difference_panel.selected_documents()
            if pair is not None:
                protected.update(document.document_id for document in pair)

        protected.update(
            document.document_id
            for document in self.documents.values()
            if document.source is not None and document.source_path is None
        )
        return {document_id for document_id in protected if document_id in self.documents}

    def _evict_resident_documents(self) -> None:
        """Release planned unprotected native sources while preserving reload state."""

        for document_id in self.residency_manager.resident_document_ids:
            document = self.documents.get(document_id)
            if document is None or document.source is None:
                self.residency_manager.remove(document_id)
                continue
            self._record_resident_source(document)

        protected = self._residency_protected_document_ids()
        for document_id in self.residency_manager.eviction_candidates(protected):
            document = self.documents.get(document_id)
            if document is None or document.source is None:
                self.residency_manager.remove(document_id)
                continue
            if document.source_path is None:
                continue
            document.source = None
            document.preview = None
            document.statistics_cache.clear()
            document.histogram_cache.clear()
            document.loading_state = "pending"
            self._invalidate_channel_views(document_id)
            self.residency_manager.remove(document_id)
            self._update_document_item(document)

    def _invalidate_channel_views(self, document_id: str) -> None:
        self._channel_view_cache = {
            key: value for key, value in self._channel_view_cache.items() if key[0] != document_id
        }

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
        page_ids = [document.document_id for document in self.current_comparison_documents()]
        self._promote_running_preloads(page_ids)
        self._invalidate_preload_plan()
        self._allow_raw_profile_retry(page_ids)
        required = set(page_ids)
        if self._difference_source_ids is not None:
            required.update(self._difference_source_ids)
        self._cancel_obsolete_loads(required)
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

        if documents:
            self._current_index = min(self._current_index, len(documents) - 1)
            self._page_start = self._normalized_comparison_page_start(documents)
            page = self.current_comparison_documents()
            if not (self._page_start <= self._current_index < self._page_start + len(page)):
                self._current_index = self._page_start
        else:
            self._current_index = 0
            self._page_start = 0

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
            self._update_empty_workspace_state()
            self.central_stack.setCurrentWidget(self.empty_workspace)
            self._active_document_id = None
            self.structured_status.set_active_document()
            self._evict_resident_documents()
            self._update_file_states([], None)
            self._update_comparison_page_controls()
            self._refresh_preload_plan()
            return

        comparison_page = self.current_comparison_documents()
        analysis_candidates = comparison_page
        for document in analysis_candidates:
            self._ensure_loaded(document)
        analysis_ready = [
            document for document in analysis_candidates if document.source is not None
        ]
        for document in analysis_ready:
            self.residency_manager.touch(document.document_id)

        self.difference_panel.set_documents(
            analysis_ready,
            None,
            self._shared_roi,
        )
        cached_display = self.difference_panel.cached_display_for_current()
        cached_six_difference = (
            cached_display is not None
            and len(comparison_page) >= COMPARISON_PAGE_SIZE
            and hasattr(self, "diff_action")
            and self.diff_action.isChecked()
        )
        if cached_display is not None:
            if cached_six_difference:
                self._capture_six_image_diff_restore_state()
            self._store_difference_document(
                *cached_display,
                self.difference_panel.mapping_snapshot_for_payload(
                    cached_display[1],
                    cached_display[2],
                ),
                switch_to_result=False,
            )
        elif (
            len(analysis_candidates) >= 2
            and len(analysis_ready) >= 2
            and hasattr(self, "diff_action")
            and self.diff_action.isChecked()
        ):
            self.difference_panel.calculate_difference()
        self._update_action_states()

        split_documents = self._current_split_documents()
        self._channel_split_active = bool(split_documents)
        if split_documents:
            split_ids = {document.document_id for document in split_documents}
            if self._split_focus_document_id not in split_ids:
                self._split_focus_document_id = split_documents[0].document_id
            if self._split_active_document_id not in split_ids:
                self._split_active_document_id = self._split_focus_document_id

        display_documents = list(split_documents or comparison_page)
        difference_document = self._difference_document
        show_difference = (
            len(analysis_candidates) >= 2
            and difference_document is not None
            and self._difference_result_matches_current_pair()
            and hasattr(self, "diff_action")
            and self.diff_action.isChecked()
        )
        if show_difference and self._layout_mode != "Single View":
            assert difference_document is not None
            if difference_document.document_id not in self._multi_display_order:
                self._promote_multi_document(difference_document.document_id)
            display_documents = [difference_document, *display_documents]

        large_selection = len(documents) > COMPARISON_PAGE_SIZE
        difference_is_primary = (
            show_difference
            and difference_document is not None
            and self._focus_document_id == difference_document.document_id
        )
        if self._channel_split_active and self._layout_mode != "Single View":
            split_primary = self._split_focus_document_id
            display_documents = sorted(
                display_documents,
                key=lambda item: 0 if item.document_id == split_primary else 1,
            )
        elif self._layout_mode != "Single View" and not difference_is_primary:
            primary = self._primary_document_for_page(comparison_page)
            if primary is not None:
                self._focus_document_id = primary.document_id
                self._promote_multi_document(primary.document_id)

        if self._layout_mode != "Single View" and not self._channel_split_active:
            display_documents = self._ordered_multi_documents(display_documents)

        if self._layout_mode == "Single View":
            effective_layout, capacity = "Single", 1
        elif large_selection:
            effective_layout, capacity = "Grid 3x2", COMPARISON_PAGE_SIZE
        else:
            effective_layout, capacity = self._effective_layout(len(display_documents))
        self._view_capacity = capacity

        if self._view_capacity == 1:
            if self._channel_split_active:
                split_order_ids = [document.document_id for document in split_documents]
                active_id = self._split_active_document_id
                split_index = (
                    split_order_ids.index(active_id) if active_id in split_order_ids else 0
                )
                document = split_documents[split_index]
                self._split_active_document_id = document.document_id
                self.viewer.set_document(document, fit=not preserve_view)
                self.viewer.set_tile_context(split_index + 1, "")
                self.viewer.set_header(
                    f"[{split_index + 1}/{len(split_documents)}] {document.display_name}"
                )
                self._set_single_navigation(document.document_id)
                self.viewer.set_roi_bounds(None)
                self.viewer.set_line_selection(None)
                self.central_stack.setCurrentWidget(self.viewer)
                visible_state = [comparison_page[0]]
            else:
                document = documents[self._current_index]
                local_slot = self._current_index - self._page_start + 1
                self.viewer.set_document(document, fit=not preserve_view)
                self.viewer.set_tile_context(local_slot, "")
                if large_selection:
                    self.viewer.set_header(f"[{local_slot}] {document.display_name}")
                else:
                    self.viewer.set_header(
                        f"[{local_slot}/{len(documents)}] {document.display_name}"
                    )
                self._set_single_navigation(document.document_id)
                self.viewer.set_roi_bounds(self._shared_roi)
                self.viewer.set_line_selection(self._shared_line)
                self.central_stack.setCurrentWidget(self.viewer)
                visible_state = [document]
        elif self._channel_split_active:
            channel_documents = display_documents
            self.multi_compare_view.set_capacity(4)
            self.multi_compare_view.set_layout_kind(
                "Focus + 2" if len(channel_documents) == 3 else "Grid 2x2",
                self._split_focus_document_id,
            )
            self.multi_compare_view.set_documents(
                channel_documents,
                0,
                len(channel_documents),
                None,
                None,
                preserve_view,
            )
            self.central_stack.setCurrentWidget(self.multi_compare_view)
            for viewer in self.multi_compare_view.visible_viewers:
                viewer.set_focus(
                    viewer.document is not None
                    and viewer.document.document_id == self._split_focus_document_id
                )
                viewer.set_focus_control_visible(
                    viewer.document is not None and len(channel_documents) > 1
                )
            visible_state = [comparison_page[0]]
        else:
            visible = display_documents[: self._view_capacity]
            self.multi_compare_view.set_capacity(self._view_capacity)
            self.multi_compare_view.set_layout_kind(
                effective_layout,
                self._focus_document_id,
            )
            local_slot_by_id = {
                document.document_id: index + 1 for index, document in enumerate(comparison_page)
            }
            self.multi_compare_view.set_documents(
                visible,
                0,
                len(comparison_page),
                self._shared_roi,
                self._shared_line,
                preserve_view,
                local_slot_by_id,
                fixed_geometry_count=(COMPARISON_PAGE_SIZE if large_selection else None),
                local_slots=large_selection,
            )
            self.central_stack.setCurrentWidget(self.multi_compare_view)
            visible_state = [
                document for document in visible if document is not self._difference_document
            ]

        self._visible_document_ids = {document.document_id for document in visible_state}
        required_ids = {document.document_id for document in analysis_candidates}
        required_ids.update(self._visible_document_ids)
        if self._difference_source_ids is not None:
            required_ids.update(self._difference_source_ids)
        self._cancel_obsolete_loads(required_ids)
        for document in analysis_ready:
            self.residency_manager.touch(document.document_id)
        self._evict_resident_documents()

        self._normalize_shared_roi(analysis_ready)
        self._normalize_shared_line(analysis_ready)
        region_name = self.comparison_analysis_panel.region_scope.currentText()
        analysis_bounds = self._shared_roi if region_name == "Active ROI" else None
        self.comparison_analysis_panel.set_documents(
            analysis_ready,
            analysis_bounds,
            region_name,
        )
        if self._channel_split_active:
            active = next(
                (
                    document
                    for document in split_documents
                    if document.document_id == self._split_active_document_id
                ),
                split_documents[0] if split_documents else self.current_document,
            )
        else:
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
        if cached_six_difference and self._difference_document is not None:
            self._navigate_single_view("difference")
            self._set_active_document(self._difference_document)
        if self._channel_split_active and comparison_page:
            self._update_file_states([comparison_page[0]], comparison_page[0])
        else:
            self._update_file_states(visible_state, active)
        self._update_comparison_page_controls()
        self._refresh_preload_plan()

    def _split_display_documents(
        self,
        document: ImageDocument,
    ) -> tuple[list[ImageDocument], bool]:
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
            or getattr(profile, "channel_layout", None) == "BAYER"
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

    def _current_split_documents(self) -> list[ImageDocument]:
        if not self._split_channels:
            return []
        page = self.current_comparison_documents()
        if len(page) != 1:
            return []
        document = page[0]
        channel_documents, split_active = self._split_display_documents(document)
        return channel_documents if split_active or document.source is None else []

    def _set_split_channels(self, enabled: bool) -> None:
        self._split_channels = enabled
        self._split_focus_document_id = None
        self._split_active_document_id = None
        if enabled:
            if self._layout_mode == "Auto":
                self._layout_mode = "Multi View"
            self._view_capacity = 1 if self._layout_mode == "Single View" else 4
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
        documents = self.selected_documents
        if documents:
            self._current_index = min(self._current_index, len(documents) - 1)
            if mode == "Single View" and previous_active_id is not None:
                selected_index = next(
                    (
                        index
                        for index, document in enumerate(documents)
                        if document.document_id == previous_active_id
                    ),
                    None,
                )
                if selected_index is not None:
                    self._current_index = selected_index
            self._sync_comparison_page_to_index(self._current_index)
        else:
            self._current_index = 0
            self._page_start = 0

        current_page = self.current_comparison_documents()
        if mode == "Single View":
            self._view_capacity = 1
        elif len(documents) > COMPARISON_PAGE_SIZE:
            self._view_capacity = COMPARISON_PAGE_SIZE
        else:
            _effective, self._view_capacity = self._effective_layout(len(current_page))

        if hasattr(self, "layout_selector"):
            self.layout_selector.blockSignals(True)
            self.layout_selector.setCurrentText(mode)
            self.layout_selector.blockSignals(False)
        self._allow_raw_profile_retry([document.document_id for document in current_page])
        if changed:
            self._reset_pixel_status()
        self._render_selection(preserve_view=not changed)
        if mode == "Single View" and previous_was_difference:
            self._navigate_single_view("difference")

    def _layout_mode_is_presented(self, mode: str) -> bool:
        documents = self.selected_documents
        document_count = len(documents)
        page_count = len(self.current_comparison_documents())
        expects_multi = mode != "Single View" and (page_count > 1 or self._split_channels)
        expected_widget = self.multi_compare_view if expects_multi else self.viewer
        if document_count == 0:
            expected_widget = self.empty_workspace
        if self.central_stack.currentWidget() is not expected_widget:
            return False
        if expects_multi:
            if document_count > COMPARISON_PAGE_SIZE:
                expected_capacity = COMPARISON_PAGE_SIZE
            else:
                display_count = page_count
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
        split_ids = {item.document_id for item in self._current_split_documents()}
        if self._channel_split_active and document_id in split_ids:
            self._split_focus_document_id = document_id
            self._split_active_document_id = document_id
            self._render_selection(preserve_view=True)
            return

        page = self.current_comparison_documents()
        allowed_ids = {item.document_id for item in page}
        if self.diff_action.isChecked() and self._difference_document is not None:
            allowed_ids.add(self._difference_document.document_id)
        if document_id not in allowed_ids:
            return
        self._promote_multi_document(document_id)
        self._focus_document_id = document_id
        selected_index = next(
            (
                index
                for index, item in enumerate(self.selected_documents)
                if item.document_id == document_id
            ),
            None,
        )
        if selected_index is not None:
            self._current_index = selected_index
            page_start = self._normalized_comparison_page_start()
            self._primary_page_slot = selected_index - page_start
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
        return [
            document
            for document in self.current_comparison_documents()
            if document.source is not None
        ]

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
        self.residency_manager.touch(document.document_id)
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
        if self._channel_split_active:
            split_ids = {item.document_id for item in self._current_split_documents()}
            if document.document_id in split_ids:
                self._split_active_document_id = document.document_id
                page = self.current_comparison_documents()
                if page:
                    self._update_file_states([page[0]], page[0])
                self._evict_resident_documents()
                return
        selected_index = next(
            (
                index
                for index, selected in enumerate(self.selected_documents)
                if selected.document_id == document.document_id
            ),
            None,
        )
        if selected_index is not None:
            self._current_index = selected_index
        visible = [
            viewer.document
            for viewer in self.multi_compare_view.occupied_viewers
            if viewer.document is not None
        ]
        self.line_profile_panel.set_reference_priority_ids(
            self._line_reference_priority_ids(visible, document)
        )
        self._update_file_states(visible, document)
        self._evict_resident_documents()

    def _activate_multi_document(self, document_id: str) -> bool:
        viewer = next(
            (
                item
                for item in self.multi_compare_view.occupied_viewers
                if item.document is not None and item.document.document_id == document_id
            ),
            None,
        )
        if viewer is None:
            return False
        viewer.activated.emit(viewer)
        return True

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

    def show_selected_image(self, local_index: int) -> None:
        if self._view_capacity != 1 or local_index < 0:
            return
        split_documents = self._current_split_documents()
        if split_documents:
            if local_index >= len(split_documents):
                return
            self._show_single_split_document(split_documents[local_index])
            return
        page = self.current_comparison_documents()
        if local_index >= len(page):
            return
        selected_index = self._page_start + local_index
        self._show_single_document(page[local_index], selected_index)

    def _set_single_navigation(self, current_key: str) -> None:
        split_documents = self._current_split_documents()
        navigation_documents = split_documents or self.current_comparison_documents()
        items = [
            (document.document_id, str(index + 1), document.display_name)
            for index, document in enumerate(navigation_documents)
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
            self._store_difference_document(
                *cached,
                self.difference_panel.mapping_snapshot_for_payload(cached[1], cached[2]),
                switch_to_result=False,
            )
            if len(self.current_comparison_documents()) >= COMPARISON_PAGE_SIZE:
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
        split_documents = self._current_split_documents()
        split_document = next(
            (document for document in split_documents if document.document_id == key),
            None,
        )
        if split_document is not None:
            self._show_single_split_document(split_document)
            return
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
            self._set_active_document(difference)
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

    def _show_single_split_document(self, document: ImageDocument) -> None:
        split_documents = self._current_split_documents()
        split_index = next(
            (
                index
                for index, candidate in enumerate(split_documents)
                if candidate.document_id == document.document_id
            ),
            None,
        )
        if split_index is None:
            return
        page = self.current_comparison_documents()
        if not page:
            return
        self._layout_mode = "Single View"
        self._view_capacity = 1
        self._channel_split_active = True
        self._split_active_document_id = document.document_id
        self.layout_selector.blockSignals(True)
        self.layout_selector.setCurrentText("Single View")
        self.layout_selector.blockSignals(False)
        self._reset_pixel_status()
        self.viewer.set_document(document, fit=False)
        self.viewer.set_tile_context(split_index + 1, "")
        self.viewer.set_header(
            f"[{split_index + 1}/{len(split_documents)}] {document.display_name}"
        )
        self._set_single_navigation(document.document_id)
        self.viewer.set_roi_bounds(None)
        self.viewer.set_line_selection(None)
        self.central_stack.setCurrentWidget(self.viewer)
        self._visible_document_ids = {page[0].document_id}
        self._set_active_document(document)
        self._update_file_states([page[0]], page[0])
        self._update_comparison_page_controls()
        self._refresh_preload_plan()

    def _show_single_document(self, document: ImageDocument, selected_index: int) -> None:
        previous_page_start = self._page_start
        self._layout_mode = "Single View"
        self._view_capacity = 1
        self._current_index = selected_index
        self._sync_comparison_page_to_index(selected_index)
        self._allow_raw_profile_retry([document.document_id])
        self.layout_selector.blockSignals(True)
        self.layout_selector.setCurrentText("Single View")
        self.layout_selector.blockSignals(False)
        self._reset_pixel_status()
        if self._page_start != previous_page_start:
            self._render_selection(preserve_view=True)
            return

        self._ensure_loaded(document)
        local_slot = selected_index - self._page_start + 1
        self.viewer.set_document(document, fit=False)
        self.viewer.set_tile_context(local_slot, "")
        if len(self.selected_documents) > COMPARISON_PAGE_SIZE:
            self.viewer.set_header(f"[{local_slot}] {document.display_name}")
        else:
            self.viewer.set_header(
                f"[{local_slot}/{len(self.selected_documents)}] {document.display_name}"
            )
        self._set_single_navigation(document.document_id)
        self.viewer.set_roi_bounds(self._shared_roi)
        self.viewer.set_line_selection(self._shared_line)
        self.central_stack.setCurrentWidget(self.viewer)
        self._visible_document_ids = {document.document_id}
        self._set_active_document(document)
        self._update_file_states([document], document)
        self._update_comparison_page_controls()
        self._refresh_preload_plan()

    def next_image(self) -> None:
        documents = self.selected_documents
        if not documents:
            return
        if len(documents) > COMPARISON_PAGE_SIZE:
            self._step_selected_image(1)
            return
        if self._view_capacity == 1:
            if self._cycle_single_navigation(1):
                return
            self._current_index = 0
        elif self._cycle_visible_active(1):
            return
        else:
            self._current_index = 0
        self._reset_pixel_status()
        self._render_selection(preserve_view=True)

    def previous_image(self) -> None:
        documents = self.selected_documents
        if not documents:
            return
        if len(documents) > COMPARISON_PAGE_SIZE:
            self._step_selected_image(-1)
            return
        if self._view_capacity == 1:
            if self._cycle_single_navigation(-1):
                return
            self._current_index = 0
        elif self._cycle_visible_active(-1):
            return
        else:
            self._current_index = 0
        self._reset_pixel_status()
        self._render_selection(preserve_view=True)

    def _selected_navigation_index(self) -> int:
        documents = self.selected_documents
        for document_id in (self._active_document_id, self._focus_document_id):
            if document_id is None:
                continue
            index = next(
                (
                    candidate
                    for candidate, document in enumerate(documents)
                    if document.document_id == document_id
                ),
                None,
            )
            if index is not None:
                return index
        return min(self._current_index, max(0, len(documents) - 1))

    def _step_selected_image(self, step: int) -> None:
        documents = self.selected_documents
        if not documents:
            return
        current_index = self._selected_navigation_index()
        target_index = (current_index + step) % len(documents)
        previous_start = self._normalized_comparison_page_start(documents)
        self._current_index = target_index
        self._sync_comparison_page_to_index(target_index)
        page = self.current_comparison_documents()
        self._allow_raw_profile_retry([document.document_id for document in page])
        target = documents[target_index]
        if self._layout_mode == "Single View":
            self._reset_pixel_status()
            self._render_selection(preserve_view=True)
            return
        if self._page_start != previous_start:
            self._reset_pixel_status()
            self._render_selection(preserve_view=True)
        self._activate_multi_document(target.document_id)

    def previous_comparison_page(self) -> None:
        self._move_comparison_page(-1)

    def next_comparison_page(self) -> None:
        self._move_comparison_page(1)

    def _move_comparison_page(self, step: int) -> None:
        documents = self.selected_documents
        if len(documents) <= COMPARISON_PAGE_SIZE:
            return
        start = self._normalized_comparison_page_start(documents)
        local_index = self._current_page_local_index()
        new_start = start + step * COMPARISON_PAGE_SIZE
        last_start = ((len(documents) - 1) // COMPARISON_PAGE_SIZE) * COMPARISON_PAGE_SIZE
        if new_start < 0:
            self.statusBar().showMessage("Already at the first Comparison Page", 2500)
            self._update_comparison_page_controls()
            return
        if new_start > last_start:
            self.statusBar().showMessage("Already at the last Comparison Page", 2500)
            self._update_comparison_page_controls()
            return

        self._page_start = new_start
        page = documents[new_start : new_start + COMPARISON_PAGE_SIZE]
        local_index = min(local_index, len(page) - 1)
        self._current_index = new_start + local_index
        target = page[local_index]
        self._allow_raw_profile_retry([document.document_id for document in page])
        self._reset_pixel_status()
        self._render_selection(preserve_view=True)
        if self._layout_mode != "Single View":
            self._activate_multi_document(target.document_id)

    def _cycle_single_navigation(self, step: int) -> bool:
        split_documents = self._current_split_documents()
        documents = split_documents or self.selected_documents
        keys = [document.document_id for document in documents]
        if (
            not split_documents
            and self.diff_action.isChecked()
            and self._difference_document is not None
        ):
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

    def _cycle_visible_active(self, step: int) -> bool:
        split_documents = self._current_split_documents()
        documents = split_documents or self.current_comparison_documents()
        if len(documents) < 2:
            return False
        ids = [document.document_id for document in documents]
        current_id = (
            self._split_active_document_id
            if split_documents and self._split_active_document_id in ids
            else self._active_document_id
            if self._active_document_id in ids
            else documents[self._current_page_local_index()].document_id
        )
        current = ids.index(current_id)
        target = documents[(current + step) % len(documents)]
        if split_documents:
            self._split_active_document_id = target.document_id
            self._reset_pixel_status()
            return self._activate_multi_document(target.document_id)
        selected_index = next(
            index
            for index, document in enumerate(self.selected_documents)
            if document.document_id == target.document_id
        )
        self._current_index = selected_index
        self._reset_pixel_status()
        return self._activate_multi_document(target.document_id)

    def next_folder_position(self) -> None:
        self._apply_folder_navigation(1)

    def previous_folder_position(self) -> None:
        self._apply_folder_navigation(-1)

    def _plan_folder_navigation(self, step: int) -> FolderNavigationPlan | None:
        selection = self._folder_navigation_selection()
        if selection is None:
            return None
        return plan_folder_navigation(selection, self._folder_documents, step)

    def _apply_folder_navigation(self, step: int) -> None:
        selection = self._folder_navigation_selection()
        if selection is None:
            self.statusBar().showMessage(
                "Folder Position requires 1–6 selected images from different folders",
                5000,
            )
            return
        plan = plan_folder_navigation(selection, self._folder_documents, step)
        if plan is None:
            direction = "previous" if step < 0 else "next"
            self.statusBar().showMessage(
                f"No {direction} folder position; selection was not changed",
                5000,
            )
            return
        if self.diff_action.isChecked() and len(self.selected_documents) == 2:
            current_ids = [document.document_id for document in self.selected_documents]
            if self._focus_document_id in current_ids:
                self._pending_position_focus = current_ids.index(self._focus_document_id)
            else:
                self._pending_position_focus = "difference"
        for folder_key, index in zip(plan.folder_keys, plan.indices, strict=True):
            self._folder_indices[folder_key] = index
        if isinstance(self._pending_position_focus, int):
            self._focus_document_id = plan.document_ids[self._pending_position_focus]
            self._promote_multi_document(self._focus_document_id)
        self._select_document_ids(
            list(plan.document_ids),
            preserve_view=True,
            preserve_overlays=True,
        )
        positions = ", ".join(
            f"{index + 1}/{len(self._folder_documents[folder_key])}"
            for folder_key, index in zip(plan.folder_keys, plan.indices, strict=True)
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
        selected_set = set(selected_ids)
        required = {
            document.document_id
            for document in self.current_comparison_documents()
            if document.document_id not in selected_set
        }
        if self._difference_source_ids is not None:
            required.update(
                document_id
                for document_id in self._difference_source_ids
                if document_id not in selected_set
            )
        self._cancel_obsolete_loads(required)
        self._invalidate_preload_plan()
        self.document_list.blockSignals(True)
        try:
            for document_id in selected_ids:
                self._raw_profile_prompt_suppressed.discard(document_id)
                self.residency_manager.remove(document_id)
                document = self.documents.pop(document_id, None)
                if document is not None and document.source_path is not None:
                    self._document_id_by_path.pop(self._path_key(document.source_path), None)
                    self._remove_document_from_folder(document_id, document.source_path)
                self.document_list.remove_document_item(document_id)
                self._invalidate_channel_views(document_id)
        finally:
            self.document_list.blockSignals(False)
        self._selection_order = [
            document_id for document_id in self._selection_order if document_id not in selected_set
        ]
        if self._selection_order:
            self._current_index = min(self._current_index, len(self._selection_order) - 1)
            self._sync_comparison_page_to_index(self._current_index)
        else:
            self._current_index = 0
            self._page_start = 0
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
        for document_id in self._selection_order:
            self._remember_folder_index(document_id)
        if not preserve_view:
            self._current_index = 0
            self._page_start = 0
            self._primary_page_slot = 0
            if self._layout_mode != "Single View":
                self._focus_document_id = None
        elif self._selection_order:
            self._current_index = min(self._current_index, len(self._selection_order) - 1)
            self._sync_comparison_page_to_index(self._current_index)
        else:
            self._current_index = 0
            self._page_start = 0

        page_ids = [document.document_id for document in self.current_comparison_documents()]
        self._promote_running_preloads(page_ids)
        self._invalidate_preload_plan()
        self._allow_raw_profile_retry(page_ids)
        required = set(page_ids)
        if self._difference_source_ids is not None:
            required.update(self._difference_source_ids)
        self._cancel_obsolete_loads(required)

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
            for document in self.current_comparison_documents()
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
        self.comparison_analysis_panel.set_documents(ready, self._shared_roi)
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
            for document in self.current_comparison_documents()
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
            self._line_source_documents(),
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
            for document in self.current_comparison_documents()
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
        mapping = self.difference_panel.mapping_snapshot_for_payload(numerical, preview)
        force_single = len(self.current_comparison_documents()) >= COMPARISON_PAGE_SIZE
        if force_single:
            self._capture_six_image_diff_restore_state()
        stay_single = force_single or self._layout_mode == "Single View"
        self._store_difference_document(
            title,
            numerical,
            preview,
            mapping,
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
        preserve_folder_primary = isinstance(self._pending_position_focus, int)
        if self._difference_document is not None and not preserve_folder_primary:
            self._focus_document_id = self._difference_document.document_id
            self._promote_multi_document(self._difference_document.document_id)
        self._pending_position_focus = None
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
        mapping = self.difference_panel.mapping_snapshot_for_payload(numerical, preview)
        self._store_difference_document(
            title,
            numerical,
            preview,
            mapping,
            switch_to_result=False,
        )
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
        mapping: DifferenceSamplingSnapshot | None = None,
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
        self._apply_difference_mapping(difference, mapping)
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
                self._reference_value_at(viewer.document, x, y)
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
    def _apply_difference_mapping(
        document: ImageDocument,
        mapping: DifferenceSamplingSnapshot | None,
    ) -> None:
        if mapping is None:
            if document.source is not None:
                document.spatial_sampling = SpatialSampling.identity(
                    (int(document.source.shape[0]), int(document.source.shape[1]))
                )
            document.sample_channel = None
            return

        source_shape = (
            None
            if document.source is None
            else (int(document.source.shape[0]), int(document.source.shape[1]))
        )
        if mapping.spatial_sampling.sample_shape != source_shape:
            raise ValueError("Difference spatial sampling must match its native result shape")
        document.spatial_sampling = mapping.spatial_sampling
        document.sample_channel = mapping.sample_channel

    @staticmethod
    def _reference_value_at(document: ImageDocument, x: int, y: int) -> object:
        lookup_at_reference = getattr(document, "sample_lookup_at_reference", None)
        lookup = (
            lookup_at_reference(x, y) if callable(lookup_at_reference) else document.pixel_at(x, y)
        )
        return None if lookup is None else getattr(lookup, "value", lookup)

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
        files = [path for path in paths if path.is_file()]
        folder_result = self.register_folders(folders) if folders else None
        document_ids = self._register_inputs(
            discover_image_inputs(files),
            resolve_raw_profiles=True,
        )
        if document_ids:
            self._select_document_ids(document_ids)

        messages: list[str] = []
        if document_ids:
            messages.append(f"Opened {len(document_ids)} image(s)")
        if folder_result is not None:
            messages.append(self._folder_registration_message(folder_result))
        if messages:
            self.statusBar().showMessage(" · ".join(messages), 5000)

    def _update_empty_workspace_state(self) -> None:
        self.empty_workspace.set_registered_documents(bool(self.documents))

    def _update_document_item(self, document: ImageDocument) -> None:
        self.document_list.update_document_item(
            document.document_id,
            self._document_item_text(document),
            document.error_state or str(document.source_path or ""),
        )
        self.document_list.set_document_state(
            document.document_id,
            visible=document.document_id in self._visible_document_ids,
            active=document.document_id == self._active_document_id,
            loading_state=document.loading_state,
            resident=document.source is not None,
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

    def _folder_navigation_selection(self) -> list[tuple[str, str]] | None:
        documents = self.selected_documents
        if not 1 <= len(documents) <= 6:
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
        return self._preferred_dialog_directory(self.application_settings.default_open_directory)

    def _export_dialog_directory(self) -> str:
        return self._preferred_dialog_directory(self.application_settings.default_export_directory)

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

    def _prepare_floating_workspaces_for_shutdown(self) -> None:
        """Reattach managed floating docks while the main native window is valid."""

        hardening = self.__dict__.get("beta_workspace_hardening_controller")
        quiesce_hardening = getattr(hardening, "quiesce_pending_callbacks", None)
        if callable(quiesce_hardening):
            quiesce_hardening()

        for dock in (self.bottom_dock, self.iqa_dock):
            title = PlotsDockTitleBar.controller_for_dock(dock)
            if title is not None:
                title.quiesce_pending_callbacks()
            if not dock.isFloating():
                continue
            if dock.isMaximized():
                dock.showNormal()
            dock.hide()
            area = (
                title.shutdown_dock_area()
                if title is not None
                else Qt.DockWidgetArea.RightDockWidgetArea
            )
            self.addDockWidget(area, dock)
            dock.setFloating(False)

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
        self.iqa_dock.hide()
        self.set_layout_mode("Auto")
        self.statusBar().showMessage("Workspace layout reset", 3000)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._closing = True
        self._save_ui_state()
        self._prepare_floating_workspaces_for_shutdown()
        self.comparison_analysis_panel.shutdown()
        self.line_profile_panel.shutdown()
        self.difference_panel.shutdown()
        self.iqa_controller.shutdown()
        for worker in tuple(self._workers.values()):
            worker.cancel()
        self._invalidate_preload_plan(include_promoted=True)
        if not self._load_pool.waitForDone(3000):
            LOGGER.warning("Image loads did not finish within the shutdown grace period")
        if not self._preload_pool.waitForDone(3000):
            LOGGER.warning("Image preloads did not finish within the shutdown grace period")
        if not QThreadPool.globalInstance().waitForDone(3000):
            LOGGER.warning("Background tasks did not finish within the shutdown grace period")
        self._workers.clear()
        self._preload_workers.clear()
        self._preload_worker_requests.clear()
        self._promoted_preload_tokens.clear()
        event.accept()
