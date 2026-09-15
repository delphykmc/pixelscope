from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from collections import deque
from datetime import datetime
from pathlib import Path

GOOD = "eac9e412ee483c0852528c59524d861410873bf3"
BAD = "6b8773fbfe5402738d9da121bc8e11e5c5fd5532"
PRODUCTION_FILE = Path("src/pixelscope/ui/plots_dock_title.py")
CHANGED_EXISTING_TESTS = (
    Path("tests/ui/test_issue81_qt_lifecycle.py"),
    Path("tests/ui/test_plot_statistics_contracts.py"),
)
NEW_TESTS = (Path("tests/ui/test_issue84_floating_workspace_maximize.py"),)

HEAP_CORRUPTION = 0xC0000374
ACCESS_VIOLATION = 0xC0000005

CASES = {
    "good": "exact last-known-good tree",
    "bad": "exact first-bad merged tree",
    "good_prod_bad_tests": "PR85 tree/tests with plots_dock_title.py reverted to good",
    "bad_prod_good_tests": "PR85 production with PR85 test delta removed",
}


def _run(
    cwd: Path,
    command: list[str],
    *,
    check: bool = True,
    capture: bool = False,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def _git(repo: Path, *args: str, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return _run(repo, ["git", *args], capture=capture)


def _repo_root() -> Path:
    completed = _run(
        Path.cwd(),
        ["git", "rev-parse", "--show-toplevel"],
        capture=True,
    )
    return Path(completed.stdout.strip()).resolve()


def _require_commit(repo: Path, sha: str) -> None:
    try:
        _git(repo, "cat-file", "-e", f"{sha}^{{commit}}", capture=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Required commit {sha} is not available locally. Run git fetch first.") from exc


def _restore_file(repo: Path, worktree: Path, ref: str, path: Path) -> None:
    data = subprocess.run(
        ["git", "show", f"{ref}:{path.as_posix()}"],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout
    target = worktree / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


def _prepare_case(repo: Path, worktree: Path, case: str) -> None:
    if case in {"good", "bad"}:
        return
    if case == "good_prod_bad_tests":
        _restore_file(repo, worktree, GOOD, PRODUCTION_FILE)
        return
    if case == "bad_prod_good_tests":
        for path in CHANGED_EXISTING_TESTS:
            _restore_file(repo, worktree, GOOD, path)
        for path in NEW_TESTS:
            target = worktree / path
            if target.exists():
                target.unlink()
        return
    raise ValueError(f"Unknown case: {case}")


def _environment(worktree: Path) -> dict[str, str]:
    env = os.environ.copy()
    source = str((worktree / "src").resolve())
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = source if not existing else source + os.pathsep + existing
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONUNBUFFERED"] = "1"
    return env


def _verify_source(worktree: Path, env: dict[str, str]) -> None:
    completed = _run(
        worktree,
        [sys.executable, "-c", "import pixelscope.ui.plots_dock_title as m; print(m.__file__)"],
        capture=True,
        env=env,
    )
    actual = Path(completed.stdout.strip()).resolve()
    expected = (worktree / PRODUCTION_FILE).resolve()
    if os.path.normcase(str(actual)) != os.path.normcase(str(expected)):
        raise RuntimeError(f"Wrong source imported: expected {expected}, got {actual}")


def _classify(returncode: int) -> str:
    if returncode == 0:
        return "PASS"
    normalized = returncode & 0xFFFFFFFF
    if normalized == HEAP_CORRUPTION:
        return "HEAP_CORRUPTION_0xC0000374"
    if normalized == ACCESS_VIOLATION:
        return "ACCESS_VIOLATION_0xC0000005"
    if normalized >= 0xC0000000:
        return f"NATIVE_CRASH_0x{normalized:08X}"
    if returncode == 1:
        return "PYTEST_COMPLETED_WITH_FAILURES"
    return f"PYTEST_EXIT_{returncode}"


def _full_suite(worktree: Path, env: dict[str, str], log: Path) -> tuple[int, list[str]]:
    tail: deque[str] = deque(maxlen=30)
    with log.open("w", encoding="utf-8", errors="replace") as stream:
        process = subprocess.Popen(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=worktree,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            stream.write(line)
            stream.flush()
            tail.append(line.rstrip())
        return process.wait(), list(tail)


def _base_for_case(case: str) -> str:
    return GOOD if case == "good" else BAD


def _case_summary(results: list[str]) -> str:
    if any(item.startswith("HEAP_CORRUPTION") for item in results):
        return "HEAP_CORRUPTION_REPRODUCED"
    if any("ACCESS_VIOLATION" in item or item.startswith("NATIVE_CRASH") for item in results):
        return "NATIVE_CRASH_REPRODUCED"
    if results and all(item in {"PASS", "PYTEST_COMPLETED_WITH_FAILURES"} for item in results):
        return "NO_NATIVE_CRASH_OBSERVED"
    return "INCONCLUSIVE"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the PR85 Qt lifecycle 2x2 production/test matrix.")
    parser.add_argument(
        "--cases",
        nargs="+",
        choices=tuple(CASES),
        default=list(CASES),
        help="Cases to run. Default: all four cases.",
    )
    parser.add_argument("--repeats", type=int, default=1, help="Fresh-process runs per case.")
    parser.add_argument("--keep-worktrees", action="store_true")
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")

    repo = _repo_root()
    _require_commit(repo, GOOD)
    _require_commit(repo, BAD)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output = Path(tempfile.gettempdir()) / f"pixelscope-pr85-matrix-{stamp}"
    output.mkdir(parents=True)
    print("PR #85 Qt lifecycle matrix diagnostic")
    print(f"Python: {sys.executable}")
    print(f"Output: {output}\n")

    summaries: dict[str, str] = {}
    all_results: dict[str, list[str]] = {}

    for case in args.cases:
        worktree = output / f"worktree-{case}"
        logs = output / f"logs-{case}"
        logs.mkdir()
        base = _base_for_case(case)
        added = False
        results: list[str] = []
        try:
            _git(repo, "worktree", "add", "--detach", str(worktree), base)
            added = True
            _prepare_case(repo, worktree, case)
            env = _environment(worktree)
            _verify_source(worktree, env)

            status = _git(worktree, "status", "--short", capture=True).stdout
            (output / f"status-{case}.txt").write_text(status, encoding="utf-8")
            print(f"[{case}] {CASES[case]}")
            for index in range(1, args.repeats + 1):
                log = logs / f"full-suite-{index}.log"
                print(f"  run {index}/{args.repeats}: running")
                returncode, tail = _full_suite(worktree, env, log)
                result = _classify(returncode)
                results.append(result)
                print(f"  run {index}/{args.repeats}: {result} (exit={returncode})")
                if result not in {"PASS", "PYTEST_COMPLETED_WITH_FAILURES"}:
                    for line in tail[-8:]:
                        print(f"    {line}")
        finally:
            if added and not args.keep_worktrees:
                subprocess.run(
                    ["git", "worktree", "remove", "--force", str(worktree)],
                    cwd=repo,
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        all_results[case] = results
        summaries[case] = _case_summary(results)
        print(f"  case verdict: {summaries[case]}\n")

    subprocess.run(
        ["git", "worktree", "prune"],
        cwd=repo,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    lines = ["PR85 lifecycle matrix summary"]
    for case in args.cases:
        lines.append(f"{case}={summaries[case]}")
        for index, result in enumerate(all_results[case], start=1):
            lines.append(f"{case}.run_{index}={result}")
    (output / "SUMMARY.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("=== RESULT TO SHARE ===")
    for case in args.cases:
        print(f"{case.upper()}={summaries[case]}")
        for index, result in enumerate(all_results[case], start=1):
            print(f"{case.upper()}_RUN_{index}={result}")
    print(f"Local logs: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
