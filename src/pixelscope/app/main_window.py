from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
from PySide6.QtCore import QItemSelectionModel, Qt, QThreadPool
from PySide6.QtGui import QAction, QCloseEvent, QDragEnterEvent, QDropEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pixelscope.core.bayer import bayer_channel_at
from pixelscope.core.channel_views import split_document_channels
from pixelscope.core.diff_engine import absolute_difference, signed_difference
from pixelscope.core.display_transform import (
    render_absolute_difference,
    render_signed_difference,
)
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineSelection, clamp_line
from pixelscope.core.roi import RoiBounds, clamp_roi
from pixelscope.io.path_discovery import (
    ImageInput,
    discover_image_inputs,
    natural_sort_key,
)
from pixelscope.io.raw_profile import RawProfile
from pixelscope.ui.comparison_analysis_panel import ComparisonAnalysisPanel
from pixelscope.ui.document_list import DocumentListWidget
from pixelscope.ui.image_viewer import ImageViewer
from pixelscope.ui.line_profile_panel import LineProfilePanel
from pixelscope.ui.multi_compare_view import MultiCompareView
from pixelscope.ui.raw_open_dialog import RawOpenDialog
from pixelscope.workers.image_load_worker import ImageLoadWorker
from pixelscope.workers.task_worker import TaskError, TaskWorker

