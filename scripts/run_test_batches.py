from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

DEFAULT_UI_BATCH_SIZE = 8
DEFAULT_TIMEOUT_SECONDS = 600.0
DEFAULT_ARTIFACTS_DIR = Path(".test-results") / "batched"
NON_UI_PATHS = (
    "tests/unit",
    "tests/integration",
    "tests/performance",
)


@dataclass(frozen=True)
class TestBatch:
    name: str
    paths: tuple[str, ...]


@dataclass(frozen=True)
class BatchResult:
    batch: TestBatch
    status: str
    returncode: int | None
    elapsed_seconds: float
    log_path: Path
    junit_path: Path


class PositiveInt(argparse.Action):
    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: object,
        option_string: str | None = None,
    ) -> None:
        try:
            value = int(str(values))
        except ValueError:
            parser.error(f"{option_string or self.dest} must be an integer")
        if value <= 0:
            parser.error(f"{option_string or self.dest} must be > 0")
        setattr(namespace, self.dest, value)


class PositiveFloat(argparse.Action):
    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: object,
        option_string: str | None = None,
    ) -> None:
        try:
            value = float(str(values))
        except ValueError:
            parser.error(f"{option_string or self.dest} must be a number")
        if value <= 0:
            parser.error(f"{option_string or self.dest} must be > 0")
        setattr(namespace, self.dest, value)


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def discover_ui_test_files(repo_root: Path) -> list[str]:
    ui_root = repo_root / "tests" / "ui"
    return sorted(path.relative_to(repo_root).as_posix() for path in ui_root.rglob("test_*.py"))


def chunked(items: Sequence[str], size: int) -> list[tuple[str, ...]]:
    if size <= 0:
        raise ValueError("batch size must be > 0")
    return [tuple(items[index : index + size]) for index in range(0, len(items), size)]


def build_batches(repo_root: Path, *, ui_batch_size: int, scope: str) -> list[TestBatch]:
    batches: list[TestBatch] = []
    if scope in {"all", "non-ui"}:
        existing = tuple(path for path in NON_UI_PATHS if (repo_root / path).exists())
        if existing:
            batches.append(TestBatch(name="non-ui", paths=existing))

    if scope in {"all", "ui"}:
        ui_files = discover_ui_test_files(repo_root)
        for index, paths in enumerate(chunked(ui_files, ui_batch_size), start=1):
            batches.append(TestBatch(name=f"ui-{index:03d}", paths=paths))
    return batches


def classify_returncode(returncode: int, *, platform_name: str = os.name) -> str:
    if returncode == 0:
        return "passed"
    if returncode == 1:
        return "pytest-failed"
    if returncode == 2:
        return "pytest-interrupted"
    if returncode == 3:
        return "pytest-internal-error"
    if returncode == 4:
        return "pytest-usage-error"
    if returncode == 5:
        return "no-tests-collected"
    if platform_name == "nt" and (returncode & 0xFFFFFFFF) >= 0xC0000000:
        return "native-crash"
    if platform_name != "nt" and returncode < 0:
        return "signal-crash"
    return "process-error"


def format_returncode(returncode: int | None, *, platform_name: str = os.name) -> str:
    if returncode is None:
        return "n/a"
    if platform_name == "nt" and (returncode & 0xFFFFFFFF) >= 0xC0000000:
        return f"{returncode} (0x{returncode & 0xFFFFFFFF:08X})"
    return str(returncode)


def _output_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def prepare_artifacts(artifacts_dir: Path) -> None:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    for pattern in ("*.log", "*.xml", "summary.txt"):
        for path in artifacts_dir.glob(pattern):
            if path.is_file():
                path.unlink()


