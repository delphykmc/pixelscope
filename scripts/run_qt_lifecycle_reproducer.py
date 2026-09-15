from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

_HEAP_CORRUPTION = 0xC0000374
_ACCESS_VIOLATION = 0xC0000005
_TESTS = (
    "tests/ui/test_qt_lifecycle_reproducer.py::test_00_heavy_qt_widget_tree_teardown",
    "tests/ui/test_qt_lifecycle_reproducer.py::test_01_background_worker_after_heavy_qt_teardown",
)


def _repo_root() -> Path:
    completed = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return Path(completed.stdout.strip()).resolve()


def _environment(repo: Path) -> dict[str, str]:
    env = os.environ.copy()
    source = str((repo / "src").resolve())
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = source if not existing else source + os.pathsep + existing
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONUNBUFFERED"] = "1"
    env["PIXELSCOPE_QT_LIFECYCLE_REPRO"] = "1"
    return env


def _classify(returncode: int) -> str:
    if returncode == 0:
        return "PASS"
    normalized = returncode & 0xFFFFFFFF
    if normalized == _HEAP_CORRUPTION:
        return "HEAP_CORRUPTION_0xC0000374"
    if normalized == _ACCESS_VIOLATION:
        return "ACCESS_VIOLATION_0xC0000005"
    if normalized >= 0xC0000000:
        return f"NATIVE_CRASH_0x{normalized:08X}"
    if returncode == 1:
        return "PYTEST_COMPLETED_WITH_FAILURES"
    return f"PYTEST_EXIT_{returncode}"


def _run_once(
    repo: Path,
    env: dict[str, str],
    timeout_seconds: int,
    log_path: Path,
) -> str:
    command = [sys.executable, "-m", "pytest", "-q", "-s", *_TESTS]
    process = subprocess.Popen(
        command,
        cwd=repo,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
    )
    try:
        output, _ = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        process.kill()
        output, _ = process.communicate()
        log_path.write_text(output, encoding="utf-8", errors="replace")
        return f"HANG_TIMEOUT_{timeout_seconds}S"
    log_path.write_text(output, encoding="utf-8", errors="replace")
    return _classify(process.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Repeatedly run the ordered A->B Qt lifecycle reproducer in fresh Python processes."
        )
    )
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    if args.timeout_seconds < 1:
        parser.error("--timeout-seconds must be at least 1")

    repo = _repo_root()
    env = _environment(repo)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = Path(tempfile.gettempdir()) / f"pixelscope-qt-lifecycle-repro-{stamp}"
    output_dir.mkdir(parents=True)

    print("PixelScope Qt lifecycle A->B reproducer")
    print(f"Python: {sys.executable}")
    print(f"Repeats: {args.repeats}")
    print(f"Timeout: {args.timeout_seconds}s")
    print(f"Logs: {output_dir}\n")

    results: list[str] = []
    for index in range(1, args.repeats + 1):
        log_path = output_dir / f"run-{index:02d}.log"
        print(f"[{index}/{args.repeats}] running", flush=True)
        result = _run_once(repo, env, args.timeout_seconds, log_path)
        results.append(result)
        print(f"[{index}/{args.repeats}] {result}", flush=True)

    failures = sum(result != "PASS" for result in results)
    native = sum(
        "HEAP_CORRUPTION" in result
        or "ACCESS_VIOLATION" in result
        or result.startswith("NATIVE_CRASH")
        for result in results
    )
    hangs = sum(result.startswith("HANG_TIMEOUT") for result in results)

    summary = [
        "PixelScope Qt lifecycle A->B reproducer summary",
        f"runs={len(results)}",
        f"non_pass={failures}",
        f"native_crash={native}",
        f"hang={hangs}",
        *(f"run_{index}={result}" for index, result in enumerate(results, start=1)),
    ]
    (output_dir / "SUMMARY.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")

    print("\n=== RESULT TO SHARE ===")
    print(f"RUNS={len(results)}")
    print(f"NON_PASS={failures}")
    print(f"NATIVE_CRASH={native}")
    print(f"HANG={hangs}")
    for index, result in enumerate(results, start=1):
        print(f"RUN_{index}={result}")
    print(f"Local logs: {output_dir}")
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
