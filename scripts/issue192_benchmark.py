"""D1 paired first-Diff-ON preview MISS/HIT diagnosis; no production changes."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(os.environ.get("ISSUE192_SOURCE_ROOT", Path(__file__).resolve().parents[1])).resolve()
sys.path[:0] = [str(ROOT), str(ROOT / "src")]


def textured(seed: int, height: int = 2160, width: int = 3840):
    import numpy as np

    rng = np.random.default_rng(seed)
    noise = rng.integers(0, 32, (height, width, 3), dtype=np.uint8)
    x = np.arange(width, dtype=np.uint16)[None, :]
    y = np.arange(height, dtype=np.uint16)[:, None]
    for c in range(3):
        texture = ((x // (3 + c) + y // (5 - c) + seed * (c + 1)) * 19) % 224
        noise[..., c] += texture.astype(np.uint8)
    marker = max(1, min(32, height // 4, width // 4))
    noise[:marker, :marker] = (255, 0, 0) if seed == 1901 else (0, 255, 255)
    noise[-marker:, -marker:] = (seed % 256, 7, 231)
    return noise


def make_fixtures(folder: Path) -> dict:
    import cv2

    folder.mkdir(parents=True, exist_ok=False)
    manifest = {}
    for alias, seed in (("A", 1901), ("B", 1902)):
        rgb = textured(seed)
        path = folder / f"{alias}.png"
        assert cv2.imwrite(
            str(path), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_PNG_COMPRESSION, 1]
        )
        encoded = path.read_bytes()
        manifest[alias] = {
            "seed": seed,
            "encoded_bytes": len(encoded),
            "decoded_bytes": int(rgb.nbytes),
            "sha256": hashlib.sha256(encoded).hexdigest(),
            "shape": list(rgb.shape),
            "dtype": "uint8",
            "channels": "RGB",
            "compression": "PNG lossless level 1",
            "decoder": "production Unicode-safe np.fromfile + OpenCV imdecode BGR-to-RGB",
            "storage": "generated real local-disk file; warm/uncontrolled OS cache",
        }
    assert manifest["A"]["sha256"] != manifest["B"]["sha256"]
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


class Recorder:
    def __init__(self, capacity: int = 4096):
        self.capacity = capacity
        self.events: list[dict] = []
        self.dropped = 0
        self.epoch = 0
        self.intent = "setup"
        self.documents: dict[str, str] = {}
        self.tokens: dict[str, int] = {}
        self.local = threading.local()
        self.lock = threading.Lock()
        self.active = False

    def action(self, name):
        self.epoch += 1
        self.intent = name
        self.add("intent_accepted")

    def add(self, stage: str, *, context=None, **fields):
        if not self.active:
            return
        if context is None:
            context = getattr(self.local, "context", None) or {
                "intent_id": self.intent,
                "selection_epoch": self.epoch,
            }
        event = {"stage": stage, "ns": time.perf_counter_ns(), **context, **fields}
        if any(
            not isinstance(value, str | int | float | bool | type(None)) for value in event.values()
        ):
            raise TypeError("observer records must be primitive")
        with self.lock:
            if len(self.events) >= self.capacity:
                self.dropped += 1
            else:
                self.events.append(event)


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
    from pixelscope.core import display_transform
    from pixelscope.ui import difference_curation_lifecycle as lifecycle_module
    from pixelscope.ui import difference_panel as module

    assert Path(display_transform.__file__).resolve().is_relative_to(ROOT / "src")
    assert gc.isenabled()
    trace = Recorder()
    panel_type, numerical = main.DifferencePanel, module.render_absolute_difference
    lifecycle_type = lifecycle_module.DifferenceCurationLifecycle
    gui_thread = threading.get_ident()

    def mark(stage, **fields):
        trace.add(stage, gui_thread=threading.get_ident() == gui_thread, **fields)

    def render_absolute(*args, **kwargs):
        mark("absolute_begin", selected_uint8=args[0].dtype == np.uint8)
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
        a_start = time.perf_counter_ns()
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
        a_ready_ms = (time.perf_counter_ns() - a_start) / 1e6
        b_start = time.perf_counter_ns()
        assert window.quick_compare_controller.handle_image_drop([fixtures / "B.png"])
        wait(
            lambda: len(window.selected_documents) == 2
            and not window._workers
            and window.large_folder_registration_controller.is_idle
            and all(d.source is not None for d in window.selected_documents)
        )
        b_ready_ms = (time.perf_counter_ns() - b_start) / 1e6
        wait(lambda: panel.has_cached_map() and idle())
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

        def geometry():
            result = {}
            for viewer in window.multi_compare_view.occupied_viewers:
                document = viewer.document
                alias = next(
                    (
                        name
                        for name, source in zip(("A", "B"), documents, strict=True)
                        if document is source
                    ),
                    "Diff",
                )
                ranges = viewer.view_box.viewRange()
                result[alias] = {
                    "center": [(low + high) / 2 for low, high in ranges],
                    "image_px_per_view_px": list(viewer.view_box.viewPixelSize()),
                    "view_size": [viewer.view_box.width(), viewer.view_box.height()],
                    "pending": viewer._pending_document is not None,
                }
            return result

        key = panel._preview_cache_key(difference_map)
        timer.start()
        phases = {}
        first_preview = None
        for phase in ("cold", "warm"):
            wait(idle)
            geometry_before = geometry()
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
            phases[phase]["geometry_before"] = geometry_before
            phases[phase]["geometry_after"] = geometry()
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
        for _ in range(5):
            window.diff_action.trigger()
            wait(idle)
            assert panel._preview_key == key and panel._preview_value is first_preview
            window.diff_action.trigger()
            wait(idle)
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
            "foreground_ready_ms": {"A": a_ready_ms, "B": b_ready_ms},
            "source_sha": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "transform_sha256": hashlib.sha256(
                Path(display_transform.__file__).read_bytes()
            ).hexdigest(),
            "desktop": {
                "qt_platform": app.platformName(),
                "visible": window.isVisible(),
                "exposed": window.windowHandle().isExposed(),
            },
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
                "five_toggle_cycles",
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
    parser.add_argument("--fixtures", required=True, type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--phase", choices=("AA", "screening", "confirmation", "smoke"))
    parser.add_argument("--child", action="store_true")
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
    fixtures = args.fixtures.resolve()
    manifest = (
        json.loads((fixtures / "manifest.json").read_text())
        if fixtures.exists()
        else make_fixtures(fixtures)
    )
    versions = (
        (("A0", args.baseline), ("A1", args.baseline))
        if args.phase == "AA"
        else (("baseline", args.baseline), ("candidate", args.candidate))
    )
    repeats = 22 if args.phase == "confirmation" else (1 if args.phase == "smoke" else 10)
    samples = []
    for repeat in range(repeats):
        for version, source in versions if repeat % 2 == 0 else tuple(reversed(versions)):
            run_id = f"{version}-{repeat:02d}"
            folder = output / run_id
            folder.mkdir(exist_ok=False)
            environment = os.environ.copy()
            environment["ISSUE192_SOURCE_ROOT"] = str(source.resolve())
            environment.pop("QT_QPA_PLATFORM", None)
            command = [
                sys.executable,
                str(Path(__file__).resolve()),
                "--child",
                "--output",
                str(folder),
                "--fixtures",
                str(fixtures),
            ]
            try:
                process = subprocess.run(
                    command, cwd=folder, env=environment, capture_output=True, timeout=90
                )
                (folder / "stderr.log").write_bytes(process.stderr)
                path = folder / "result.json"
                result = json.loads(path.read_text()) if path.exists() else {"status": "fail"}
                if process.returncode:
                    result["status"] = "fail"
            except subprocess.TimeoutExpired:
                result = {"status": "fail", "error_type": "watchdog_timeout"}
            result.update(
                run_id=run_id,
                version=version,
                repeat=repeat,
                warmup=repeat < 2 and args.phase != "smoke",
            )
            samples.append(result)
            print(args.phase, run_id, result["status"], flush=True)
            evidence = {
                "phase": args.phase,
                "fixtures": manifest,
                "samples": samples,
                "normal_gc": gc.isenabled(),
                "driver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "paint": "INCONCLUSIVE; GUI callback and readiness upper bounds only",
            }
            (output / "evidence.json").write_bytes((json.dumps(evidence, indent=2) + "\n").encode())
    return 1 if any(s["status"] != "ok" for s in samples) else 0


if __name__ == "__main__":
    raise SystemExit(main())
