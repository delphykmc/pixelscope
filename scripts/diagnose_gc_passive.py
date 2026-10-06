from __future__ import annotations

import argparse
import faulthandler
import gc
import heapq
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest


class PassiveGCProbe:
    """Observe natural cyclic-GC activity without forcing collection or touching Qt."""

    def __init__(self, log_path: Path, summary_path: Path, fatal_path: Path) -> None:
        self.log_path = log_path
        self.summary_path = summary_path
        self.fatal_path = fatal_path
        for path in (log_path, summary_path, fatal_path):
            path.parent.mkdir(parents=True, exist_ok=True)

        self.log_file = log_path.open("w", encoding="utf-8", buffering=1)
        self.fatal_file = fatal_path.open("w", encoding="utf-8", buffering=1)
        faulthandler.enable(file=self.fatal_file, all_threads=True)

        self.started = 0
        self.current_index = 0
        self.current_nodeid = "<session>"
        self.current_state = "session"
        self.t0 = time.monotonic()
        self.registered = False

        self.gc_events = [0, 0, 0]
        self.gc_collected = [0, 0, 0]
        self.gc_max = [0, 0, 0]
        self.gen2_bins: dict[int, list[int]] = defaultdict(lambda: [0, 0])
        self.top_events: list[tuple[int, int, int, str, str]] = []

        self.log_file.write(
            "kind\telapsed_s\tindex\tstate\tgeneration\tcollected\tuncollectable\tnodeid\n"
        )

    @staticmethod
    def _safe_nodeid(nodeid: str) -> str:
        return nodeid.replace("\t", " ").replace("\n", " ").replace("\r", " ")

    def _write(
        self,
        kind: str,
        *,
        generation: int = -1,
        collected: int = -1,
        uncollectable: int = -1,
        nodeid: str | None = None,
    ) -> None:
        elapsed = time.monotonic() - self.t0
        selected_nodeid = self.current_nodeid if nodeid is None else nodeid
        self.log_file.write(
            f"{kind}\t{elapsed:.6f}\t{self.current_index}\t{self.current_state}\t"
            f"{generation}\t{collected}\t{uncollectable}\t"
            f"{self._safe_nodeid(selected_nodeid)}\n"
        )

    def _gc_callback(self, phase: str, info: dict[str, int]) -> None:
        if phase != "stop":
            return

        generation = int(info.get("generation", -1))
        collected = int(info.get("collected", 0))
        uncollectable = int(info.get("uncollectable", 0))

        self._write(
            "gc",
            generation=generation,
            collected=collected,
            uncollectable=uncollectable,
        )

        if 0 <= generation <= 2:
            self.gc_events[generation] += 1
            self.gc_collected[generation] += collected
            self.gc_max[generation] = max(self.gc_max[generation], collected)

        if generation == 2:
            bucket = ((max(self.current_index, 1) - 1) // 100) * 100 + 1
            bucket_values = self.gen2_bins[bucket]
            bucket_values[0] += 1
            bucket_values[1] += collected

        candidate = (
            collected,
            generation,
            self.current_index,
            self.current_state,
            self.current_nodeid,
        )
        if len(self.top_events) < 40:
            heapq.heappush(self.top_events, candidate)
        elif candidate > self.top_events[0]:
            heapq.heapreplace(self.top_events, candidate)

    def pytest_sessionstart(self, session: pytest.Session) -> None:
        del session
        self._write("session_start", nodeid=f"gc_threshold={gc.get_threshold()}")
        gc.callbacks.append(self._gc_callback)
        self.registered = True

    def pytest_runtest_logstart(self, nodeid: str, location: tuple[str, int | None, str]) -> None:
        del location
        self.started += 1
        self.current_index = self.started
        self.current_nodeid = nodeid
        self.current_state = "test"
        self._write("test_start")

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        if report.when != "teardown":
            return
        self._write("test_end", nodeid=report.nodeid)
        self.current_state = "between_tests"

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        del session
        if self.registered:
            with suppress_value_error():
                gc.callbacks.remove(self._gc_callback)
            self.registered = False
        self.current_state = "session_finish"
        self._write("session_finish", nodeid=f"exit={int(exitstatus)}")
        self._write_summary(exitstatus)

    def _write_summary(self, exitstatus: int) -> None:
        with self.summary_path.open("w", encoding="utf-8") as fp:
            fp.write("PixelScope passive natural-GC timeline\n")
            fp.write("===================================\n")
            fp.write(f"pytest_exit={int(exitstatus)}\n")
            fp.write(f"tests_started={self.started}\n")
            fp.write(f"gc_enabled={gc.isenabled()}\n")
            fp.write(f"gc_threshold={gc.get_threshold()}\n\n")

            fp.write("GC totals\n")
            fp.write("generation  events  collected  max_single_collection\n")
            for generation in range(3):
                fp.write(
                    f"{generation:>10}  {self.gc_events[generation]:>6}  "
                    f"{self.gc_collected[generation]:>9}  {self.gc_max[generation]:>21}\n"
                )

            fp.write("\nGeneration-2 progression by 100-test prefix\n")
            fp.write("tests       events  collected\n")
            for bucket in sorted(self.gen2_bins):
                events, collected = self.gen2_bins[bucket]
                fp.write(f"{bucket:04d}-{bucket + 99:04d}  {events:>6}  {collected:>9}\n")

            fp.write("\nLargest natural GC events\n")
            fp.write("collected  gen  index  state          nodeid\n")
            for collected, generation, index, state, nodeid in sorted(
                self.top_events, reverse=True
            ):
                fp.write(
                    f"{collected:>9}  {generation:>3}  {index:>5}  "
                    f"{state:<13}  {nodeid}\n"
                )

    def close(self) -> None:
        if self.registered:
            with suppress_value_error():
                gc.callbacks.remove(self._gc_callback)
            self.registered = False
        self.log_file.flush()
        self.log_file.close()
        self.fatal_file.flush()
        self.fatal_file.close()


class suppress_value_error:
    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        del exc, tb
        return exc_type is ValueError


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gc-log", default="temp/gc_passive.tsv")
    parser.add_argument("--summary", default="temp/gc_passive_summary.txt")
    parser.add_argument("--fatal-log", default="temp/gc_passive_fatal.log")
    return parser.parse_known_args()


def main() -> int:
    args, pytest_args = parse_args()
    probe = PassiveGCProbe(
        Path(args.gc_log),
        Path(args.summary),
        Path(args.fatal_log),
    )
    try:
        return int(pytest.main(pytest_args, plugins=[probe]))
    finally:
        probe.close()


if __name__ == "__main__":
    raise SystemExit(main())
