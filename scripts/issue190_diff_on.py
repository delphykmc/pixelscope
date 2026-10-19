"""D1 paired first-Diff-ON preview MISS/HIT diagnosis; no production changes."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts.issue190_user_path import Recorder, make_fixtures, textured  # noqa: E402


def memory() -> dict:
    """Untimed Windows process snapshot, not allocation attribution."""
    import ctypes
    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
            (name, ctypes.c_size_t)
            for name in (
                "PeakWorkingSetSize",
                "WorkingSetSize",
                "QuotaPeakPagedPoolUsage",
                "QuotaPagedPoolUsage",
                "QuotaPeakNonPagedPoolUsage",
                "QuotaNonPagedPoolUsage",
                "PagefileUsage",
                "PeakPagefileUsage",
                "PrivateUsage",
            )
        ]

    process = ctypes.windll.kernel32.GetCurrentProcess
    process.restype = wintypes.HANDLE
    get = ctypes.windll.psapi.GetProcessMemoryInfo
    get.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    values = Counters()
    values.cb = ctypes.sizeof(values)
    if not get(process(), ctypes.byref(values), values.cb):
        raise OSError("process memory snapshot unavailable")
    return {
        "RSS_bytes": values.WorkingSetSize,
        "private_bytes": values.PrivateUsage,
        "lifetime_peak_RSS_bytes": values.PeakWorkingSetSize,
    }


def durations(events: list[dict], phase: str) -> dict:
    rows = [e for e in events if e["intent_id"] == phase]
    result = {}
    names = {e["stage"][:-6] for e in rows if e["stage"].endswith("_begin")}
    for name in names:
        starts = [e["ns"] for e in rows if e["stage"] == name + "_begin"]
        ends = [e["ns"] for e in rows if e["stage"] == name + "_end"]
        if len(starts) != len(ends):
            raise ValueError("unbalanced trace")
        result[name + "_ms"] = sum(b - a for a, b in zip(starts, ends, strict=True)) / 1e6
        result[name + "_calls"] = len(starts)
    return result


def child(fixtures: Path) -> dict:
    import numpy as np
    from PySide6.QtCore import QCoreApplication, QEvent, QSettings, QTimer
    from PySide6.QtTest import QTest

    from pixelscope.app import main_window as main
    from pixelscope.app.bootstrap import compose_main_window_presentation, create_application
    from pixelscope.ui import difference_curation_lifecycle as lifecycle_module
    from pixelscope.ui import difference_panel as module

    assert gc.isenabled()
    trace = Recorder()
    panel_type, numerical = main.DifferencePanel, module.render_absolute_difference
    lifecycle_type = lifecycle_module.DifferenceCurationLifecycle
    gui_thread = threading.get_ident()

    def mark(stage, **fields):
        trace.add(stage, gui_thread=threading.get_ident() == gui_thread, **fields)

    def render_absolute(*args, **kwargs):
        mark("absolute_begin")
        try:
            return numerical(*args, **kwargs)
        finally:
            mark("absolute_end")

    class Panel(panel_type):
        def cached_display_for_current(self):
            mark("cached_display_begin", map_hit=self.has_cached_map())
            try:
                return super().cached_display_for_current()
            finally:
                mark("cached_display_end")

        def _cached_preview(self, difference_map, selected):
            hit = self._preview_cache_key(difference_map) == self._preview_key
            mark("cached_preview_begin", preview_hit=hit and self._preview_value is not None)
            try:
                return super()._cached_preview(difference_map, selected)
            finally:
                mark("cached_preview_end")

    class Lifecycle(lifecycle_type):
        def _set_difference_visible(self, enabled):
            mark("handler_begin", enabled=enabled)
            try:
                return super()._set_difference_visible(enabled)
            finally:
                mark("handler_end")

        def _render_selection(self, *args, **kwargs):
            mark("selection_dispatch_begin")
            try:
                return super()._render_selection(*args, **kwargs)
            finally:
                mark("selection_dispatch_end")

    class Window(main.MainWindow):
        def _store_difference_document(self, *args, **kwargs):
            mark("store_begin")
            try:
                return super()._store_difference_document(*args, **kwargs)
            finally:
                mark("store_end")

        def _render_selection(self, *args, **kwargs):
            mark("selection_render_begin")
            try:
                return super()._render_selection(*args, **kwargs)
            finally:
                mark("selection_render_end")

    app = create_application(["issue190-D1"])
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(Path.cwd() / "settings")
    )
    QSettings().clear()
    heartbeat = []
    timer = QTimer()
    timer.setInterval(10)
    timer.timeout.connect(lambda: heartbeat.append(time.perf_counter_ns()))
    window = None

    def wait(predicate, seconds=25):
        deadline = time.perf_counter() + seconds
        while not predicate():
            if time.perf_counter() >= deadline:
                raise TimeoutError("bounded D1 condition")
            app.processEvents()
            QTest.qWait(1)

    try:
        main.DifferencePanel, module.render_absolute_difference = Panel, render_absolute
        lifecycle_module.DifferenceCurationLifecycle = Lifecycle
        window = Window()
        compose_main_window_presentation(window)
        window.resize(1200, 800)
        window.setWindowTitle("PixelScope #190 D1 first Diff ON")
        window.show()
        window.open_image_paths([fixtures / "A.png"])
        panel = window.difference_panel
        analysis = window.comparison_analysis_panel

        def idle():
            return (
                not window._workers
                and panel._worker is None
                and panel._preview_worker is None
                and analysis._worker is None
                and not analysis._refresh_timer.isActive()
                and window.large_folder_registration_controller.is_idle
            )

        wait(
            lambda: len(window.selected_documents) == 1
            and idle()
            and window.selected_documents[0].source is not None
        )
        assert window.quick_compare_controller.handle_image_drop([fixtures / "B.png"])
        wait(lambda: len(window.selected_documents) == 2 and panel.has_cached_map() and idle())
        assert not window.diff_action.isChecked() and window._difference_document is None
        assert panel._preview_value is None, "cold preview must not be pre-rendered"
        documents = list(window.selected_documents)
        source_identity = [(d, d.source, d.preview, d.generation) for d in documents]
        difference_map = panel.cached_result_for_current()
        assert difference_map is not None
        assert panel._metric_key() in panel._metric_cache
        expected = [textured(1901), textured(1902)]
        for document, pixels in zip(documents, expected, strict=True):
            assert np.array_equal(document.source, pixels)
            assert np.array_equal(document.preview, pixels)
        absolute = np.abs(expected[0].astype(np.int16) - expected[1].astype(np.int16)).astype(
            np.uint8
        )
        assert np.array_equal(difference_map.absolute, absolute)

        def controls():
            return (
                panel.channel.currentText(),
                panel.mode.currentText(),
                panel.gain.value(),
                panel.region.currentText(),
                panel.threshold.value(),
                panel._active_roi,
                window._shared_roi,
            )

        controls_before = controls()
        key = panel._preview_cache_key(difference_map)
        timer.start()
        phases = {}
        first_preview = None
        for phase in ("cold", "warm"):
            wait(idle)
            before = memory()
            QTest.qWait(15)
            wait(lambda: bool(heartbeat), seconds=2)  # Untimed first-tick availability gate.
            tick = heartbeat[-1]
            count = len(heartbeat)
            trace.active = True
            trace.action(phase)
            mark(
                "activation_cache_state",
                map_hit=panel.has_cached_map(),
                preview_hit=panel._preview_key == key and panel._preview_value is not None,
                existing_document=window._difference_document is not None,
            )
            mark("action_begin")
            window.diff_action.trigger()
            mark("action_end")
            trace.active = False
            wait(lambda count=count: len(heartbeat) > count, seconds=2)
            first_tick = heartbeat[count]
            trace.active = False
            after = memory()
            assert window.diff_action.isChecked()
            assert panel._preview_key == key and controls() == controls_before
            assert panel.cached_result_for_current() is difference_map
            assert window.selected_documents == documents
            for doc, source, preview, generation in source_identity:
                assert (
                    doc.source is source and doc.preview is preview and doc.generation == generation
                )
            if phase == "cold":
                first_preview = panel._preview_value
            else:
                assert panel._preview_value is first_preview
            phases[phase] = {
                "metrics": durations(trace.events, phase),
                "first_heartbeat_gap_ms": (first_tick - tick) / 1e6,
                "memory_before": before,
                "memory_after": after,
            }
            wait(idle)
            if phase == "cold":
                window.diff_action.trigger()  # OFF outside both measured ON actions.
                wait(idle)
                assert not window.diff_action.isChecked() and panel._preview_value is first_preview
        trace.active = True
        trace.action("warm_cache_probe")
        mark("probe_begin")
        cached = panel.cached_display_for_current()
        mark("probe_end")
        trace.active = False
        assert cached is not None and cached[2] is first_preview
        assert not any(
            e["stage"] == "absolute_begin"
            for e in trace.events
            if e["intent_id"] == "warm_cache_probe"
        )
        assert all(
            e["preview_hit"]
            for e in trace.events
            if e["intent_id"] == "warm_cache_probe" and e["stage"] == "cached_preview_begin"
        )
        phases["warm_cache_probe"] = {"metrics": durations(trace.events, "warm_cache_probe")}
        timer.stop()
        assert np.array_equal(first_preview, numerical(absolute, float(panel.gain.value())))
        assert np.array_equal(window._difference_document.preview, first_preview)
        assert np.array_equal(window._difference_document.source, absolute)
        assert window._normal_load_stale_drop_count == 0
        assert window.large_folder_registration_controller.stale_result_count == 0
        cold = [e for e in trace.events if e["intent_id"] == "cold"]
        warm = [e for e in trace.events if e["intent_id"] == "warm"]
        assert next(e for e in cold if e["stage"] == "cached_preview_begin")["preview_hit"] is False
        assert all(e["preview_hit"] for e in warm if e["stage"] == "cached_preview_begin")
        assert phases["cold"]["metrics"]["absolute_calls"] == 1
        assert phases["cold"]["metrics"]["handler_calls"] == 1
        assert phases["warm"]["metrics"]["handler_calls"] == 1
        assert not any(e["stage"] == "absolute_begin" for e in warm)
        assert all(e["gui_thread"] for e in trace.events if "gui_thread" in e)
        assert trace.dropped == 0 and gc.isenabled()
        origin = trace.events[0]["ns"]
        for event in trace.events:
            event["ns"] -= origin
        return {
            "status": "ok",
            "phases": phases,
            "events": trace.events,
            "checks": [
                "same_pair_source_preview_generation",
                "same_preview_key_controls_ROI",
                "passive_map_hit_both",
                "cold_preview_miss_once",
                "warm_preview_hit_reuses_array",
                "exact_source_preview_Diff_pixels",
                "no_stale_publish",
                "GUI_thread",
                "normal_GC",
            ],
            "paint": "INCONCLUSIVE; no postpaint oracle",
            "trace_dropped": trace.dropped,
        }
    finally:
        trace.active = False
        timer.stop()
        if sys.exc_info()[0] is not None:
            (Path.cwd() / "failure_trace.json").write_text(
                json.dumps({"events": trace.events, "trace_dropped": trace.dropped}),
                encoding="utf-8",
            )
        try:
            if window is not None:
                window.close()
                wait(
                    lambda: window._load_pool.activeThreadCount() == 0
                    and window.large_folder_registration_controller.pool.activeThreadCount() == 0
                )
                app.processEvents()
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        finally:
            main.DifferencePanel, module.render_absolute_difference = panel_type, numerical
            lifecycle_module.DifferenceCurationLifecycle = lifecycle_type


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--fixtures", type=Path)
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--repeats", type=int, default=8)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if args.child:
        try:
            result = child(args.fixtures.resolve())
        except Exception as error:
            import traceback

            traceback.print_exc()
            result = {"status": "fail", "error_type": type(error).__name__}
            if (output / "failure_trace.json").exists():
                result.update(json.loads((output / "failure_trace.json").read_text()))
        (output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        return 0 if result["status"] == "ok" else 1
    manifest = make_fixtures(output / "fixtures")
    samples = []
    for index in range(args.warmups + args.repeats):
        folder = output / f"pair-{index:02d}"
        folder.mkdir()
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--child",
            "--output",
            str(folder),
            "--fixtures",
            str(output / "fixtures"),
        ]
        try:
            process = subprocess.run(command, cwd=folder, capture_output=True, timeout=90)
            (folder / "stderr.log").write_bytes(process.stderr)
            result = json.loads((folder / "result.json").read_text())
            if process.returncode:
                result["status"] = "fail"
        except subprocess.TimeoutExpired:
            result = {"status": "fail", "error_type": "watchdog_timeout"}
        result.update(run_id=f"pair-{index:02d}", warmup=index < args.warmups)
        samples.append(result)
        print(result["run_id"], result["status"], flush=True)
    observed = [s for s in samples if not s["warmup"] and s["status"] == "ok"]

    def median_metric(phase, key):
        values = [
            s["phases"][phase]["metrics"][key]
            for s in observed
            if key in s["phases"][phase]["metrics"]
        ]
        return statistics.median(values) if values else None

    summary = (
        {
            phase: {
                key: median_metric(phase, key)
                for key in (
                    "action_ms",
                    "handler_ms",
                    "cached_display_ms",
                    "cached_preview_ms",
                    "absolute_ms",
                    "store_ms",
                    "selection_render_ms",
                    "selection_dispatch_ms",
                    "probe_ms",
                )
            }
            for phase in ("cold", "warm", "warm_cache_probe")
        }
        if observed
        else {}
    )
    evidence = {
        "source_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "fixtures": manifest,
        "samples": samples,
        "median_ms": summary,
        "scope": (
            "paired GUI callback study; OS cache warm/uncontrolled; "
            "no postpaint or optimization claim"
        ),
        "memory_scope": (
            "untimed process snapshots; lifetime peak RSS, " "not action allocation or peak private"
        ),
        "normal_gc": gc.isenabled(),
    }
    (output / "evidence.json").write_bytes((json.dumps(evidence, indent=2) + "\n").encode())
    print(json.dumps(summary), flush=True)
    return 1 if any(s["status"] != "ok" for s in samples) else 0


if __name__ == "__main__":
    raise SystemExit(main())
