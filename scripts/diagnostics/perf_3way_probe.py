"""Non-invasive, version-agnostic GUI call-timing probe for the 3-way test.

Run ONLY from perf_3way.ps1.  This file stays on a diagnostics branch;
the measured worktrees are pinned, unmodified historic source trees.

Measurements are Python method wall times, NOT monitor scanout latency.
A small amount of instrumentation overhead is unavoidable.
"""

from __future__ import annotations

import atexit
import functools
import importlib
import os
from pathlib import Path
import statistics
import sys
import time
from collections import defaultdict
from typing import Any, Callable

_TIMES: dict[str, list[float]] = defaultdict(list)
_MIN_MS = float(os.environ.get("PIXELSCOPE_DIAG_MIN_MS", "5"))
_STAGE = os.environ.get("PIXELSCOPE_DIAG_STAGE", "unknown")


def _line(message: str) -> None:
    print(f"[perf-3way:{_STAGE}] {message}", flush=True)


def _wrap(qualified_module: str, class_name: str, method_name: str) -> None:
    try:
        module = importlib.import_module(qualified_module)
        owner = getattr(module, class_name)
        original = getattr(owner, method_name)
    except (AttributeError, ImportError, ModuleNotFoundError):
        return
    if not callable(original):
        return
    key = f"{class_name}.{method_name}"

    @functools.wraps(original)
    def timed(self: Any, *args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter_ns()
        try:
            return original(self, *args, **kwargs)
        finally:
            milliseconds = (time.perf_counter_ns() - start) / 1_000_000.0
            _TIMES[key].append(milliseconds)
            if milliseconds >= _MIN_MS:
                _line(f"CALL {key} {milliseconds:.3f}ms")

    setattr(owner, method_name, timed)


def _summary() -> None:
    _line("SUMMARY: Python call durations; nested call times overlap")
    for name, observations in sorted(_TIMES.items()):
        values = sorted(observations)
        count = len(values)
        median = statistics.median(values)
        p95 = values[min(count - 1, int((count - 1) * 0.95 + 0.999999))]
        total = sum(values)
        _line(
            f"SUMMARY {name} n={count} p50={median:.3f}ms"
            f" p95={p95:.3f}ms max={values[-1]:.3f}ms total={total:.1f}ms"
        )


def _install_measurements() -> None:
    targets: dict[tuple[str, str], tuple[str, ...]] = {
        ("pixelscope.app.main_window", "MainWindow"): (
            "_selection_changed",
            "_select_document_ids",
            "_render_selection",
            "_update_file_states",
            "_apply_folder_navigation",
            "_handle_dropped_paths",
            "_start_load",
            "_load_succeeded",
            "_set_difference_visible",
        ),
        ("pixelscope.app.registration_controller", "RegistrationController"): (
            "enqueue",
            "_register_chunk",
            "_finish_registration",
        ),
        ("pixelscope.ui.multi_compare_view", "MultiCompareView"): (
            "set_documents",
            "set_capacity",
            "set_layout_kind",
            "_arrange_viewers",
            "fit_images",
        ),
        ("pixelscope.ui.image_viewer", "ImageViewer"): (
            "set_document",
            "_upload_preview",
            "_ensure_display_preview",
            "_display_preview_succeeded",
            "_notify_first_frame_painted",
        ),
        ("pixelscope.ui.comparison_analysis_panel", "ComparisonAnalysisPanel"): (
            "set_documents",
            "_render",
        ),
        ("pixelscope.ui.difference_panel", "DifferencePanel"): (
            "set_documents",
            "calculate_difference",
            "cached_display_for_current",
            "_on_result",
        ),
        ("pixelscope.ui.quick_compare", "QuickCompareController"): (
            "_apply_registered_drop",
            "_schedule_difference",
            "_try_pending_difference",
        ),
        ("pixelscope.ui.display_gain", "DisplayGainState"): ("set_gain",),
    }
    for (module, cls), method_names in targets.items():
        for name in method_names:
            _wrap(module, cls, name)


def main() -> int:
    expected_source = Path(os.environ["PIXELSCOPE_DIAG_SRC"]).resolve()
    settings_dir = Path(os.environ["PIXELSCOPE_DIAG_SETTINGS"]).resolve()
    settings_dir.mkdir(parents=True, exist_ok=True)

    # Avoid reading or overwriting the existing installed/internal PixelScope
    # registry-backed QSettings. Use per-revision temporary INI storage.
    from PySide6.QtCore import QSettings

    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str(settings_dir),
    )

    import pixelscope

    imported_root = Path(pixelscope.__file__).resolve().parent
    if imported_root != expected_source / "pixelscope":
        raise RuntimeError(
            "Wrong PixelScope imported. "
            f"Expected {expected_source / 'pixelscope'}, got {imported_root}"
        )
    _line(f"SOURCE {imported_root}")
    _line(f"PYTHON {sys.executable}")
    _line(f"SETTINGS {settings_dir}")
    _line("Use the exact same files, window/plots/layout and interaction sequence each run.")

    if os.environ.get("PIXELSCOPE_DIAG_NO_PROBE") != "1":
        _install_measurements()
        atexit.register(_summary)
    else:
        _line("Timing wrappers disabled (-NoProbe)")

    # Delay this import until after the per-version patch installation.  Qt
    # signals and QuickCompare composition bind class methods during startup.
    from pixelscope.app.application import main as app_main

    return int(app_main())


if __name__ == "__main__":
    raise SystemExit(main())
