"""Issue #156 U5: use public Qt for Enterprise IQA floating dock ownership."""

from __future__ import annotations

import ast
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QDockWidget, QLabel, QMainWindow

from pixelscope.ui.plots_dock_title import PlotsDockTitleBar
from pixelscope_enterprise.iqa.dock_lifecycle import IqaDockLifecycle

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_iqa_analysis_no_longer_imports_main_private_beta_controller() -> None:
    path = REPO_ROOT / "src" / "pixelscope_enterprise" / "iqa" / "analysis_window.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules = {item.module for item in ast.walk(tree) if isinstance(item, ast.ImportFrom)}
    assert "pixelscope.ui.beta_workspace_hardening" not in modules
    assert "pixelscope_enterprise.iqa.dock_lifecycle" in modules


def test_iqa_dock_public_qt_float_dock_and_quiesce(qtbot: object) -> None:
    """One bounded native Qt cycle, not the unrelated MAIN workspace tests."""
    window = QMainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    dock = QDockWidget("IQA Test", window)
    dock.setFeatures(
        QDockWidget.DockWidgetFeature.DockWidgetMovable
        | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        | QDockWidget.DockWidgetFeature.DockWidgetClosable
    )
    dock.setWidget(QLabel("Synthetic candidates"))
    title = PlotsDockTitleBar(
        dock,
        title="IQA Test",
        geometry_setting="ui/tests_issue156_iqa_dock_geometry",
    )
    dock.setTitleBarWidget(title)
    controller = IqaDockLifecycle(dock, title_bar=title)
    assert controller.parent() is dock
    normalized = QSignalSpy(controller._normalize_timer.timeout)
    detached = QSignalSpy(controller._detach_timer.timeout)
    window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
    window.show()
    qtbot.waitUntil(dock.isVisible, timeout=4000)  # type: ignore[attr-defined]

    # isFloating() updates synchronously; signal spies prove both deferred
    # callbacks actually execute with the native event loop running.
    dock.setFloating(True)
    qtbot.waitUntil(dock.isFloating, timeout=4000)  # type: ignore[attr-defined]
    qtbot.waitUntil(lambda: normalized.count() >= 1, timeout=4000)  # type: ignore[attr-defined]
    qtbot.waitUntil(lambda: detached.count() >= 1, timeout=4000)  # type: ignore[attr-defined]
    assert dock.titleBarWidget() is title

    # Explicitly exercise the non-null transient-parent cleanup branch.
    floating_handle = dock.windowHandle()
    host_handle = window.windowHandle()
    assert floating_handle is not None and host_handle is not None
    floating_handle.setTransientParent(host_handle)
    assert floating_handle.transientParent() is not None
    detach_count = detached.count()
    controller._normalize_timer.start(0)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: detached.count() > detach_count, timeout=4000
    )
    assert floating_handle.transientParent() is None

    dock.setFloating(False)
    qtbot.waitUntil(lambda: not dock.isFloating(), timeout=4000)  # type: ignore[attr-defined]
    assert dock.titleBarWidget() is title
    dock.setFloating(True)
    qtbot.waitUntil(dock.isFloating, timeout=4000)  # type: ignore[attr-defined]
    qtbot.waitUntil(lambda: normalized.count() >= 3, timeout=4000)  # type: ignore[attr-defined]
    assert dock.isFloating()

    # Quiesce while still floating, with both callbacks deliberately pending.
    controller._normalize_timer.start(100)
    controller._detach_timer.start(100)
    counts = normalized.count(), detached.count()
    assert controller._normalize_timer.isActive()
    assert controller._detach_timer.isActive()
    controller.quiesce_pending_callbacks()
    controller.quiesce_pending_callbacks()  # idempotent shutdown
    assert not controller._normalize_timer.isActive()
    assert not controller._detach_timer.isActive()
    qtbot.wait(130)  # type: ignore[attr-defined]
    assert (normalized.count(), detached.count()) == counts
    window.close()
