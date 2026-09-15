from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from collections import deque
from datetime import datetime
from pathlib import Path

GOOD_BASELINE = "eac9e412ee483c0852528c59524d861410873bf3"
FIRST_BAD_MERGE = "6b8773fbfe5402738d9da121bc8e11e5c5fd5532"
TARGET_FILE = Path("src/pixelscope/ui/plots_dock_title.py")

_HEAP_CORRUPTION = 0xC0000374
_ACCESS_VIOLATION = 0xC0000005


def _git(repo: Path, *args: str, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
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


def _require_commit(repo: Path, sha: str) -> None:
    try:
        _git(repo, "cat-file", "-e", f"{sha}^{{commit}}", capture=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"Required commit {sha} is not available locally. Fetch the hotfix branch/history first."
        ) from exc


def _replace_with_good_baseline(repo: Path, probe: Path) -> None:
    completed = subprocess.run(
        ["git", "show", f"{GOOD_BASELINE}:{TARGET_FILE.as_posix()}"],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    target = probe / TARGET_FILE
    target.write_bytes(completed.stdout)


def _probe_environment(probe: Path) -> dict[str, str]:
    env = os.environ.copy()
    probe_src = str((probe / "src").resolve())
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = probe_src if not existing else probe_src + os.pathsep + existing
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONUNBUFFERED"] = "1"
    return env


def _verify_import_source(probe: Path, env: dict[str, str]) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import pixelscope.ui.plots_dock_title as m; print(m.__file__)",
        ],
        cwd=probe,
        env=env,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    imported = Path(completed.stdout.strip()).resolve()
    expected = (probe / TARGET_FILE).resolve()
    if os.path.normcase(str(imported)) != os.path.normcase(str(expected)):
        raise RuntimeError(
            "Probe imported the wrong source tree. "
            f"Expected {expected}, imported {imported}. Aborting to avoid a false result."
        )


def _classify_exit_code(returncode: int) -> str:
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


def _run_pytest(probe: Path, env: dict[str, str], log_path: Path) -> tuple[int, list[str]]:
    command = [sys.executable, "-m", "pytest", "-q"]
    tail: deque[str] = deque(maxlen=40)
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        process = subprocess.Popen(
            command,
            cwd=probe,
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
            log.write(line)
            log.flush()
            tail.append(line.rstrip())
        returncode = process.wait()
    return returncode, list(tail)


def _write_probe_metadata(repo: Path, probe: Path, output_dir: Path) -> None:
    status = _git(probe, "status", "--short", capture=True).stdout
    diff = _git(probe, "diff", "--", TARGET_FILE.as_posix(), capture=True).stdout
    bad_blob = _git(
        repo, "rev-parse", f"{FIRST_BAD_MERGE}:{TARGET_FILE.as_posix()}", capture=True
    ).stdout.strip()
    good_blob = _git(
        repo, "rev-parse", f"{GOOD_BASELINE}:{TARGET_FILE.as_posix()}", capture=True
    ).stdout.strip()
    metadata = (
        f"first_bad_merge={FIRST_BAD_MERGE}\n"
        f"good_baseline={GOOD_BASELINE}\n"
        f"target={TARGET_FILE.as_posix()}\n"
        f"bad_blob={bad_blob}\n"
        f"good_blob={good_blob}\n"
        f"python={sys.executable}\n"
        f"probe_status:\n{status}\n"
    )
    (output_dir / "probe_metadata.txt").write_text(metadata, encoding="utf-8")
    (output_dir / "production_revert.patch").write_text(diff, encoding="utf-8")


def _overall_verdict(results: list[str]) -> str:
    if any("HEAP_CORRUPTION" in result for result in results):
        return "HEAP_CORRUPTION_REPRODUCED"
    if any("ACCESS_VIOLATION" in result or "NATIVE_CRASH" in result for result in results):
        return "OTHER_NATIVE_CRASH_REPRODUCED"
    completed = {"PASS", "PYTEST_COMPLETED_WITH_FAILURES"}
    if results and all(result in completed for result in results):
        return "NO_NATIVE_CRASH_OBSERVED"
    return "INCONCLUSIVE"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a PR #85 A/B lifecycle probe: keep the merged PR #85 tree/tests, but replace "
            "plots_dock_title.py with the last known-good PR #83 version."
        )
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=3,
        help="Number of fresh-process full-suite runs (default: 3).",
    )
    parser.add_argument(
        "--keep-worktree",
        action="store_true",
        help="Keep the detached diagnostic worktree for manual inspection.",
    )
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")

    repo = _repo_root()
    _require_commit(repo, GOOD_BASELINE)
    _require_commit(repo, FIRST_BAD_MERGE)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = Path(tempfile.gettempdir()) / f"pixelscope-pr85-lifecycle-{stamp}"
    probe = output_dir / "probe"
    logs = output_dir / "logs"
    logs.mkdir(parents=True, exist_ok=False)

    print("PR #85 Qt lifecycle A/B diagnostic")
    print(f"Output: {output_dir}")
    print(f"Python: {sys.executable}")
    print(f"Probe base: {FIRST_BAD_MERGE[:8]}")
    print(f"Production file source: {GOOD_BASELINE[:8]}:{TARGET_FILE.as_posix()}")
    print("The current checkout is not modified.\n")

    worktree_added = False
    results: list[str] = []
    try:
        _git(repo, "worktree", "add", "--detach", str(probe), FIRST_BAD_MERGE)
        worktree_added = True
        _replace_with_good_baseline(repo, probe)
        _write_probe_metadata(repo, probe, output_dir)
        env = _probe_environment(probe)
        _verify_import_source(probe, env)

        for index in range(1, args.repeats + 1):
            log_path = logs / f"full-suite-{index}.log"
            print(f"[{index}/{args.repeats}] full pytest: running")
            returncode, tail = _run_pytest(probe, env, log_path)
            result = _classify_exit_code(returncode)
            results.append(result)
            print(f"[{index}/{args.repeats}] result: {result} (exit={returncode})")
            if result not in {"PASS", "PYTEST_COMPLETED_WITH_FAILURES"}:
                print("Last output lines:")
                for line in tail[-12:]:
                    print(f"  {line}")

        verdict = _overall_verdict(results)
        summary = [
            "PR85 lifecycle A/B diagnostic summary",
            f"probe={FIRST_BAD_MERGE[:8]} + {TARGET_FILE.as_posix()}@{GOOD_BASELINE[:8]}",
            *(f"run_{index}={result}" for index, result in enumerate(results, start=1)),
            f"verdict={verdict}",
            "",
            "Interpretation:",
            "- NO_NATIVE_CRASH_OBSERVED: PR #85 production delta is strongly implicated.",
            "- HEAP_CORRUPTION_REPRODUCED: reverting this production file is insufficient.",
            "- PYTEST_COMPLETED_WITH_FAILURES is expected to be possible because PR #85 tests",
            "  remain while the production implementation is reverted; it still proves pytest",
            "  completed without a native process crash for that run.",
        ]
        (output_dir / "SUMMARY.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")

        print("\n=== RESULT TO SHARE ===")
        print(f"FULL_REVERT_PROBE={verdict}")
        for index, result in enumerate(results, start=1):
            print(f"RUN_{index}={result}")
        print(f"Local logs: {output_dir}")
        return 0 if verdict == "NO_NATIVE_CRASH_OBSERVED" else 2
    finally:
        if worktree_added and not args.keep_worktree:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(probe)],
                cwd=repo,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                ["git", "worktree", "prune"],
                cwd=repo,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )


if __name__ == "__main__":
    raise SystemExit(main())
