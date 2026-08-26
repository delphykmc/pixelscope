from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_installer_release import (  # noqa: E402
    find_iscc,
    inno_major_version,
    validate_iscc,
)
from scripts.distribution_contract import RELEASE_ROOT, release_stem  # noqa: E402
from scripts.release_contract import REPO_ROOT, release_version  # noqa: E402
from scripts.validate_release_bundle import validate_release_bundle  # noqa: E402


def _run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    print(f"+ {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=REPO_ROOT, env=env, check=True)


def _capture(command: list[str], *, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        errors="replace",
        check=True,
    )
    return result.stdout.strip() or result.stderr.strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_python(path: Path, *, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"{label} Python does not exist: {resolved}")
    return resolved


def _source_commit() -> str:
    return _capture(["git", "rev-parse", "HEAD"])


def _require_clean_worktree() -> None:
    status = _capture(["git", "status", "--porcelain", "--untracked-files=normal"])
    if status:
        raise RuntimeError(
            "Release candidates must be built from a clean source worktree. "
            "Commit/stash source changes before retrying."
        )


def _release_note_source(version: str) -> Path:
    releases_dir = REPO_ROOT / "docs" / "releases"
    matches = sorted(releases_dir.glob(f"*-v{version}.md"))
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one dated release-note source for v{version}; found {matches}"
        )
    return matches[0]


def _render_release_notes(source: Path, destination: Path, *, commit: str) -> None:
    text = source.read_text(encoding="utf-8")
    marker = "{{SOURCE_COMMIT}}"
    if marker not in text:
        raise RuntimeError(f"Release-note source is missing {marker}: {source}")
    rendered = text.replace(marker, commit)
    if marker in rendered:
        raise RuntimeError("Release-note source commit marker was not fully rendered")
    destination.write_text(rendered, encoding="utf-8")


def _run_repository_validation(dev_python: Path) -> None:
    _run([str(dev_python), "scripts/check_docs.py"])
    _run(
        [
            str(dev_python),
            "-m",
            "pytest",
            "-q",
            "tests/unit/test_release_candidate.py",
            "tests/unit/test_release_distribution.py",
        ]
    )
    _run([str(dev_python), "-m", "pytest", "-q"])
    _run([str(dev_python), "-m", "ruff", "check", "."])
    _run([str(dev_python), "-m", "mypy", "src"])
    _run([str(dev_python), "-m", "pip", "check"])
    _run(["git", "diff", "--check"])


def _run_release_pipeline(release_python: Path, compiler: Path) -> tuple[Path, ...]:
    env = os.environ.copy()
    env["ISCC_PATH"] = str(compiler)

    _run([str(release_python), "-m", "pip", "check"], env=env)
    _run([str(release_python), "scripts/build_release.py"], env=env)
    _run([str(release_python), "scripts/validate_release_artifact.py"], env=env)
    _run([str(release_python), "scripts/smoke_packaged_release.py"], env=env)
    _run([str(release_python), "scripts/build_portable_release.py"], env=env)
    _run([str(release_python), "scripts/smoke_portable_release.py"], env=env)
    _run(
        [
            str(release_python),
            "scripts/build_installer_release.py",
            "--iscc",
            str(compiler),
        ],
        env=env,
    )
    _run([str(release_python), "scripts/smoke_installer_release.py"], env=env)
    _run([str(release_python), "scripts/validate_release_bundle.py"], env=env)
    return validate_release_bundle()


def _stage_candidate(
    artifacts: tuple[Path, ...],
    *,
    version: str,
    commit: str,
    release_python: Path,
    compiler: Path,
) -> Path:
    stage_root = RELEASE_ROOT / "candidate" / release_stem(version)
    if stage_root.exists():
        shutil.rmtree(stage_root)
    stage_root.mkdir(parents=True, exist_ok=True)

    staged_artifacts: dict[str, dict[str, object]] = {}
    for artifact in artifacts:
        destination = stage_root / artifact.name
        shutil.copy2(artifact, destination)
        staged_artifacts[artifact.name] = {
            "size": destination.stat().st_size,
            "sha256": _sha256(destination),
        }

    notes_source = _release_note_source(version)
    _render_release_notes(notes_source, stage_root / "RELEASE_NOTES.md", commit=commit)

    provenance = {
        "schema_version": 1,
        "product": "PixelScope",
        "version": version,
        "source_commit": commit,
        "built_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "release_python_executable": release_python.name,
        "release_python_version": _capture([str(release_python), "--version"]),
        "pyinstaller_version": _capture(
            [str(release_python), "-m", "PyInstaller", "--version"]
        ),
        "inno_compiler_executable": compiler.name,
        "inno_compiler_major": inno_major_version(compiler),
        "inno_compiler_sha256": _sha256(compiler),
        "release_note_source": notes_source.relative_to(REPO_ROOT).as_posix(),
        "artifacts": staged_artifacts,
    }
    (stage_root / "release-provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return stage_root


def build_release_candidate(
    *,
    dev_python: Path,
    release_python: Path,
    iscc: Path | None = None,
) -> Path:
    if sys.platform != "win32":
        raise RuntimeError("P7-C release-candidate builds are supported only on Windows")

    dev_python = _resolve_python(dev_python, label="development")
    release_python = _resolve_python(release_python, label="release")
    compiler = find_iscc(iscc)
    validate_iscc(compiler)

    _require_clean_worktree()
    commit = _source_commit()
    version = release_version()
    _release_note_source(version)

    if RELEASE_ROOT.exists():
        shutil.rmtree(RELEASE_ROOT)

    _run_repository_validation(dev_python)
    _require_clean_worktree()
    artifacts = _run_release_pipeline(release_python, compiler)
    stage_root = _stage_candidate(
        artifacts,
        version=version,
        commit=commit,
        release_python=release_python,
        compiler=compiler,
    )
    print(f"PixelScope release candidate PASS: {stage_root.resolve()}")
    return stage_root


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build and validate an owner-local PixelScope release candidate"
    )
    parser.add_argument(
        "--dev-python",
        type=Path,
        default=REPO_ROOT / ".venv" / "Scripts" / "python.exe",
        help="development environment Python used for repository validation",
    )
    parser.add_argument(
        "--release-python",
        type=Path,
        default=REPO_ROOT / ".venv-release" / "Scripts" / "python.exe",
        help="release environment Python used for packaging and artifact smoke",
    )
    parser.add_argument(
        "--iscc",
        type=Path,
        default=None,
        help="supported Inno Setup ISCC.exe; otherwise use existing P7-B discovery",
    )
    args = parser.parse_args()
    build_release_candidate(
        dev_python=args.dev_python,
        release_python=args.release_python,
        iscc=args.iscc,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
