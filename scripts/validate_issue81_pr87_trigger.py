from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

BASE_MAIN = "d51064d62291ed4057f2ddc215bc015143e634ef"
PR87_TRIGGER = "d6e699f21d5756ffaa043c94ba43fd0584a75b2c"

_HEAP_CORRUPTION = 0xC0000374
_ACCESS_VIOLATION = 0xC0000005


def _run(
    cwd: Path,
    command: list[str],
    *,
    check: bool = True,
    capture: bool = False,
    env: dict[str, str] | None = None,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _repo_root() -> Path:
    completed = _run(
        Path.cwd(),
        ["git", "rev-parse", "--show-toplevel"],
        capture=True,
    )
    return Path(completed.stdout.strip()).resolve()


def _git(repo: Path, *args: str, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return _run(repo, ["git", *args], capture=capture)


def _require_commit(repo: Path, ref: str) -> None:
    try:
        _git(repo, "cat-file", "-e", f"{ref}^{{commit}}", capture=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Required commit is unavailable locally: {ref}") from exc


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


def _environment(worktree: Path) -> dict[str, str]:
    env = os.environ.copy()
    source = str((worktree / "src").resolve())
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = source if not existing else source + os.pathsep + existing
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONUNBUFFERED"] = "1"
    return env


def _write_overlay_patch(repo: Path, head: str, patch_path: Path) -> None:
    completed = subprocess.run(
        [
            "git",
            "diff",
            "--binary",
            f"{BASE_MAIN}..{head}",
            "--",
            "src",
            "tests",
        ],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    patch_path.write_bytes(completed.stdout)
    if not completed.stdout:
        raise RuntimeError("Current branch has no src/tests delta relative to the main baseline")


def _apply_overlay(worktree: Path, patch_path: Path) -> None:
    completed = subprocess.run(
        ["git", "apply", "--3way", "--index", str(patch_path)],
        cwd=worktree,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "Unable to overlay the current Issue #81 fix delta onto the PR #87 trigger tree.\n"
            + (completed.stdout or "")
        )


def _verify_trigger_tree(worktree: Path) -> None:
    help_module = worktree / "src/pixelscope/ui/user_guide_help.py"
    application = (worktree / "src/pixelscope/app/application.py").read_text(encoding="utf-8")
    main_window = (worktree / "src/pixelscope/app/main_window.py").read_text(encoding="utf-8")
    if not help_module.is_file():
        raise RuntimeError("PR #87 User Guide module is missing from the validation worktree")
    if "install_user_guide_help(window)" not in application:
        raise RuntimeError("PR #87 production Help installation is missing from the validation worktree")
    if "self._menu_map = menus" not in main_window:
        raise RuntimeError("PR #87 retained menu-wrapper trigger is missing from the validation worktree")


def _run_full_suite(
    worktree: Path,
    env: dict[str, str],
    log_path: Path,
    timeout_seconds: int,
) -> str:
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=worktree,
            env=env,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        log_path.write_text(
            output + f"\n[watchdog] timeout after {timeout_seconds}s\n",
            encoding="utf-8",
            errors="replace",
        )
        return f"HANG_TIMEOUT_{timeout_seconds}S"

    output = completed.stdout or ""
    log_path.write_text(output, encoding="utf-8", errors="replace")
    return _classify(completed.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Overlay the current Issue #81 src/tests delta onto the exact PR #87 crash-trigger "
            "tree and repeat the full pytest suite in fresh processes."
        )
    )
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--keep-worktree", action="store_true")
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    if args.timeout_seconds < 1:
        parser.error("--timeout-seconds must be at least 1")

    repo = _repo_root()
    _require_commit(repo, BASE_MAIN)
    _require_commit(repo, PR87_TRIGGER)
    head = _git(repo, "rev-parse", "HEAD", capture=True).stdout.strip()

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = Path(tempfile.gettempdir()) / f"pixelscope-issue81-pr87-trigger-{stamp}"
    worktree = output_dir / "worktree"
    logs = output_dir / "logs"
    logs.mkdir(parents=True)
    patch_path = output_dir / "issue81-overlay.patch"
    _write_overlay_patch(repo, head, patch_path)

    print("Issue #81 validation on PR #87 trigger tree")
    print(f"Trigger: {PR87_TRIGGER[:8]}")
    print(f"Overlay head: {head[:8]}")
    print(f"Repeats: {args.repeats}")
    print(f"Output: {output_dir}\n")

    added = False
    results: list[str] = []
    try:
        _git(repo, "worktree", "add", "--detach", str(worktree), PR87_TRIGGER)
        added = True
        _apply_overlay(worktree, patch_path)
        _verify_trigger_tree(worktree)
        status = _git(worktree, "status", "--short", capture=True).stdout
        (output_dir / "overlay-status.txt").write_text(status, encoding="utf-8")
        env = _environment(worktree)

        for index in range(1, args.repeats + 1):
            print(f"[{index}/{args.repeats}] full pytest: running", flush=True)
            result = _run_full_suite(
                worktree,
                env,
                logs / f"full-suite-{index:02d}.log",
                args.timeout_seconds,
            )
            results.append(result)
            print(f"[{index}/{args.repeats}] {result}", flush=True)

        native = sum(
            "HEAP_CORRUPTION" in item
            or "ACCESS_VIOLATION" in item
            or item.startswith("NATIVE_CRASH")
            for item in results
        )
        hangs = sum(item.startswith("HANG_TIMEOUT") for item in results)
        passes = sum(item == "PASS" for item in results)
        summary = [
            "Issue #81 / PR #87 trigger validation",
            f"trigger={PR87_TRIGGER}",
            f"overlay_head={head}",
            f"runs={len(results)}",
            f"pass={passes}",
            f"native_crash={native}",
            f"hang={hangs}",
            *(f"run_{index}={item}" for index, item in enumerate(results, start=1)),
        ]
        (output_dir / "SUMMARY.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")

        print("\n=== RESULT TO SHARE ===")
        print(f"RUNS={len(results)}")
        print(f"PASS={passes}")
        print(f"NATIVE_CRASH={native}")
        print(f"HANG={hangs}")
        for index, item in enumerate(results, start=1):
            print(f"RUN_{index}={item}")
        print(f"Local logs: {output_dir}")
        return 0 if passes == len(results) else 2
    finally:
        if added and not args.keep_worktree:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree)],
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
