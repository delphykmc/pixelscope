from __future__ import annotations

import weakref
from typing import Any, cast

from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtGui import QWindow
from PySide6.QtWidgets import QDockWidget, QLabel, QMainWindow, QSizePolicy, QSplitter, QWidget

from pixelscope.ui.design_tokens import (
    TOKENS,
    WORKSPACE_CHROME_HEIGHT,
    panel_heading_style,
)
from pixelscope.ui.lifecycle_hooks import OwnerCallback, WeakOwnerHook
from pixelscope.ui.plots_dock_title import PlotsDockTitleBar

class _WorkspaceDockTopLevelController(QObject):
    """Keep PixelScope dock chrome while QDockWidget owns floating topology."""

    def __init__(self, dock: QDockWidget, *, docked_title_bar: QWidget | None = None) -> None:
        super().__init__(dock)
        self._dock = dock
        self._docked_title_bar = docked_title_bar
        self._normalizing = False
        self._quiescing = False
        self._normalize_timer = QTimer(self)
        self._normalize_timer.setSingleShot(True)
        self._normalize_timer.timeout.connect(  # type: ignore[attr-defined]
            self._normalize_floating
        )
        self._detach_timer = QTimer(self)
        self._detach_timer.setSingleShot(True)
        self._detach_timer.timeout.connect(  # type: ignore[attr-defined]
            self._detach_transient_parent
        )
        dock.topLevelChanged.connect(self._top_level_changed)  # type: ignore[attr-defined]
        dock.visibilityChanged.connect(self._visibility_changed)  # type: ignore[attr-defined]
        if dock.isFloating():
            self._top_level_changed(True)

    def _top_level_changed(self, floating: bool) -> None:
        if self._quiescing:
            return
        if floating:
            # Run after QDockWidget and the geometry/title controllers have
            # completed their own topLevelChanged handlers.
            self._normalize_timer.start(0)
            return
        self._restore_docked_title_bar()

    def _visibility_changed(self, visible: bool) -> None:
        if not self._quiescing and visible and self._dock.isFloating():
            # IQA installs its title lazily on first show.
            self._normalize_timer.start(0)

    def _normalize_floating(self) -> None:
        if self._quiescing or self._normalizing or not self._dock.isFloating():
            return
        self._normalizing = True
        try:
            title_bar = self._dock.titleBarWidget()
            if isinstance(title_bar, PlotsDockTitleBar):
                self._docked_title_bar = title_bar
            else:
                retained = PlotsDockTitleBar.controller_for_dock(self._dock)
                if retained is not None:
                    self._docked_title_bar = retained
                    self._dock.setTitleBarWidget(retained)
                    retained.show()
                    retained.sync(True)

            # Do not rewrite Qt window flags or native HWND styles here. Those
            # mutations race QDockWidget's native move/dock loop on Windows and
            # can leave the window following the cursor after a docking drop.
            if not self._dock.isHidden():
                self._detach_timer.start(0)
        finally:
            self._normalizing = False

    def _detach_transient_parent(self) -> None:
        if self._quiescing or not self._dock.isFloating() or self._dock.isHidden():
            return
        handle = self._dock.windowHandle()
        if handle is not None and handle.transientParent() is not None:
            # QWindow::setTransientParent accepts a null pointer to clear the
            # relation, although the PySide stub currently types it as non-null.
            handle.setTransientParent(cast(QWindow, None))

    def quiesce_pending_callbacks(self) -> None:
        """Stop queued native-window adjustments before application teardown."""

        self._quiescing = True
        self._normalize_timer.stop()
        self._detach_timer.stop()

    def _restore_docked_title_bar(self) -> None:
        if self._dock.isFloating():
            return
        title_bar = self._docked_title_bar or PlotsDockTitleBar.controller_for_dock(self._dock)
        if title_bar is not None:
            self._docked_title_bar = title_bar
        if title_bar is not None and self._dock.titleBarWidget() is not title_bar:
            self._dock.setTitleBarWidget(title_bar)
            title_bar.show()
        if isinstance(title_bar, PlotsDockTitleBar):
            title_bar.sync(False)


