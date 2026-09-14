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
_SCREEN_MAP_PRINTED = False


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


def _rect_short(rect: QRect) -> str:
    return f"{rect.x()},{rect.y()},{rect.width()}x{rect.height()}"


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


def _screen_id(screen: QScreen | None) -> str:
    if screen is None:
        return "NONE"
    screens = QGuiApplication.screens()
    try:
        return f"S{screens.index(screen)}"
    except ValueError:
        return "OTHER"


def _print_screen_map_once() -> None:
    global _SCREEN_MAP_PRINTED
    if _SCREEN_MAP_PRINTED:
        return
    _SCREEN_MAP_PRINTED = True
    primary = QGuiApplication.primaryScreen()
    print("=== TYPE ONLY THESE SCREEN/RESULT LINES BACK TO CHATGPT ===", flush=True)
    for index, screen in enumerate(QGuiApplication.screens()):
        primary_marker = " PRIMARY" if screen is primary else ""
        print(
            f"SCREEN S{index}{primary_marker} "
            f"geo={_rect_short(screen.geometry())} "
            f"avail={_rect_short(screen.availableGeometry())} "
            f"dpr={screen.devicePixelRatio():.2f} "
            f"dpi={screen.logicalDotsPerInch():.1f}",
            flush=True,
        )


def _collect_snapshot(title_bar: PlotsDockTitleBar, phase: str) -> dict[str, Any]:
    dock = title_bar._dock
    frame_geometry = dock.frameGeometry()
    handle = dock.windowHandle()
    handle_screen = handle.screen() if handle is not None else None
    transient_parent = handle.transientParent() if handle is not None else None
    center_screen = QGuiApplication.screenAt(frame_geometry.center())
    widget_screen = dock.screen()
    main_window = title_bar._main_window()
    main_screen = main_window.screen() if main_window is not None else None

    return {
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
        "widget_screen_id": _screen_id(widget_screen),
        "window_handle_screen": _screen_name(handle_screen),
        "window_handle_screen_id": _screen_id(handle_screen),
        "screen_at_frame_center": _screen_name(center_screen),
        "screen_at_frame_center_id": _screen_id(center_screen),
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
        "main_window_screen_id": _screen_id(main_screen),
        "screens": [_screen_payload(screen) for screen in QGuiApplication.screens()],
    }


def _write_payload(payload: dict[str, Any]) -> None:
    with _DIAGNOSTIC_PATH.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        stream.write("\n")


def _write_snapshot(title_bar: PlotsDockTitleBar, phase: str) -> dict[str, Any] | None:
    try:
        _print_screen_map_once()
        payload = _collect_snapshot(title_bar, phase)
        _write_payload(payload)
        return payload
    except (OSError, RuntimeError) as exc:
        print(f"DIAGNOSTIC-ERROR {exc}", flush=True)
        return None


def _payload_rect(payload: dict[str, Any], key: str) -> QRect:
    value = payload[key]
    return QRect(value["x"], value["y"], value["width"], value["height"])


def _screen_by_id(screen_id: str) -> QScreen | None:
    if not screen_id.startswith("S"):
        return None
    try:
        index = int(screen_id[1:])
    except ValueError:
        return None
    screens = QGuiApplication.screens()
    return screens[index] if 0 <= index < len(screens) else None


def _print_result(
    title_bar: PlotsDockTitleBar,
    action: str,
    target_screen_id: str,
    phase: str,
) -> None:
    payload = _write_snapshot(title_bar, phase)
    if payload is None:
        return

    frame = _payload_rect(payload, "dock_frame_geometry")
    target_screen = _screen_by_id(target_screen_id)
    available = target_screen.availableGeometry() if target_screen is not None else QRect()
    dx = frame.x() - available.x()
    dy = frame.y() - available.y()
    dw = frame.width() - available.width()
    dh = frame.height() - available.height()

    print(
        f"RESULT {payload['panel_title']} {action.upper()} "
        f"target={target_screen_id} "
        f"widget={payload['widget_screen_id']} "
        f"handle={payload['window_handle_screen_id']} "
        f"center={payload['screen_at_frame_center_id']} "
        f"avail={_rect_short(available)} "
        f"frame={_rect_short(frame)} "
        f"delta={dx},{dy},{dw},{dh} "
        f"max={int(bool(payload['dock_maximized']))}",
        flush=True,
    )


def _diagnostic_toggle_maximized(title_bar: PlotsDockTitleBar) -> None:
    action = "restore" if title_bar._dock.isMaximized() else "maximize"
    before = _write_snapshot(title_bar, f"before-{action}")
    target_screen_id = (
        before["screen_at_frame_center_id"] if before is not None else "NONE"
    )

    _ORIGINAL_TOGGLE_MAXIMIZED(title_bar)
    _write_snapshot(title_bar, f"after-{action}-immediate")
    QTimer.singleShot(
        0,
        partial(_write_snapshot, title_bar, f"after-{action}-event-loop"),
    )
    QTimer.singleShot(
        250,
        partial(
            _print_result,
            title_bar,
            action,
            target_screen_id,
            f"after-{action}-250ms",
        ),
    )


def main() -> int:
    PlotsDockTitleBar._toggle_maximized = _diagnostic_toggle_maximized
    print(
        "[PixelScope multi-monitor diagnostic] " f"full log: {_DIAGNOSTIC_PATH}",
        flush=True,
    )
    print(
        "Run Plots and IQA maximize/restore on primary and secondary. "
        "You only need to type the SCREEN and RESULT lines back to ChatGPT.",
        flush=True,
    )
    from pixelscope.app.application import main as application_main

    return application_main()


if __name__ == "__main__":
    raise SystemExit(main())
