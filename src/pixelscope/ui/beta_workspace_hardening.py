from __future__ import annotations

from types import MethodType
from typing import Any, cast

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, QTimer
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

from pixelscope.ui.design_tokens import (
    TOKENS,
    WORKSPACE_CHROME_HEIGHT,
    panel_heading_style,
)
from pixelscope.ui.plots_dock_title import PlotsDockTitleBar

_DISABLED_ICON_COLOR = "#737980"


def _set_vertical_policy(widget: QWidget, policy: QSizePolicy.Policy) -> None:
    size_policy = widget.sizePolicy()
    size_policy.setVerticalPolicy(policy)
    widget.setSizePolicy(size_policy)


def _set_horizontal_policy(widget: QWidget, policy: QSizePolicy.Policy) -> None:
    size_policy = widget.sizePolicy()
    size_policy.setHorizontalPolicy(policy)
    widget.setSizePolicy(size_policy)


def _sync_full_text_label(label: QLabel, description: str) -> None:
    text = label.text()
    label.setToolTip(text)
    label.setAccessibleName(f"{description}: {text}")


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
                # Remove the legacy 230 px local cap so the Scene attribute list
                # can use additional width when the user intentionally enlarges IQA.
                attribute_filter.setMaximumWidth(window.maximumWidth())

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

        self._relax_composed_iqa_shell()

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

            def update_with_accessibility(_window: Any) -> None:
                update_page_controls()
                sync_page_labels()

            dynamic_window = cast(Any, window)
            dynamic_window._update_comparison_page_controls = MethodType(
                update_with_accessibility,
                window,
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

            def sync_with_accessibility(_controller: Any) -> None:
                sync_review_controls()
                sync_review_label()

            review._sync_controls = MethodType(sync_with_accessibility, review)
        sync_review_label()

    def _relax_composed_iqa_shell(self) -> None:
        """Relax the final P5-C shell as well as the nested P5-B Results widget."""

        remote_workspace = getattr(self.window, "remote_iqa_workspace", None)
        if not isinstance(remote_workspace, QWidget):
            return

        remote_workspace.setMinimumWidth(0)
        remote_workspace.setMinimumHeight(0)
        _set_horizontal_policy(remote_workspace, QSizePolicy.Policy.Ignored)
        _set_vertical_policy(remote_workspace, QSizePolicy.Policy.Ignored)

        tabs = getattr(remote_workspace, "tabs", None)
        if isinstance(tabs, QTabWidget):
            tabs.setMinimumWidth(0)
            tabs.setMinimumHeight(0)
            _set_horizontal_policy(tabs, QSizePolicy.Policy.Ignored)
            _set_vertical_policy(tabs, QSizePolicy.Policy.Ignored)
            for index in range(tabs.count()):
                page = tabs.widget(index)
                if isinstance(page, QWidget):
                    page.setMinimumWidth(0)
                    page.setMinimumHeight(0)
                    _set_horizontal_policy(page, QSizePolicy.Policy.Ignored)
                    _set_vertical_policy(page, QSizePolicy.Policy.Ignored)

        for label in remote_workspace.findChildren(QLabel):
            label.setMinimumWidth(0)
            label.setWordWrap(True)
            if label.text() and not label.toolTip():
                label.setToolTip(label.text())
            if label.text() and not label.accessibleName():
                label.setAccessibleName(label.text())

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
