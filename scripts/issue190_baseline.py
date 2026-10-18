"""Issue #190 diagnostic runner. No optimization; timings are observational.

Run with the repository's CPython 3.10 environment. Every sample runs in a fresh
child with a watchdog; raw output and isolated settings stay under ignored temp/.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path
from threading import Event

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
BASE = "a9ecbf49757b0135e658cc9842722b1604c3f2f1"


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")


def summarize(samples: list[dict]) -> dict:
    groups: dict[str, dict[str, list[float]]] = {}
    for sample in samples:
        if sample.get("warmup") or sample.get("status") != "ok":
            continue
        group = groups.setdefault(sample["case_id"], {})
        for key, value in sample.get("metrics_ms", {}).items():
            group.setdefault(key, []).append(value)
    return {
        case: {
            key: {"median": statistics.median(values), "raw": values}
            for key, values in metrics.items()
        }
        for case, metrics in groups.items()
    }


def child(case: str, output: Path) -> dict:
    if case.startswith("E1"):
        os.environ["PIXELSCOPE_LOAD_TRACE"] = "1"
    import cv2
    import numpy as np
    from PySide6.QtCore import QCoreApplication, QEvent, QSettings, Qt, QTimer
    from PySide6.QtTest import QSignalSpy, QTest

    from pixelscope.app.bootstrap import (
        compose_main_window_presentation,
        create_application,
    )
    from pixelscope.app.main_window import MainWindow
    from pixelscope.core.image_document import ImageDocument
    from pixelscope.io.path_discovery import discover_registration_inputs

    assert gc.isenabled(), "normal automatic GC is required"
    app = create_application(["issue190"])
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(output / "settings")
    )
    QSettings().clear()
    window = MainWindow()
    compose_main_window_presentation(window)
    window.resize(1200, 800)
    window.show()

    def wait(predicate, seconds=15):
        deadline = time.perf_counter() + seconds
        while not predicate():
            if time.perf_counter() >= deadline:
                raise TimeoutError("bounded GUI condition did not complete")
            app.processEvents()
            QTest.qWait(1)

    app.processEvents()
    marks = {}
    metrics = {}
    checks = []
    fixtures = output / "fixtures"
    fixtures.mkdir()

    def image(path, value, shape=(8, 12, 3)):
        assert cv2.imwrite(str(path), np.full(shape, value, dtype=np.uint8))
        return path

    ticks = []
    heartbeat = QTimer()
    heartbeat.setInterval(10)
    heartbeat.timeout.connect(lambda: ticks.append(time.perf_counter_ns()))
    controller = window.large_folder_registration_controller
    release = Event()
    started = time.perf_counter_ns()

    def mark(name):
        marks[name] = time.perf_counter_ns()

    try:
        if case.startswith("E2"):
            folder = fixtures / "F"
            folder.mkdir()
            for index in range(1, 129):
                image(folder / f"image{index}.png", index)
                (folder / f"unsupported{index}.txt").write_text("unsupported", encoding="utf-8")
            a, b = image(fixtures / "A.png", 17), image(fixtures / "B.png", 93)
            entered = Event()
            order = []

            # Existing discovery injection point: worker closure holds plain data only.
            def discovery(paths, **kwargs):
                name = "F" if paths[0] == folder else paths[0].stem
                marks[name + "_discovery_start"] = time.perf_counter_ns()
                order.append(name)
                if name == "F":
                    entered.set()
                    if not release.wait(5):
                        raise TimeoutError("discovery barrier was not released")
                result = discover_registration_inputs(paths, **kwargs)
                marks[name + "_discovery_end"] = time.perf_counter_ns()
                return result

            controller._discovery_function = discovery
            folder_selection = []

            def rows_inserted(parent, first, last):
                # E2 row milestones only; E3 timing has no row observer.
                model = window.document_list.model()
                for row in range(first, last + 1):
                    index = model.index(row, 0, parent)
                    if not index.data(Qt.ItemDataRole.UserRole):
                        continue
                    path = Path(str(index.data(window.document_list.PATH_ROLE)))
                    name = path.stem
                    if path.parent == folder:
                        marks.setdefault("F_first_row", time.perf_counter_ns())
                        marks["F_final_row"] = time.perf_counter_ns()
                    elif name in ("A", "B"):
                        marks[name + "_registered"] = time.perf_counter_ns()

            window.document_list.model().rowsInserted.connect(rows_inserted)
            controller.progress_changed.connect(
                lambda phase, _done, _total: folder_selection.append(
                    [d.display_name for d in window.selected_documents]
                )
                if phase == "idle" and len(window.documents) == 128
                else None
            )
            started = time.perf_counter_ns()
            heartbeat.start()
            if case == "E2_contended":
                mark("F_enqueue")
                controller.enqueue([folder])
                wait(entered.is_set)
            mark("A_enqueue")
            window.open_image_paths([a])
            mark("B_enqueue")
            assert window.quick_compare_controller.handle_image_drop([b])
            if case == "E2_contended":
                QTimer.singleShot(750, release.set)
            wait(lambda: controller.is_idle)
            mark("registration_complete")
            assert [d.source_path for d in window.selected_documents] == [a.resolve(), b.resolve()]
            assert order == (["F", "A", "B"] if case == "E2_contended" else ["A", "B"])
            assert controller.stale_result_count == 0
            assert len(window.documents) == (130 if case == "E2_contended" else 2)
            assert len(set(window.documents)) == len(window.documents)
            if case == "E2_contended":
                folder_docs = [
                    d for d in window.documents.values() if d.source_path.parent == folder
                ]
                assert [d.display_name for d in folder_docs] == [
                    f"image{i}.png" for i in range(1, 129)
                ]
                assert folder_selection == [[]]
            checks += [
                "A_B_order",
                "FIFO",
                "unique_rows",
                "no_stale_callback",
                "folder_natural_order_no_autoselect",
            ]
            for name in ("A", "B"):
                for milestone in ("discovery_start", "registered"):
                    metrics[name + "_enqueue_to_" + milestone] = (
                        marks[name + "_" + milestone] - marks[name + "_enqueue"]
                    ) / 1e6
        elif case.startswith("E3"):
            _, lane, count_text = case.split("_")
            count = int(count_text)
            write_json(
                fixtures / "catalog.json",
                {
                    "count": count,
                    "shape": [8, 12],
                    "dtype": "uint8",
                    "state": "resident",
                    "value_rule": "index modulo 256",
                },
            )
            ids = []
            for index in range(count):
                document = ImageDocument.from_array(
                    np.full((8, 12), index % 256, dtype=np.uint8), f"item{index}"
                )
                window.add_document(document, select=False)
                ids.append(document.document_id)
            window.document_list.expandAll()
            window._select_document_ids([ids[-1]])
            app.processEvents()
            counts = {"dataChanged": 0, "selectionChanged": 0}

            def data_changed(*_args):
                counts["dataChanged"] += 1

            def selection_changed(*_args):
                counts["selectionChanged"] += 1

            if lane == "L2":
                window.document_list.model().dataChanged.connect(data_changed)
                window.document_list.selectionModel().selectionChanged.connect(selection_changed)
            started = time.perf_counter_ns()
            heartbeat.start()

            def timed(name, action):
                before = time.perf_counter_ns()
                action()
                metrics[name] = (time.perf_counter_ns() - before) / 1e6
                app.processEvents()

            timed("select_one", lambda: window._select_document_ids([ids[0]]))
            assert [d.document_id for d in window.selected_documents] == [ids[0]]
            item = window.document_list.document_item(ids[0])
            assert window.document_list.currentItem() is item
            timed(
                "update_file_states",
                lambda: window._update_file_states(
                    [window.documents[ids[0]]], window.documents[ids[0]]
                ),
            )
            assert item.data(0, window.document_list.ACTIVE_ROLE)
            assert item.toolTip(0)
            timed("keyboard_down", lambda: QTest.keyClick(window.document_list, Qt.Key.Key_Down))
            if count > 1:
                assert window.document_list.currentItem() is not item
            window.document_list.scrollToItem(item)
            app.processEvents()
            rect = window.document_list.visualItemRect(item)
            assert not rect.isEmpty()
            timed(
                "mouse_select",
                lambda: QTest.mouseClick(
                    window.document_list.viewport(), Qt.MouseButton.LeftButton, pos=rect.center()
                ),
            )
            assert [d.document_id for d in window.selected_documents] == [ids[0]]
            window._select_document_ids(ids[:2])
            app.processEvents()
            before_scroll = window.document_list.verticalScrollBar().value()
            primary_id = ids[min(1, count - 1)]
            timed("primary_toggle", lambda: window._set_focus_document(primary_id))
            assert window._focus_document_id == primary_id
            assert window.document_list.verticalScrollBar().value() == before_scroll
            checks += [
                "selected_order",
                "current_item",
                "active_role_tooltip",
                "keyboard",
                "mouse",
                "scrollbar",
            ]
            marks["proxy_counts"] = counts
        elif case.startswith("E1"):
            from pixelscope.workers import image_load_worker

            _, action, delay_text = case.split("_")
            delay = int(delay_text)
            a = image(fixtures / "A.png", 17, (2160, 3840, 3))
            b = image(fixtures / "B.png", 93, (2160, 3840, 3))
            original_read = image_load_worker.read_image

            def delayed_read(path):
                if path == b:
                    time.sleep(delay / 1000)
                result = original_read(path)
                marks[path.stem + "_worker_read_return"] = time.perf_counter_ns()
                return result

            image_load_worker.read_image = delayed_read
            spies = [
                QSignalSpy(viewer.first_frame_painted)
                for viewer in (window.viewer, *window.multi_compare_view.viewers)
            ]
            accepted = {}
            paints = []
            offsets = [0] * len(spies)
            started = time.perf_counter_ns()
            heartbeat.start()
            if action == "Open":
                window.open_image_paths([a, b])
            else:
                assert window.quick_compare_controller.handle_image_drop([a, b])

            def ready():
                now = time.perf_counter_ns()
                for document in window.documents.values():
                    if document.source is not None:
                        accepted.setdefault(document.display_name, now)
                for i, spy in enumerate(spies):
                    while offsets[i] < spy.count():
                        paints.append(
                            {
                                "viewer_index": i,
                                "document_id": spy.at(offsets[i])[0],
                                "observed_ns": now,
                            }
                        )
                        offsets[i] += 1
                return len(accepted) == 2 and bool(paints) and not window._workers

            wait(ready)
            metrics["both_ready_and_partial_paint"] = (time.perf_counter_ns() - started) / 1e6
            heartbeat.stop()
            assert all(d.loading_state == "ready" for d in window.selected_documents)
            for document in window.selected_documents:
                assert document.source.shape == (2160, 3840, 3)
                assert np.all(document.source == (17 if document.display_name == "A.png" else 93))
            marks["GUI_ready_poll_upper_bound"] = accepted
            marks["partial_paint_signals"] = paints
            checks += ["both_sources_exact", "existing_first_frame_signal"]
            image_load_worker.read_image = original_read
        else:
            raise ValueError(case)
        app.processEvents()
        heartbeat.stop()
        ended = time.perf_counter_ns()
        intervals = [started, *ticks, ended]
        metrics["heartbeat_max_gap"] = (
            max(b - a for a, b in zip(intervals, intervals[1:], strict=False)) / 1e6
        )
        return {
            "status": "ok",
            "metrics_ms": metrics,
            "milestones": marks,
            "checks": checks,
            "elapsed_ms": (ended - started) / 1e6,
            "normal_gc": gc.isenabled(),
            "fixture_sha256": fixture_digest(fixtures),
            "qt_platform": app.platformName(),
        }
    finally:
        release.set()
        heartbeat.stop()
        window.close()
        wait(
            lambda: window._load_pool.activeThreadCount() == 0
            and controller.pool.activeThreadCount() == 0
        )
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def fixture_digest(folder: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(folder.iterdir()):
        if path.is_dir():
            digest.update(fixture_digest(path).encode())
        else:
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "temp/issue190")
    parser.add_argument("--repeats", type=int, default=8)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--lanes", default="E2,E3,E1")
    parser.add_argument("--child")
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.child:
        try:
            result = child(args.child, args.output)
        except Exception as error:
            import traceback

            traceback.print_exc()
            result = {"status": "failed", "error": type(error).__name__ + ": " + str(error)}
        write_json(args.output / "result.json", result)
        return 0 if result["status"] == "ok" else 1
    if args.repeats < 1 or args.warmups < 0:
        parser.error("positive repeats and nonnegative warmups required")
    cases = []
    lanes = args.lanes.split(",")
    if "E2" in lanes:
        cases += ["E2_control", "E2_contended"]
    if "E3" in lanes:
        cases += [f"E3_{lane}_{size}" for size in (1, 100, 1000) for lane in ("L1", "L2")]
    if "E1" in lanes:
        cases += [f"E1_{action}_{delay}" for action in ("Open", "Drop") for delay in (0, 250, 1000)]
    source_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    import cv2
    import numpy
    import pyqtgraph
    import PySide6

    write_json(
        args.output / "run_meta.json",
        {
            "base_sha": BASE,
            "source_sha": source_sha,
            "python": sys.version,
            "os": platform.platform(),
            "qt": PySide6.__version__,
            "deps": {
                "numpy": numpy.__version__,
                "opencv": cv2.__version__,
                "pyqtgraph": pyqtgraph.__version__,
            },
            "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "normal_gc": gc.isenabled(),
            "seed": 0,
            "display_mode": os.environ.get("QT_QPA_PLATFORM", "native"),
            "cache": "fresh process; OS cache uncontrolled; generated fixtures warm",
            "fixture": (
                "E2 128 PNG + 128 unsupported, direct A/B; "
                "E3 resident 8x12 gray; E1 two UHD RGB8"
            ),
            "barrier_ms": 750,
            "network": "G3_unavailable: no representative UNC supplied",
            "repeats": args.repeats,
            "warmups": args.warmups,
            "dirty": bool(
                subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
            ),
        },
    )
    samples = []
    # Rotate case order by repetition; no retry or failed-sample replacement.
    with (args.output / "cases.jsonl").open("w", encoding="utf-8") as raw:
        for repeat in range(args.warmups + args.repeats):
            for case in cases[repeat % len(cases) :] + cases[: repeat % len(cases)]:
                run_id = f"{case}-{repeat:02d}"
                folder = args.output / run_id
                folder.mkdir(exist_ok=False)
                command = [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--child",
                    case,
                    "--output",
                    str(folder),
                ]
                try:
                    completed = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=60)
                    (folder / "stdout.log").write_bytes(completed.stdout)
                    (folder / "stderr.log").write_bytes(completed.stderr)
                    result_file = folder / "result.json"
                    result = (
                        json.loads(result_file.read_text(encoding="utf-8"))
                        if result_file.exists()
                        else {"status": "crashed"}
                    )
                    result["returncode"] = completed.returncode
                    if completed.returncode:
                        result["status"] = "failed"
                except subprocess.TimeoutExpired:
                    result = {"status": "timeout"}
                result.update(case_id=case, run_id=run_id, warmup=repeat < args.warmups)
                samples.append(result)
                raw.write(json.dumps(result) + "\n")
                raw.flush()
                print(run_id, result["status"], flush=True)
    write_json(args.output / "summary.json", summarize(samples))
    failures = [s["run_id"] for s in samples if s["status"] != "ok"]
    write_json(
        args.output / "decisions.json",
        {
            "U1": (
                "inconclusive: E1 legacy signal lacks slot/epoch/binding identity; "
                "no exact first valid tile attribution"
            ),
            "U2": (
                "inconclusive: E2 synthetic FIFO causal fixture only; "
                "no real SMB or scheduler candidate"
            ),
            "U3": "inconclusive: no residency candidate or protected-source overlap measurement",
            "U4": "inconclusive: E3 baseline/proxy counts only; no candidate or MDE",
            "grade": "G1 synthetic; Windows Qt event processing, not physical scanout",
            "missing": [
                "G3 real SMB",
                "E1 three-seam observer and OFF/ON/lifecycle prevalidation",
                "process peak memory",
                "E3 viewport repaint proxy",
                "independent Qt/System/QA methodology reviews",
            ],
            "failures": failures,
            "raw_run_ids": [s["run_id"] for s in samples],
            "command": (
                "python scripts/issue190_baseline.py --output temp/issue190-run "
                "--warmups 2 --repeats 8"
            ),
        },
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
