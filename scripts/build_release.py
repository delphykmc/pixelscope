from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_user_guide import build_user_guide  # noqa: E402
from scripts.release_contract import (  # noqa: E402
    BUILD_ROOT,
    DIST_ROOT,
    REFERENCE_EXECUTABLE_PATH,
    REFERENCE_SPEC_PATH,
    REPO_ROOT,
    SPEC_PATH,
    validate_release_host,
    write_windows_version_info,
)
from scripts.validate_release_artifact import validate_artifact  # noqa: E402


def _target_paths(target: str) -> tuple[Path, Path, str]:
    if target == "core":
        return SPEC_PATH, DIST_ROOT / "PixelScope", "PixelScope.exe"
    if target == "reference":
        return (
            REFERENCE_SPEC_PATH,
            DIST_ROOT / "PixelScopeReference",
            REFERENCE_EXECUTABLE_PATH.name,
        )
    raise ValueError(f"Unknown public package target: {target}")


def pyinstaller_command(target: str = "core") -> list[str]:
    """Return the PyInstaller invocation for one explicit public package target."""

    spec_path, _app_dir, _executable_name = _target_paths(target)
    return [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        "--distpath",
        str(DIST_ROOT),
        "--workpath",
        str(BUILD_ROOT),
        str(spec_path),
    ]


def documentation_python() -> Path:
    """Choose build-time MkDocs, separate from the frozen application runtime."""
    explicit = os.environ.get("PIXELSCOPE_DOCS_PYTHON")
    if explicit:
        return Path(explicit).expanduser().resolve()
    dev_python = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    return dev_python if dev_python.is_file() else Path(sys.executable)


def build_public_target(target: str = "core") -> Path:
    """Build and validate one of the two public PixelScope package modes."""

    validate_release_host()
    _spec_path, app_dir, executable_name = _target_paths(target)
    site = build_user_guide(python=documentation_python())
    write_windows_version_info()
    command = pyinstaller_command() if target == "core" else pyinstaller_command(target)
    subprocess.run(command, cwd=REPO_ROOT, check=True)

    # The frozen Help lookup is executable-relative, not a PyInstaller _MEIPASS
    # resource. Copy after COLLECT and before artifact/manifest validation.
    help_root = app_dir / "help"
    if help_root.exists():
        shutil.rmtree(help_root)
    shutil.copytree(site, help_root)
    # MkDocs' generated 404.html is hosting-only and contains absolute /assets
    # references that cannot resolve when opened from file://.
    (help_root / "404.html").unlink(missing_ok=True)
    if target == "core":
        validate_artifact()
    else:
        if target == "core":
        validate_artifact(app_dir)
    else:
        validate_artifact(app_dir, executable_name=executable_name)
    return app_dir


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a public PixelScope package target")
    parser.add_argument(
        "--target",
        choices=("core", "reference"),
        default="core",
        help="public package mode to build (default: core)",
    )
    args = parser.parse_args([] if arguments is None else arguments)
    output = build_public_target(args.target)
    print(f"Built PixelScope {args.target} package: {output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
