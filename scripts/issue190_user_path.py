"""R1-R3 on-disk user-path v0. Exact epoch-bound post-paint is INCONCLUSIVE.

No product/Qt instance method is replaced. Test-owned subclasses and temporary
module checkpoints record primitive events; all module replacements restore in
finally after feature-owned shutdown. No disk writes from a GUI/worker observer.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import platform
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
BASE = "a9ecbf49757b0135e658cc9842722b1604c3f2f1"


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


def stage_metrics(events: list[dict]) -> dict:
    metrics = {}
    for intent in dict.fromkeys(e["intent_id"] for e in events if e["stage"] == "intent_accepted"):
        subset = [e for e in events if e["intent_id"] == intent]
        accepted = next(e["ns"] for e in subset if e["stage"] == "intent_accepted")
        for alias in ("A", "B"):
            source = [e for e in subset if e.get("source") == alias]
            lookup = {e["stage"]: e["ns"] for e in source}
            for stage in (
                "row_registered",
                "load_queued",
                "load_worker_start",
                "encoded_bytes_read",
                "opencv_decode_completed",
                "canonical_preview_ready",
                "source_gui_return_accepted",
                "legacy_first_frame_signal",
            ):
                if stage in lookup:
                    metrics[f"{intent}_{alias}_intent_to_{stage}"] = (
                        lookup[stage] - accepted
                    ) / 1e6
            for name, start, end in (
                ("file_read", "encoded_file_read_begin", "encoded_bytes_read"),
                ("decode_and_encoded_hash", "encoded_bytes_read", "opencv_decode_completed"),
                ("channel_conversion", "opencv_decode_completed", "channel_layout_converted"),
                ("preview_build", "channel_layout_converted", "canonical_preview_ready"),
                ("foreground_queue", "load_queued", "load_worker_start"),
                ("source_gui_callback", "source_gui_enter", "source_gui_return_accepted"),
                ("result_signal_to_gui", "load_result_signal", "source_gui_enter"),
            ):
                if start in lookup and end in lookup:
                    metrics[f"{intent}_{alias}_{name}"] = (lookup[end] - lookup[start]) / 1e6
        for start, end, name in (
            ("discovery_start", "discovery_return", "discovery"),
            ("diff_calculate_queued", "diff_calculate_start", "passive_diff_queue"),
            ("diff_calculate_start", "diff_calculate_return", "passive_diff_compute_and_metrics"),
            ("diff_calculate_return", "diff_cache_ready", "passive_diff_to_cache_gui"),
            ("intent_accepted", "diff_cache_ready", "intent_to_passive_diff_cache"),
            ("intent_accepted", "action_handler_return", "synchronous_action"),
            ("intent_accepted", "ready_snapshot", "intent_to_ready_snapshot_upper_bound"),
        ):
            starts = [e["ns"] for e in subset if e["stage"] == start]
            ends = [e["ns"] for e in subset if e["stage"] == end]
            if starts and ends:
                metrics[f"{intent}_{name}"] = (max(ends) - min(starts)) / 1e6
        for name in ("render", "files_state"):
            starts = [e["ns"] for e in subset if e["stage"] == name + "_begin"]
            ends = [e["ns"] for e in subset if e["stage"] == name + "_return"]
            if len(starts) == len(ends):
                metrics[f"{intent}_{name}_accumulated"] = (
                    sum(b - a for a, b in zip(starts, ends, strict=True)) / 1e6
                )
    return metrics


def run_child(case: str, output: Path, fixtures: Path, proof: bool = False) -> dict:
    import numpy as np
    from PySide6.QtCore import (
        QCoreApplication,
        QEvent,
        QMimeData,
        QPoint,
        QPointF,
        QSettings,
        Qt,
        QTimer,
        QUrl,
    )
    from PySide6.QtGui import QDragEnterEvent, QDropEvent
    from PySide6.QtTest import QTest

    from pixelscope.app import main_window as main_module
    from pixelscope.app.bootstrap import compose_main_window_presentation, create_application
    from pixelscope.core import load_latency_trace
    from pixelscope.core.image_document import ImageDocument
    from pixelscope.core.roi import RoiBounds
    from pixelscope.io.path_discovery import discover_registration_inputs
    from pixelscope.ui import difference_panel as diff_module
    from scripts.issue190_followup import desktop_metadata

    assert gc.isenabled()
    recorder = Recorder()
    expected = {"A": textured(1901), "B": textured(1902)}
    source_worker = main_module.ImageLoadWorker
    diff_worker = diff_module.TaskWorker
    original_mark = load_latency_trace.mark
    checks = []
    range_failures = []
    heartbeat = []
    context_by_source = {}

    def record_mark(stage, *, document_id=None, once=False):
        alias = recorder.documents.get(document_id) if document_id else None
        fields = {"source": alias} if alias else {}
        recorder.add(stage, **fields)
        # Default old diagnostic is OFF; no logger/disk activity in this observer.

    class SourceWorker(source_worker):
        def __init__(self, path, *args, **kwargs):
            self.diagnostic_context = context_by_source[Path(path).stem].copy()
            super().__init__(path, *args, **kwargs)
            context = self.diagnostic_context

            def succeeded(_task, _doc, _gen, result):
                recorder.add(
                    "load_result_signal", context=context, preview_revision=id(result.preview)
                )

            self.signals.succeeded.connect(succeeded, Qt.ConnectionType.DirectConnection)

        def run(self):
            recorder.local.context = self.diagnostic_context
            recorder.add("load_worker_start")
            try:
                super().run()
            finally:
                recorder.add("load_worker_return")
                del recorder.local.context

    class DiffWorker(diff_worker):
        def __init__(self, function, *args, **kwargs):
            kind = function.__name__.strip("_")
            context = {"intent_id": recorder.intent, "selection_epoch": recorder.epoch}
            recorder.add("diff_" + kind + "_queued", context=context)

            def measured(*values, **options):
                recorder.add("diff_" + kind + "_start", context=context)
                result = function(*values, **options)
                recorder.add(
                    "diff_" + kind + "_return",
                    context=context,
                    map_reused=bool(result[2]) if kind == "calculate" else False,
                )
                return result

            super().__init__(measured, *args, **kwargs)

    class Window(main_module.MainWindow):
        def _start_load(self, target_id, path, raw_profile):
            alias = Path(path).stem
            recorder.documents[target_id] = alias
            token = self._load_tokens.get(target_id, 0) + 1
            recorder.tokens[alias] = token
            context = {
                "intent_id": recorder.intent,
                "selection_epoch": recorder.epoch,
                "source": alias,
                "load_token": token,
                "generation": self.documents[target_id].generation,
            }
            context_by_source[alias] = context
            recorder.add("load_queued", context=context)
            return super()._start_load(target_id, path, raw_profile)

        def _load_succeeded(self, target_id, request_token, result):
            alias = recorder.documents.get(target_id, "unknown")
            context = context_by_source.get(alias, {}).copy()
            valid = (
                not self._closing
                and target_id in self.documents
                and self._load_tokens.get(target_id) == request_token
                and isinstance(result, ImageDocument)
            )
            recorder.add("source_gui_enter", context=context, token_valid=valid)
            super()._load_succeeded(target_id, request_token, result)
            if valid and self.documents.get(target_id) is result:
                recorder.add(
                    "source_gui_return_accepted",
                    context=context,
                    preview_revision=id(result.preview),
                    generation=result.generation,
                )

        def _render_selection(self, *args, **kwargs):
            recorder.add("render_begin")
            try:
                return super()._render_selection(*args, **kwargs)
            finally:
                recorder.add("render_return")

        def _update_file_states(self, *args, **kwargs):
            recorder.add("files_state_begin")
            try:
                return super()._update_file_states(*args, **kwargs)
            finally:
                recorder.add("files_state_return")

    app = create_application(["issue190-user-path"])
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(output / "settings")
    )
    QSettings().clear()
    window = None
    timer = QTimer()
    timer.setInterval(10)
    timer.timeout.connect(lambda: heartbeat.append(time.perf_counter_ns()))

    def wait(predicate, seconds=25):
        limit = time.perf_counter() + seconds
        while not predicate():
            if time.perf_counter() > limit:
                raise TimeoutError("bounded user-path condition")
            app.processEvents()
            QTest.qWait(1)

    try:
        main_module.ImageLoadWorker = SourceWorker
        diff_module.TaskWorker = DiffWorker
        load_latency_trace.mark = record_mark
        window = Window()
        compose_main_window_presentation(window)
        window.resize(1200, 800)
        window.setWindowTitle("PixelScope #190 R1-R3 " + case)
        window.show()
        app.processEvents()
        assert not window.documents and not window.selected_documents
        registration = window.large_folder_registration_controller

        def discovery(paths, **kwargs):
            context = {
                "intent_id": recorder.intent,
                "selection_epoch": recorder.epoch,
                "source": paths[0].stem,
            }
            recorder.add("discovery_start", context=context)
            result = discover_registration_inputs(paths, **kwargs)
            recorder.add("discovery_return", context=context)
            return result

        registration._discovery_function = discovery
        model = window.document_list.model()

        def rows(parent, first, last):
            for row in range(first, last + 1):
                index = model.index(row, 0, parent)
                document_id = index.data(Qt.ItemDataRole.UserRole)
                if document_id:
                    alias = Path(str(index.data(window.document_list.PATH_ROLE))).stem
                    recorder.documents[str(document_id)] = alias
                    recorder.add("row_registered", source=alias)

        model.rowsInserted.connect(rows)
        for viewer in (window.viewer, *window.multi_compare_view.viewers):
            viewer.first_frame_painted.connect(
                lambda document_id: recorder.add(
                    "legacy_first_frame_signal",
                    source=recorder.documents.get(document_id, "Diff"),
                    physical_viewer="not_attributed",
                )
            )
        window.difference_panel.map_cached.connect(
            lambda pair: recorder.add(
                "diff_cache_ready",
                pair="/".join(recorder.documents.get(i, "unknown") for i in pair),
            )
        )

        def available(aliases):
            docs = window.selected_documents
            return (
                registration.is_idle
                and not window._workers
                and [recorder.documents.get(d.document_id) for d in docs] == aliases
                and all(d.source is not None and d.preview is not None for d in docs)
            )

        def partial_view(aliases):
            viewers = (window.viewer, *window.multi_compare_view.occupied_viewers)
            seen = set()
            for viewer in viewers:
                document = viewer.document
                if (
                    viewer.isVisible()
                    and document is not None
                    and viewer._pending_document is None
                    and viewer.image_item.image is not None
                    and viewer.image_item.image.shape == document.preview.shape
                    and viewer.image_item.image.dtype == document.preview.dtype
                    and viewer.image_item.image.ctypes.data == document.preview.ctypes.data
                    and viewer.image_item.qimage is not None
                ):
                    seen.add(recorder.documents.get(document.document_id, "Diff"))
            return set(aliases).issubset(seen)

        def action(name, callback):
            recorder.action(name)
            callback()
            recorder.add("action_handler_return")

        def drop(alias):
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(str(fixtures / f"{alias}.png"))])
            surface = window.central_stack
            drag = QDragEnterEvent(
                QPoint(20, 20),
                Qt.DropAction.CopyAction,
                mime,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
            QCoreApplication.sendEvent(surface, drag)
            event = QDropEvent(
                QPointF(20, 20),
                Qt.DropAction.CopyAction,
                mime,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
            QCoreApplication.sendEvent(surface, event)
            assert drag.isAccepted() and event.isAccepted()

        recorder.active = True
        cpu_start = time.process_time_ns()
        timer.start()
        action(
            "A_first",
            lambda: window.open_image_paths([fixtures / "A.png"])
            if case == "R1_Open"
            else drop("A"),
        )
        wait(lambda: available(["A"]) and partial_view(["A"]))
        recorder.add(
            "ready_snapshot", source="A", status="partial_qimage_and_binding_not_postpaint"
        )
        # This is a partial-display gate, not the requested epoch-bound post-paint oracle.
        if case.startswith("R23"):
            assert (
                not window.difference_panel.has_cached_map() and not window.diff_action.isChecked()
            )
            action("B_add", lambda: drop("B"))
            wait(lambda: available(["A", "B"]) and partial_view(["A", "B"]))
            recorder.add("ready_snapshot", source="pair", status="partial_pair_not_valid_postpaint")
            wait(
                lambda: window.difference_panel.has_cached_map()
                and window.difference_panel._worker is None
            )
            assert not window.diff_action.isChecked() and window._difference_document is None
            checks += ["Drop_additive_A_B", "passive_Diff_default_hidden", "first_Diff_cache_miss"]
            action(
                "Diff_explicit_on",
                window.diff_action.trigger,
            )
            wait(
                lambda: window._difference_document is not None and partial_view(["A", "B", "Diff"])
            )
            recorder.add("ready_snapshot", source="Diff", status="partial_Diff_not_valid_postpaint")
            assert window.diff_action.isChecked()

            analysis = window.comparison_analysis_panel
            wait(
                lambda: analysis._worker is None
                and not analysis._refresh_timer.isActive()
                and window.difference_panel._worker is None
                and window.difference_panel._preview_worker is None
            )
            if case.endswith("OFF"):
                window.diff_action.trigger()
                app.processEvents()
            window._shared_roi_changed(RoiBounds(512, 256, 1024, 768))
            window.multi_compare_view.occupied_viewers[0].view_box.setRange(
                xRange=(600, 2200), yRange=(400, 1300), padding=0
            )
            wait(lambda: analysis._worker is None and not analysis._refresh_timer.isActive())
            app.processEvents()
            roi_before = window._shared_roi
            source_docs = list(window.selected_documents)
            for alias in ("B", "A"):
                ranges = {
                    recorder.documents.get(v.document.document_id, "Diff"): v.view_box.viewRange()
                    for v in window.multi_compare_view.occupied_viewers
                    if v.document is not None
                }
                target = next(
                    v
                    for v in window.multi_compare_view.occupied_viewers
                    if v.document is not None
                    and recorder.documents.get(v.document.document_id) == alias
                )
                action(
                    "Primary_" + alias,
                    lambda target=target: QTest.mouseClick(
                        target.header.focus, Qt.MouseButton.LeftButton
                    ),
                )
                wait(lambda: partial_view(["A", "B"]))
                recorder.add("ready_snapshot", source=alias, status="reuse_or_paint_not_attributed")
                assert window._focus_document_id == target.document.document_id
                assert window._shared_roi == roi_before and window.selected_documents == source_docs
                for viewer in window.multi_compare_view.occupied_viewers:
                    key = recorder.documents.get(viewer.document.document_id, "Diff")
                    for axis, (before, after) in enumerate(
                        zip(ranges[key], viewer.view_box.viewRange(), strict=True)
                    ):
                        recorder.add(
                            "primary_range_check",
                            source=key,
                            axis=axis,
                            before_low=before[0],
                            before_high=before[1],
                            after_low=after[0],
                            after_high=after[1],
                        )
                    if not np.allclose(
                        viewer.view_box.viewRange(), ranges[key], atol=1e-5, rtol=1e-9
                    ):
                        range_failures.append({"primary": alias, "source": key})
            checks += ["Primary_A_B_A", "ROI_preserved", "correct_Primary_header"]
            if not range_failures:
                checks.append("pan_preserved")
        elif case == "R1_Open":
            first_token = recorder.tokens["A"]
            action("A_reopen_warm_control", lambda: window.open_image_paths([fixtures / "A.png"]))
            wait(lambda: available(["A"]) and partial_view(["A"]))
            recorder.add("ready_snapshot", source="A", status="same_path_new_token_partial")
            assert recorder.tokens["A"] > first_token
            checks += ["Open_replacement", "same_file_reopen_new_token"]

        end = time.perf_counter_ns()
        cpu_ns = time.process_time_ns() - cpu_start
        timer.stop()
        recorder.active = False
        # Heavy checks outside all timed action/observation windows.
        for document in window.selected_documents:
            alias = recorder.documents[document.document_id]
            assert np.array_equal(document.source, expected[alias])
            assert np.array_equal(document.preview, expected[alias])
            assert (
                document.encoded_source_sha256
                == json.loads((fixtures / "manifest.json").read_text())[alias]["sha256"]
            )
        checks += [
            "exact_RGB_source_and_preview",
            "encoded_digest",
            "current_generation_tokens",
            "normal_GC",
        ]
        if case.startswith("R23"):
            result = window.difference_panel.cached_result_for_current()
            assert result is not None
            expected_diff = np.abs(
                expected["A"].astype(np.int16) - expected["B"].astype(np.int16)
            ).astype(np.uint8)
            assert np.array_equal(result.absolute, expected_diff)
            assert any(
                e["stage"] == "diff_calculate_return" and e.get("map_reused") is False
                for e in recorder.events
            )
            checks += ["first_uncached_Diff_exact_widened_math"]
        assert window._normal_load_stale_drop_count == 0 and registration.stale_result_count == 0
        checks += ["no_stale_publish"]
        desktop = desktop_metadata(app, window)
        if proof:
            # Endpoint-only external proof, excluded from every timing above.
            wait(lambda: (output / "continue.json").exists(), seconds=55)
        starts = [e["ns"] for e in recorder.events if e["stage"] == "intent_accepted"]
        intervals = [min(starts), *(t for t in heartbeat if min(starts) <= t <= end), end]
        gaps = [(b - a) / 1e6 for a, b in zip(intervals, intervals[1:], strict=False)]
        return {
            "status": "fail" if range_failures else "inconclusive",
            "correctness": "fail" if range_failures else "pass",
            "range_failures": range_failures,
            "case_id": case,
            "checks": checks,
            "events": recorder.events,
            "trace_dropped": recorder.dropped,
            "metrics_ms": stage_metrics(recorder.events),
            "system": {
                "heartbeat_max_gap_ms": max(gaps),
                "heartbeat_gaps_over_50ms": sum(g > 50 for g in gaps),
                "process_cpu_ms": cpu_ns / 1e6,
                "RSS": "not_measured",
                "private_bytes": "not_measured",
            },
            "desktop": desktop,
            "normal_gc": gc.isenabled(),
            "drop_delivery": (
                "synthetic_real_Qt_DnD_events_to_installed_image_surface_filter; " "not Explorer"
            ),
            "cache": (
                "fresh process/catalog/nonresident input; warm/uncontrolled OS file "
                "cache; first passive Diff MISS"
            ),
            "not_measured": [
                "valid_current_slot_postpaint",
                "first_coherent_pair_postpaint",
                "first_Diff_postpaint",
                "worker_result_exact_emit_to_slot_postpaint",
                "physical_scanout",
                "Explorer_hover",
                "timed_viewer_rebind_fit_aux_breakdown",
                "observer_OFF_ON_overhead",
            ],
            "paint_blocker": (
                "legacy document-only signal + qimage snapshot has no epoch/binding "
                "serial/paint-region post-return oracle; full 3-seam observer not "
                "prevalidated; no forced paint or processEvents substitute"
            ),
            "R2_precondition": (
                "A partial legacy/current-qimage readiness, "
                "NOT proven valid-current-slot postpaint"
            )
            if case.startswith("R23")
            else "not_applicable",
        }
    finally:
        recorder.active = False
        timer.stop()
        if sys.exc_info()[0] is not None:
            (output / "failure_diagnostic.json").write_text(
                json.dumps(
                    {
                        "events": recorder.events,
                        "trace_dropped": recorder.dropped,
                        "metrics_ms": stage_metrics(recorder.events),
                        "checks": checks,
                        "normal_gc": gc.isenabled(),
                    },
                    indent=2,
                ),
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
            main_module.ImageLoadWorker = source_worker
            diff_module.TaskWorker = diff_worker
            load_latency_trace.mark = original_mark


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fixtures", type=Path)
    parser.add_argument("--child")
    parser.add_argument("--proof", action="store_true")
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--repeats", type=int, default=8)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if args.child:
        try:
            result = run_child(args.child, output, args.fixtures.resolve(), args.proof)
        except Exception as error:
            import traceback

            traceback.print_exc()
            result = {"status": "fail", "correctness": "fail", "error_type": type(error).__name__}
            diagnostic = output / "failure_diagnostic.json"
            if diagnostic.exists():
                result.update(json.loads(diagnostic.read_text(encoding="utf-8")))
        (output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        return 1 if result["status"] == "fail" else 0
    manifest = make_fixtures(output / "fixtures")
    meta = {
        "base": BASE,
        "source_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "python": sys.version,
        "OS": platform.platform(),
        "fixtures": manifest,
        "warmups": args.warmups,
        "repeats": args.repeats,
        "cache": "warm/uncontrolled OS cache; no OS flush; fresh child and clean catalog each case",
        "normal_gc": gc.isenabled(),
        "postpaint": "inconclusive; no validated 3-seam observer",
        "instrumentation": (
            "test-owned class-native callback brackets and restored module " "checkpoints"
        ),
    }
    (output / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    samples = []
    cases = ["R1_Open", "R1_Drop", "R23_OFF", "R23_ON"]
    with (output / "cases.jsonl").open("w", encoding="utf-8") as stream:
        for repeat in range(args.warmups + args.repeats):
            for case in cases[repeat % 4 :] + cases[: repeat % 4]:
                run_id = f"{case}-{repeat:02d}"
                folder = output / run_id
                command = [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--child",
                    case,
                    "--output",
                    str(folder),
                    "--fixtures",
                    str(output / "fixtures"),
                ]
                try:
                    process = subprocess.run(command, capture_output=True, timeout=90, cwd=ROOT)
                    folder.mkdir(exist_ok=True)
                    (folder / "stderr.log").write_bytes(process.stderr)
                    (folder / "stdout.log").write_bytes(process.stdout)
                    result = (
                        json.loads((folder / "result.json").read_text())
                        if (folder / "result.json").exists()
                        else {"status": "fail", "correctness": "fail"}
                    )
                    if process.returncode:
                        result["status"] = "fail"
                    result["returncode"] = process.returncode
                except subprocess.TimeoutExpired:
                    result = {
                        "status": "fail",
                        "correctness": "fail",
                        "error_type": "watchdog_timeout",
                    }
                result.update(run_id=run_id, case_id=case, warmup=repeat < args.warmups)
                samples.append(result)
                stream.write(json.dumps(result) + "\n")
                stream.flush()
                print(run_id, result["status"], result.get("correctness"), flush=True)
    summary = {}
    for case in cases:
        rows = [
            s
            for s in samples
            if s["case_id"] == case and not s["warmup"] and s.get("correctness") == "pass"
        ]
        summary[case] = {
            key: {
                "median": statistics.median(
                    [s["metrics_ms"][key] for s in rows if key in s["metrics_ms"]]
                ),
                "raw": [s["metrics_ms"][key] for s in rows if key in s["metrics_ms"]],
            }
            for key in sorted({key for row in rows for key in row.get("metrics_ms", {})})
        }
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    failures = [s["run_id"] for s in samples if s["status"] == "fail"]
    (output / "decisions.json").write_text(
        json.dumps(
            {
                "result": "inconclusive",
                "failures": failures,
                "reason": (
                    "Exact valid current-slot paint and sequential A-display "
                    "precondition not proven; stage timings only"
                ),
                "feature_optimization_result": "inconclusive",
                "U2_S4": "not_measured",
                "G3": "unavailable",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