class BetaWorkspaceHardeningController(QObject):
    """Production-only UI geometry/window hardening without new state authority."""

    def __init__(self, window: QMainWindow) -> None:
        super().__init__(window)
        self._window_ref = weakref.ref(window)
        self._dock_controllers: list[_WorkspaceDockTopLevelController] = []
        self._install_layout_policy()
        self._install_workspace_windows()

    @property
    def window(self) -> QMainWindow:
        window = self._window_ref()
        if window is None:
            raise RuntimeError("Beta workspace window was destroyed")
        return window

    def _install_layout_policy(self) -> None:
        window = self.window
        main_splitter = getattr(window, "main_splitter", None)
        if main_splitter is not None and main_splitter.count() >= 2:
            sidebar = main_splitter.widget(0)
            presentation = main_splitter.widget(1)
            # Keep QSplitter's native allocation/collapse semantics. Files is a
            # secondary pane and may collapse; the Image workspace is the primary
            # surface and must never snap to zero width.
            sidebar.setMinimumWidth(0)
            _set_horizontal_policy(sidebar, QSizePolicy.Policy.Ignored)
            presentation.setMinimumWidth(0)
            main_splitter.setChildrenCollapsible(True)
            main_splitter.setCollapsible(0, True)
            main_splitter.setCollapsible(1, False)

        # Treat the upper edge as one continuous workspace chrome line. The
        # original sidebar containers had a 4 px inset while the Image command
        # bar and QDockWidget titles started at the main workspace edge, which
        # made their lower separators land on different Y coordinates.
        sidebar_splitter = getattr(window, "sidebar_splitter", None)
        if isinstance(sidebar_splitter, QSplitter):
            for index in range(min(2, sidebar_splitter.count())):
                container = sidebar_splitter.widget(index)
                layout = container.layout() if isinstance(container, QWidget) else None
                if layout is None or layout.count() == 0:
                    continue
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(0)
                heading = layout.itemAt(0).widget()
                if isinstance(heading, QLabel):
                    heading.setFixedHeight(WORKSPACE_CHROME_HEIGHT)
                    heading.setStyleSheet(panel_heading_style())

        presentation_controls = getattr(window, "presentation_controls", None)
        if isinstance(presentation_controls, QWidget):
            presentation_controls.setMinimumWidth(0)
            presentation_controls.setFixedHeight(WORKSPACE_CHROME_HEIGHT)

        self._install_presentation_text_accessibility()

        for widget_name in ("document_list", "analysis_tabs"):
            widget = getattr(window, widget_name, None)
            if isinstance(widget, QWidget):
                widget.setMinimumWidth(0)

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

        # Populated Files and Multi View surfaces may contain long document
        # labels, but those labels must not become a desktop-wide minimum. Files
        # remains the Qt-collapsible secondary pane and Image remains the
        # non-collapsible primary pane established above.
        for widget_name in ("central_stack", "viewer", "multi_compare_view"):
            widget = getattr(window, widget_name, None)
            if isinstance(widget, QWidget):
                widget.setMinimumWidth(0)
                _set_horizontal_policy(widget, QSizePolicy.Policy.Ignored)

        if isinstance(main_splitter, QWidget):
            _set_vertical_policy(main_splitter, QSizePolicy.Policy.Ignored)

    def _install_presentation_text_accessibility(self) -> None:
        window = self.window

        page_label = getattr(window, "comparison_page_label", None)
        range_label = getattr(window, "comparison_page_range_label", None)

        def sync_page_labels() -> None:
            if isinstance(page_label, QLabel):
                _sync_full_text_label(page_label, "Comparison Page status")
            if isinstance(range_label, QLabel):
                _sync_full_text_label(range_label, "Comparison Page selected range")

        page_group = getattr(window, "comparison_page_group", None)
        update_page_controls = getattr(window, "_update_comparison_page_controls", None)
        if (
            isinstance(page_group, QWidget)
            and callable(update_page_controls)
            and not bool(page_group.property("betaFullTextAccessibility"))
        ):
            page_group.setProperty("betaFullTextAccessibility", True)
            original_update = OwnerCallback(update_page_controls)

            def update_with_accessibility(_window: Any) -> None:
                original_update()
                sync_page_labels()

            dynamic_window = cast(Any, window)
            dynamic_window._update_comparison_page_controls = WeakOwnerHook(
                window, update_with_accessibility
            )
        sync_page_labels()

        review = getattr(window, "review_selection_controller", None)
        count_label = getattr(review, "count_label", None)
        sync_review_controls = getattr(review, "_sync_controls", None)

        def sync_review_label() -> None:
            if isinstance(count_label, QLabel):
                _sync_full_text_label(count_label, "Temporary Pick count")

        if (
            review is not None
            and isinstance(count_label, QLabel)
            and callable(sync_review_controls)
            and not bool(count_label.property("betaFullTextAccessibility"))
        ):
            count_label.setProperty("betaFullTextAccessibility", True)
            original_sync = OwnerCallback(sync_review_controls)

            def sync_with_accessibility(_controller: Any) -> None:
                original_sync()
                sync_review_label()

            review._sync_controls = WeakOwnerHook(review, sync_with_accessibility)
        sync_review_label()

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

        contributed = getattr(self.window, "_contributed_docks", ())
        for dock in tuple(contributed):
            if isinstance(dock, QDockWidget) and dock is not plots:
                self._dock_controllers.append(_WorkspaceDockTopLevelController(dock))

    def quiesce_pending_callbacks(self) -> None:
        """Quiesce every managed dock's queued native-window adjustment."""

        for controller in self._dock_controllers:
            controller.quiesce_pending_callbacks()


def install_beta_workspace_hardening(window: QMainWindow) -> BetaWorkspaceHardeningController:
    """Install Beta layout/window hardening once on the production main window."""

    existing = window.__dict__.get("beta_workspace_hardening_controller")
    if isinstance(existing, BetaWorkspaceHardeningController):
        return existing
    controller = BetaWorkspaceHardeningController(window)
    window.__dict__["beta_workspace_hardening_controller"] = controller
    return controller
