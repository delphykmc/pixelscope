"""Extension-owned lifecycle for the IQA floating Hotspot Candidates dock.

Avoid relying on MAIN's internal Beta workspace controller. Qt owns all native
dock topology; this class only keeps the IQA title and transient parent stable.
"""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QObject, QTimer
from PySide6.QtGui import QWindow
from PySide6.QtWidgets import QDockWidget

from pixelscope.ui.plots_dock_title import PlotsDockTitleBar


class IqaDockLifecycle(QObject):
    """Bounded Qt-public floating/docked transitions for an IQA-owned dock."""

    def __init__(self, dock: QDockWidget, *, title_bar: PlotsDockTitleBar) -> None:
        super().__init__(dock)
        self._dock = dock
        self._title_bar = title_bar
        self._quiescing = False
        self._normalizing = False
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
            self._normalize_timer.start(0)
        else:
            self._normalize_timer.stop()
            self._detach_timer.stop()
            self._restore_docked_title_bar()

    def _visibility_changed(self, visible: bool) -> None:
        if not self._quiescing and visible and self._dock.isFloating():
            self._normalize_timer.start(0)

    def _normalize_floating(self) -> None:
        if self._quiescing or self._normalizing or not self._dock.isFloating():
            return
        self._normalizing = True
        try:
            if self._dock.titleBarWidget() is not self._title_bar:
                self._dock.setTitleBarWidget(self._title_bar)
                self._title_bar.show()
            self._title_bar.sync(True)
            # Do not change QDockWidget window flags or native HWND styles:
            # Qt is responsible for the actual drag/float/docking transition.
            if not self._dock.isHidden():
                self._detach_timer.start(0)
        finally:
            self._normalizing = False

    def _detach_transient_parent(self) -> None:
        if self._quiescing or self._dock.isHidden() or not self._dock.isFloating():
            return
        handle = self._dock.windowHandle()
        if handle is not None and handle.transientParent() is not None:
            # Qt accepts a null transient parent; the PySide stub does not.
            handle.setTransientParent(cast(QWindow, None))

    def _restore_docked_title_bar(self) -> None:
        if self._dock.isFloating():
            return
        if self._dock.titleBarWidget() is not self._title_bar:
            self._dock.setTitleBarWidget(self._title_bar)
            self._title_bar.show()
        self._title_bar.sync(False)

    def quiesce_pending_callbacks(self) -> None:
        """Prevent queued native-window work during analysis shutdown."""
        if self._quiescing:
            return
        self._quiescing = True
        self._normalize_timer.stop()
        self._detach_timer.stop()
