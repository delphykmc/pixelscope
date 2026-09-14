from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Any

from PySide6.QtCore import QRect, QTimer
from PySide6.QtGui import QGuiApplication, QScreen

from pixelscope.ui.plots_dock_title import PlotsDockTitleBar

_DIAGNOSTIC_PATH = (
    Path(tempfile.gettempdir()) / f"pixelscope_multimonitor_diagnostic_{os.getpid()}.jsonl"
)
_ORIGINAL_TOGGLE_MAXIMIZED = PlotsDockTitleBar._toggle_maximized


def _rect_payload(rect: QRect) -> dict[str, int]:
    return {
        "x": rect.x(),
        "y": rect.y(),
        "width": rect.width(),
        "height": rect.height(),
        "left": rect.left(),
        "top": rect.top(),
        "right": rect.right(),
        "bottom": rect.bottom(),
    }


def _screen_payload(screen: QScreen | None) -> dict[str, Any] | None:
    if screen is None:
        return None
    return {
        "name": screen.name(),
        "geometry": _rect_payload(screen.geometry()),
        "available_geometry": _rect_payload(screen.availableGeometry()),
        "virtual_geometry": _rect_payload(screen.virtualGeometry()),
        "device_pixel_ratio": screen.devicePixelRatio(),
        "logical_dpi_x": screen.logicalDotsPerInchX(),
        "logical_dpi_y": screen.logicalDotsPerInchY(),
        "physical_dpi_x": screen.physicalDotsPerInchX(),
        "physical_dpi_y": screen.physicalDotsPerInchY(),
    }


def _screen_name(screen: QScreen | None) -> str | None:
    return screen.name() if screen is not None else None


def _write_snapshot(title_bar: PlotsDockTitleBar, phase: str) -> None:
    try:
        dock = title_bar._dock
        frame_geometry = dock.frameGeometry()
        handle = dock.windowHandle()
        handle_screen = handle.screen() if handle is not None else None
        transient_parent = handle.transientParent() if handle is not None else None
        center_screen = QGuiApplication.screenAt(frame_geometry.center())
        widget_screen = dock.screen()
        main_window = title_bar._main_window()
        main_screen = main_window.screen() if main_window is not None else None

        payload: dict[str, Any] = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "pid": os.getpid(),
            "phase": phase,
            "panel_title": title_bar._panel_title,
            "dock_object_name": dock.objectName(),
            "dock_floating": dock.isFloating(),
            "dock_maximized": dock.isMaximized(),
            "dock_full_screen": dock.isFullScreen(),
            "dock_visible": dock.isVisible(),
            "dock_geometry": _rect_payload(dock.geometry()),
            "dock_frame_geometry": _rect_payload(frame_geometry),
            "dock_normal_geometry": _rect_payload(dock.normalGeometry()),
            "widget_screen": _screen_name(widget_screen),
            "window_handle_screen": _screen_name(handle_screen),
            "screen_at_frame_center": _screen_name(center_screen),
            "primary_screen": _screen_name(QGuiApplication.primaryScreen()),
            "transient_parent_present": transient_parent is not None,
            "transient_parent_screen": (
                _screen_name(transient_parent.screen()) if transient_parent is not None else None
            ),
            "window_handle_geometry": (
                _rect_payload(handle.geometry()) if handle is not None else None
            ),
            "window_handle_state": str(handle.windowStates()) if handle is not None else None,
            "main_window_geometry": (
                _rect_payload(main_window.frameGeometry()) if main_window is not None else None
            ),
            "main_window_screen": _screen_name(main_screen),
            "screens": [_screen_payload(screen) for screen in QGuiApplication.screens()],
        }

        with _DIAGNOSTIC_PATH.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            stream.write("\n")

        print(
            "[PixelScope multi-monitor diagnostic] "
            f"{phase}: widget={payload['widget_screen']}, "
            f"handle={payload['window_handle_screen']}, "
            f"center={payload['screen_at_frame_center']}, "
            f"frame={payload['dock_frame_geometry']}",
            flush=True,
        )
    except (OSError, RuntimeError) as exc:
        print(f"[PixelScope multi-monitor diagnostic] snapshot failed: {exc}", flush=True)


def _diagnostic_toggle_maximized(title_bar: PlotsDockTitleBar) -> None:
    action = "restore" if title_bar._dock.isMaximized() else "maximize"
    _write_snapshot(title_bar, f"before-{action}")
    _ORIGINAL_TOGGLE_MAXIMIZED(title_bar)
    _write_snapshot(title_bar, f"after-{action}-immediate")
    QTimer.singleShot(
        0,
        partial(_write_snapshot, title_bar, f"after-{action}-event-loop"),
    )
    QTimer.singleShot(
        250,
        partial(_write_snapshot, title_bar, f"after-{action}-250ms"),
    )


def main() -> int:
    PlotsDockTitleBar._toggle_maximized = _diagnostic_toggle_maximized
    print(
        "[PixelScope multi-monitor diagnostic] " f"log file: {_DIAGNOSTIC_PATH}",
        flush=True,
    )
    from pixelscope.app.application import main as application_main

    return application_main()


if __name__ == "__main__":
    raise SystemExit(main())