LOGGER = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Document registration, selection-driven comparison, and analysis lifecycle."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PixelScope")
        self.resize(1400, 850)
        self.setAcceptDrops(True)

        self.documents: dict[str, ImageDocument] = {}
        self._document_id_by_path: dict[str, str] = {}
        self._raw_profile_paths: dict[str, Path] = {}
        self._raw_profiles: dict[str, RawProfile] = {}
        self._workers: dict[str, TaskWorker] = {}
        self._load_tokens: dict[str, int] = {}
        self._selection_order: list[str] = []
        self._folder_documents: dict[str, list[str]] = {}
        self._folder_paths: dict[str, Path] = {}
        self._folder_indices: dict[str, int] = {}
        self._current_index = 0
        self._page_start = 0
        self._view_capacity = 1
        self._shared_roi: RoiBounds | None = None
        self._shared_line: LineSelection | None = None
        self._difference_gain = 1.0
        self._split_channels = False
        self._channel_split_active = False
        self._channel_view_cache: dict[tuple[str, int], list[ImageDocument]] = {}

        pool = QThreadPool.globalInstance()
        pool.setMaxThreadCount(min(4, max(1, pool.maxThreadCount())))

        self.viewer = ImageViewer()
        self.multi_compare_view = MultiCompareView()
        self.central_stack = QStackedWidget()
        self.central_stack.addWidget(self.viewer)
        self.central_stack.addWidget(self.multi_compare_view)

        self.document_list = DocumentListWidget()
        self.document_list.itemSelectionChanged.connect(  # type: ignore[attr-defined]
            self._selection_changed
        )
        self.document_list.paths_dropped.connect(self._handle_dropped_paths)
        self.document_list.previous_pair_requested.connect(self.previous_folder_pair)
        self.document_list.next_pair_requested.connect(self.next_folder_pair)

        self.comparison_analysis_panel = ComparisonAnalysisPanel()
        self.line_profile_panel = LineProfilePanel()
        self.analysis_tabs = QTabWidget()
        self.analysis_tabs.addTab(self.comparison_analysis_panel, "Statistics")
        self.analysis_tabs.addTab(
            self.comparison_analysis_panel.histogram_grid,
            "Histogram",
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
        self._create_actions()
        self._create_selection_shortcuts()

        self.pixel_status = QLabel("Position (   -,    -)")
        self.pixel_status.setMinimumWidth(520)
        self.pixel_status.setStyleSheet("font-family: Consolas, 'Courier New', monospace;")
        self.statusBar().addPermanentWidget(self.pixel_status, 1)
        self.statusBar().showMessage("Drop images or folders, or use File > Open")

    def _build_layout(self) -> None:
        sidebar_splitter = QSplitter(Qt.Orientation.Vertical)
        documents_container = QWidget()
        documents_layout = QVBoxLayout(documents_container)
        documents_layout.setContentsMargins(4, 4, 4, 4)
        self.files_label = QLabel("Files")
        self.files_label.setStyleSheet("font-weight: bold; padding: 3px")
        documents_layout.addWidget(self.files_label)
        documents_layout.addWidget(self.document_list)

        analysis_container = QWidget()
        analysis_layout = QVBoxLayout(analysis_container)
        analysis_layout.setContentsMargins(4, 4, 4, 4)
        analysis_label = QLabel("Analysis")
        analysis_label.setStyleSheet("font-weight: bold; padding: 3px")
        analysis_layout.addWidget(analysis_label)
        analysis_layout.addWidget(self.analysis_tabs)
        sidebar_splitter.addWidget(documents_container)
        sidebar_splitter.addWidget(analysis_container)
        sidebar_splitter.setStretchFactor(0, 2)
        sidebar_splitter.setStretchFactor(1, 3)

        sidebar = QWidget()
        sidebar.setMinimumWidth(320)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.addWidget(sidebar_splitter)
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.addWidget(sidebar)
        self.viewer_splitter = QSplitter(Qt.Orientation.Vertical)
        self.viewer_splitter.addWidget(self.central_stack)
        self.viewer_splitter.addWidget(self.line_profile_panel)
        self.viewer_splitter.setStretchFactor(0, 3)
        self.viewer_splitter.setStretchFactor(1, 1)
        self.viewer_splitter.setSizes([610, 240])
        self.main_splitter.addWidget(self.viewer_splitter)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([390, 1010])
        self.setCentralWidget(self.main_splitter)

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
        menus = {
            "File": menu_bar.addMenu("&File"),
            "Edit": menu_bar.addMenu("&Edit"),
            "Selection": menu_bar.addMenu("&Selection"),
            "View": menu_bar.addMenu("&View"),
        }
        add_action("File", "Open Images...", self.open_images, "Ctrl+O")
        add_action("File", "Open Folder...", self.open_folder, "Ctrl+Shift+O")
        add_action("File", "Open RAW with Profile...", self.open_raw)
        menus["File"].addSeparator()
        add_action("File", "Exit", self.close, "Alt+F4")

        add_action("Edit", "Remove Selected", self.remove_selected, "Delete")
        add_action("Edit", "Clear ROI", self.clear_roi, "Esc")
        add_action("Edit", "Clear Line Profile", self.clear_line, "Shift+Esc")

        add_action("Selection", "Compare Selection", self.compare_selection, "C")
        add_action("Selection", "Select All", self.select_all_documents, "Ctrl+A")
        menus["Selection"].addSeparator()
        add_action("Selection", "Previous Image", self.previous_image, "Shift+Space")
        add_action("Selection", "Next Image", self.next_image, "Space")
        previous_pair = add_action("Selection", "Previous Folder Pair", self.previous_folder_pair)
        next_pair = add_action("Selection", "Next Folder Pair", self.next_folder_pair)
        previous_pair.setText("Previous Folder Pair\tPageUp")
        next_pair.setText("Next Folder Pair\tPageDown")

        add_action("View", "Single Viewer", lambda: self.set_view_capacity(1), "Ctrl+1")
        add_action("View", "2 Viewers", lambda: self.set_view_capacity(2), "Ctrl+2")
        add_action("View", "4 Viewers", lambda: self.set_view_capacity(4), "Ctrl+4")
        add_action("View", "6 Viewers", lambda: self.set_view_capacity(6), "Ctrl+6")
        split_channels = add_action(
            "View",
            "Split Channels in 4 Views",
            self._set_split_channels,
        )
        split_channels.setCheckable(True)
        menus["View"].addSeparator()
        add_action("View", "Fit Image", self.fit_image, "F")
        add_action("View", "100% Zoom", self.zoom_100_percent, "Ctrl+0")
        menus["View"].addSeparator()
        add_action("View", "Show Signed Difference", self.show_signed_difference, "D")
        add_action(
            "View",
            "Show Absolute Difference",
            self.show_absolute_difference,
            "Shift+D",
        )
        add_action("View", "Absolute Difference Gain...", self.set_difference_gain)
        self._update_action_states()

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

    def _update_action_states(self) -> None:
        documents = self.selected_documents
        exactly_two = len(documents) == 2
        for name in ("Show Signed Difference", "Show Absolute Difference"):
            action = self.action_map.get(name)
            if action is not None:
                action.setEnabled(exactly_two)
        split_action = self.action_map.get("Split Channels in 4 Views")
        if split_action is not None:
            split_action.setEnabled(
                len(documents) == 1 and documents[0].channel_layout in ("RGB", "RGBA", "BAYER")
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
        )
        if select:
            self._select_document_ids([document.document_id])

    def open_images(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Open images",
            "",
            "Images (*.png *.bmp *.raw);;All files (*)",
        )
        if paths:
            supplied_paths = [Path(path) for path in paths]
            session = self._active_folder_selection()
            if session is not None:
                self._register_paths_during_pair(supplied_paths, session)
                return
            inputs = discover_image_inputs(supplied_paths)
            self._register_inputs(inputs, select_all=True)

    def open_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Open image folder")
        if path:
            folder = Path(path)
            session = self._active_folder_selection()
            if session is not None:
                self._register_paths_during_pair([folder], session)
                return
            inputs = discover_image_inputs((folder,))
            self._register_inputs(inputs, select_all=False)

    def compare_two_folders(self) -> None:
        first = QFileDialog.getExistingDirectory(self, "Select first image folder")
        if not first:
            return
        second = QFileDialog.getExistingDirectory(self, "Select second image folder")
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
        path, _ = QFileDialog.getOpenFileName(self, "Open RAW", "", "RAW files (*.*)")
        if not path:
            return
        raw_path = Path(path).resolve()
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
        )
        return document.document_id

    def _confirm_raw_profile(
        self,
        image_input: ImageInput,
        existing_id: str | None,
    ) -> RawProfile | None:
        dialog = RawOpenDialog(self)
        initial_profile: RawProfile | None = None
        if image_input.raw_profile_path is not None:
            try:
                initial_profile = RawProfile.load_json(image_input.raw_profile_path)
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
        if initial_profile is not None:
            dialog.set_profile(initial_profile)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.profile()

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
        worker = ImageLoadWorker(path, raw_profile)
        worker.signals.started.connect(
            lambda _task_id, _document_id, _generation: self.statusBar().showMessage(
                f"Loading {path.name}..."
            )
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
        QThreadPool.globalInstance().start(worker)

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
        self._update_document_item(result)
        self._render_selection(preserve_view=True)
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
        self._render_selection(preserve_view=True)
        self.statusBar().showMessage(f"Failed to load {path.name}: {error.message}", 5000)

    def _worker_finished(self, task_id: str) -> None:
        self._workers.pop(task_id, None)

    def _selection_changed(self) -> None:
        selected_ids = [
            str(item.data(0, Qt.ItemDataRole.UserRole))
            for item in self.document_list.document_items()
            if item.isSelected()
        ]
        selected_set = set(selected_ids)
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
        self._shared_line = None
        self._reset_pixel_status()
        self._render_selection()

    def _render_selection(self, preserve_view: bool = False) -> None:
        documents = self.selected_documents
        self._update_action_states()
        self._channel_split_active = False
        if not documents:
            self.viewer.set_document(None)
            self.multi_compare_view.set_documents([], 0, 0, None, None, preserve_view)
            self.comparison_analysis_panel.clear()
            self.line_profile_panel.clear()
            self._reset_pixel_status()
            return

        self._current_index = min(self._current_index, len(documents) - 1)
        if self._view_capacity == 1:
            self._page_start = (self._current_index // 6) * 6
        else:
            last_page = ((len(documents) - 1) // self._view_capacity) * self._view_capacity
            self._page_start = min(self._page_start, last_page)
        analysis_limit = 6 if self._view_capacity == 1 else self._view_capacity
        analysis_page = documents[self._page_start : self._page_start + analysis_limit]
        for document in analysis_page:
            self._ensure_loaded(document)
        ready_analysis = [document for document in analysis_page if document.source is not None]
        self._normalize_shared_roi(ready_analysis)
        self._normalize_shared_line(ready_analysis)

        if self._view_capacity == 1:
            document = documents[self._current_index]
            self._ensure_loaded(document)
            self.viewer.set_document(document, fit=not preserve_view)
            self.viewer.set_header(
                f"[{self._current_index + 1}/{len(documents)}] {document.display_name}"
            )
            self.viewer.set_roi_bounds(self._shared_roi)
            self.viewer.set_line_selection(self._shared_line)
            self.central_stack.setCurrentWidget(self.viewer)
        elif (
            self._view_capacity == 4
            and self._split_channels
            and len(documents) == 1
            and documents[0].source is not None
        ):
            document = documents[0]
            cache_key = (document.document_id, document.generation)
            channel_documents = self._channel_view_cache.get(cache_key)
            if channel_documents is None:
                channel_documents = split_document_channels(document)
                self._channel_view_cache = {cache_key: channel_documents}
            self._channel_split_active = bool(channel_documents)
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
        else:
            start = self._page_start
            self._page_start = start
            visible = documents[start : start + self._view_capacity]
            for document in visible:
                self._ensure_loaded(document)
            self.multi_compare_view.set_capacity(self._view_capacity)
            self.multi_compare_view.set_documents(
                visible,
                start,
                len(documents),
                self._shared_roi,
                self._shared_line,
                preserve_view,
            )
            self.central_stack.setCurrentWidget(self.multi_compare_view)

        self.comparison_analysis_panel.set_documents(ready_analysis, self._shared_roi)
        self.line_profile_panel.set_documents(ready_analysis, self._shared_line)

    def _set_split_channels(self, enabled: bool) -> None:
        self._split_channels = enabled
        self._reset_pixel_status()
        self._render_selection(preserve_view=False)

    def compare_selection(self) -> None:
        count = len(self.selected_documents)
        if count < 2:
            QMessageBox.information(
                self, "Comparison selection", "Select two or more documents in the list."
            )
            return
        self.set_view_capacity(2 if count <= 2 else 4 if count <= 4 else 6)

    def set_view_capacity(self, capacity: int) -> None:
        if capacity not in (1, 2, 4, 6):
            raise ValueError("viewer capacity must be 1, 2, 4, or 6")
        changed = capacity != self._view_capacity
        self._view_capacity = capacity
        self._page_start = (
            self._current_index if capacity == 1 else (self._current_index // capacity) * capacity
        )
        if changed:
            self._reset_pixel_status()
        self._render_selection(preserve_view=not changed)

    def show_selected_image(self, selected_index: int) -> None:
        documents = self.selected_documents
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

    def next_image(self) -> None:
        documents = self.selected_documents
        if not documents:
            return
        if self._view_capacity == 1:
            self._current_index = (self._current_index + 1) % len(documents)
            self._page_start = (self._current_index // 6) * 6
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
            self._current_index = (self._current_index - 1) % len(documents)
            self._page_start = (self._current_index // 6) * 6
        else:
            self._page_start = (
                self._page_start - self._view_capacity
                if self._page_start >= self._view_capacity
                else ((len(documents) - 1) // self._view_capacity) * self._view_capacity
            )
            self._current_index = self._page_start
        self._reset_pixel_status()
        self._render_selection(preserve_view=True)

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
        for (folder_key, _current_id), index in zip(session, target_indices, strict=True):
            self._folder_indices[folder_key] = index
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
        for document_id in self._selection_order:
            self._remember_folder_index(document_id)
        if not preserve_view:
            self._current_index = 0
            self._page_start = 0
        if not preserve_overlays:
            self._shared_roi = None
            self._shared_line = None
        self._reset_pixel_status()
        self._render_selection(preserve_view=preserve_view)

    def _shared_roi_changed(self, bounds: object) -> None:
        if self._channel_split_active:
            return
        if not isinstance(bounds, RoiBounds):
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
                selection.y,
                selection.x2,
            )
        except ValueError:
            return
        self.viewer.set_line_selection(self._shared_line)
        self.multi_compare_view.set_shared_line(self._shared_line)
        self.line_profile_panel.set_documents(ready, self._shared_line)

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
                selection.y,
                selection.x2,
            )
        except ValueError:
            self._shared_line = None

    def clear_roi(self) -> None:
        self._shared_roi = None
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

    def clear_line(self) -> None:
        self._shared_line = None
        self.viewer.set_line_selection(None)
        self.multi_compare_view.clear_line()
        self.line_profile_panel.clear_selection()

    def _require_pair(self) -> tuple[ImageDocument, ImageDocument] | None:
        ready = [document for document in self.selected_documents if document.source is not None]
        if len(ready) < 2:
            QMessageBox.information(
                self, "Two images required", "Select at least two loaded documents."
            )
            return None
        a, b = ready[:2]
        source_a = self._rgb_comparison_source(a)
        source_b = self._rgb_comparison_source(b)
        if source_a.shape != source_b.shape:
            QMessageBox.warning(
                self,
                "Shape mismatch",
                f"{a.display_name} {source_a.shape} and "
                f"{b.display_name} {source_b.shape} cannot be differenced.",
            )
            return None
        return a, b

    def show_signed_difference(self) -> None:
        self._start_difference("signed")

    def show_absolute_difference(self) -> None:
        self._start_difference("absolute")

    def _start_difference(self, mode: str) -> None:
        pair = self._require_pair()
        if pair is None:
            return
        a, b = pair
        source_a = self._rgb_comparison_source(a)
        source_b = self._rgb_comparison_source(b)
        context = (a.document_id, a.generation, b.document_id, b.generation)
        gain = self._difference_gain

        def calculate() -> tuple[str, np.ndarray[Any, Any], np.ndarray[Any, Any]]:
            if mode == "signed":
                numerical = signed_difference(source_a, source_b)
                preview = render_signed_difference(numerical)
                title = f"Signed: {a.display_name} - {b.display_name}"
            else:
                numerical = absolute_difference(source_a, source_b)
                preview = render_absolute_difference(numerical, gain)
                title = f"Absolute: {a.display_name} - {b.display_name}"
            return title, numerical, preview

        worker = TaskWorker(calculate)
        worker.signals.started.connect(
            lambda _task_id, _document_id, _generation: self.statusBar().showMessage(
                f"Calculating {mode} difference..."
            )
        )
        worker.signals.succeeded.connect(
            lambda _task_id, _document_id, _generation, result: self._difference_succeeded(
                context, result
            )
        )
        worker.signals.failed.connect(self._analysis_failed)
        worker.signals.finished.connect(self._worker_finished)
        self._workers[worker.task_id] = worker
        QThreadPool.globalInstance().start(worker)

    def _difference_succeeded(self, context: tuple[str, int, str, int], result: object) -> None:
        a_id, a_generation, b_id, b_generation = context
        a, b = self.documents.get(a_id), self.documents.get(b_id)
        if (
            a is None
            or b is None
            or a.generation != a_generation
            or b.generation != b_generation
            or not isinstance(result, tuple)
            or len(result) != 3
        ):
            return
        title, numerical, preview = result
        if (
            not isinstance(title, str)
            or not isinstance(numerical, np.ndarray)
            or not isinstance(preview, np.ndarray)
        ):
            return
        difference = ImageDocument.from_array(
            numerical,
            title,
            channel_layout="DIFFERENCE",
            prepared_preview=preview,
        )
        self._view_capacity = 1
        self.viewer.set_document(difference)
        self.viewer.set_header(title)
        self.central_stack.setCurrentWidget(self.viewer)
        self.statusBar().showMessage(f"Ready: {title}", 4000)

    def _analysis_failed(
        self,
        _task_id: str,
        _document_id: str | None,
        _generation: int,
        error: TaskError,
    ) -> None:
        LOGGER.error("Analysis failed: %s\n%s", error.message, error.traceback_text)
        QMessageBox.warning(self, "Analysis failed", error.message)

    def set_difference_gain(self) -> None:
        value, accepted = QInputDialog.getDouble(
            self,
            "Absolute difference gain",
            "Display gain",
            self._difference_gain,
            0.01,
            1000.0,
            2,
        )
        if accepted:
            self._difference_gain = value

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

    def _inspect_pixel(self, x: int, y: int, value: object) -> None:
        document = self.viewer.document
        if document is None:
            return
        self.pixel_status.setText(self._pixel_status_text(x, y, [value], [document]))

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
            self.pixel_status.setText(self._pixel_status_text(x, y, values, documents))

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
        self.pixel_status.setText("Position (   -,    -)")

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
        marker = {
            "pending": "[pending] ",
            "loading": "[loading] ",
            "error": "[error] ",
        }.get(document.loading_state, "")
        return f"{marker}{document.display_name}"

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

    def closeEvent(self, event: QCloseEvent) -> None:
        self.comparison_analysis_panel.shutdown()
        self.line_profile_panel.shutdown()
        for worker in tuple(self._workers.values()):
            worker.cancel()
        if not QThreadPool.globalInstance().waitForDone(3000):
            LOGGER.warning("Background tasks did not finish within the shutdown grace period")
        self._workers.clear()
        event.accept()