def run_batch(
    repo_root: Path,
    batch: TestBatch,
    *,
    artifacts_dir: Path,
    timeout_seconds: float,
) -> BatchResult:
    log_path = artifacts_dir / f"{batch.name}.log"
    junit_path = artifacts_dir / f"{batch.name}.xml"
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        *batch.paths,
        f"--junitxml={junit_path}",
    ]
    environment = os.environ.copy()
    environment.setdefault("PYTHONUNBUFFERED", "1")

    print(f"\n=== {batch.name}: {len(batch.paths)} path(s) ===", flush=True)
    print(" ".join(command), flush=True)
    started = time.monotonic()
    returncode: int | None
    try:
        completed = subprocess.run(
            command,
            cwd=repo_root,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
        output = completed.stdout or ""
        returncode = completed.returncode
        status = classify_returncode(returncode)
    except subprocess.TimeoutExpired as exc:
        output = _output_text(exc.stdout)
        if exc.stderr:
            output += _output_text(exc.stderr)
        returncode = None
        status = "timeout"

    elapsed = time.monotonic() - started
    log_path.write_text(output, encoding="utf-8")
    if output:
        print(output.rstrip(), flush=True)
    print(
        f"[{batch.name}] {status} in {elapsed:.1f}s; "
        f"returncode={format_returncode(returncode)}",
        flush=True,
    )
    return BatchResult(
        batch=batch,
        status=status,
        returncode=returncode,
        elapsed_seconds=elapsed,
        log_path=log_path,
        junit_path=junit_path,
    )


def write_summary(results: Sequence[BatchResult], artifacts_dir: Path) -> Path:
    summary_path = artifacts_dir / "summary.txt"
    lines = ["PixelScope fresh-process test batches", ""]
    for result in results:
        lines.append(
            f"{result.batch.name}: {result.status}; "
            f"returncode={format_returncode(result.returncode)}; "
            f"elapsed={result.elapsed_seconds:.1f}s; "
            f"paths={len(result.batch.paths)}"
        )
    failed = [result for result in results if result.status != "passed"]
    lines.extend(
        (
            "",
            f"batches={len(results)}",
            f"failed_or_incomplete={len(failed)}",
            f"overall={'PASS' if not failed else 'FAIL'}",
        )
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary_path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run PixelScope tests in deterministic fresh Python processes so long-lived Qt "
            "wrapper state cannot accumulate across the complete functional suite."
        )
    )
    parser.add_argument(
        "--scope",
        choices=("all", "non-ui", "ui"),
        default="all",
        help="Select all tests, only non-UI tests, or only UI batches.",
    )
    parser.add_argument(
        "--ui-batch-size",
        action=PositiveInt,
        default=DEFAULT_UI_BATCH_SIZE,
        help=f"Number of UI test files per fresh process (default: {DEFAULT_UI_BATCH_SIZE}).",
    )
    parser.add_argument(
        "--timeout-seconds",
        action=PositiveFloat,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=(
            "Subprocess timeout for one batch; timeout is recorded as a failed/incomplete "
            f"batch (default: {int(DEFAULT_TIMEOUT_SECONDS)})."
        ),
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=DEFAULT_ARTIFACTS_DIR,
        help=f"Per-batch logs/JUnit output directory (default: {DEFAULT_ARTIFACTS_DIR}).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print the deterministic batch plan without running pytest.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = repository_root()
    batches = build_batches(
        repo_root,
        ui_batch_size=args.ui_batch_size,
        scope=args.scope,
    )
    if not batches:
        print("No test batches were discovered.", file=sys.stderr)
        return 2

    if args.list:
        for batch in batches:
            print(f"{batch.name} ({len(batch.paths)} path(s))")
            for path in batch.paths:
                print(f"  {path}")
        return 0

    artifacts_dir = args.artifacts_dir
    if not artifacts_dir.is_absolute():
        artifacts_dir = repo_root / artifacts_dir
    prepare_artifacts(artifacts_dir)

    results = [
        run_batch(
            repo_root,
            batch,
            artifacts_dir=artifacts_dir,
            timeout_seconds=args.timeout_seconds,
        )
        for batch in batches
    ]
    summary_path = write_summary(results, artifacts_dir)
    failed = [result for result in results if result.status != "passed"]

    print("\n=== batched test summary ===")
    for result in results:
        print(
            f"{result.batch.name}: {result.status} "
            f"({result.elapsed_seconds:.1f}s, rc={format_returncode(result.returncode)})"
        )
    print(f"summary: {summary_path}")
    if failed:
        print(f"overall: FAIL ({len(failed)} failed/incomplete batch(es))")
        return 1
    print("overall: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
