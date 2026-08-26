from __future__ import annotations

import subprocess
import sys

from scripts.release_contract import (
    BUILD_ROOT,
    DIST_ROOT,
    REPO_ROOT,
    SPEC_PATH,
    validate_release_host,
    write_windows_version_info,
)
from scripts.validate_release_artifact import validate_artifact


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


def main() -> int:
    validate_release_host()
    write_windows_version_info()
    subprocess.run(pyinstaller_command(), cwd=REPO_ROOT, check=True)
    validate_artifact()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
