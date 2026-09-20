from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.release_contract import (  # noqa: E402
    BUILD_ROOT,
    DIST_ROOT,
    REPO_ROOT,
    SPEC_PATH,
    validate_release_host,
    write_windows_version_info,
)
from scripts.build_user_guide import build_user_guide  # noqa: E402
from scripts.validate_release_artifact import validate_artifact  # noqa: E402


def pyinstaller_command() -> list[str]:
    """Return the canonical PyInstaller invocation as an argument list."""

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
        str(SPEC_PATH),
    ]


def documentation_python() -> Path:
    """Choose build-time MkDocs, separate from the frozen application runtime."""
    explicit = os.environ.get("PIXELSCOPE_DOCS_PYTHON")
    if explicit:
        return Path(explicit).expanduser().resolve()
    dev_python = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    return dev_python if dev_python.is_file() else Path(sys.executable)


def main() -> int:
    validate_release_host()
    site = build_user_guide(python=documentation_python())
    write_windows_version_info()
    subprocess.run(pyinstaller_command(), cwd=REPO_ROOT, check=True)

    # The frozen Help lookup is executable-relative, not a PyInstaller _MEIPASS
    # resource. Copy after COLLECT and before artifact/manifest validation.
    help_root = DIST_ROOT / "PixelScope" / "help"
    if help_root.exists():
        shutil.rmtree(help_root)
    shutil.copytree(site, help_root)
    validate_artifact()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
