from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.distribution_contract import (  # noqa: E402
    MANIFEST_MEMBER_NAME,
    NOTICE_MEMBER_NAME,
    installer_path,
    load_payload_manifest,
    validate_payload_manifest,
)
from scripts.smoke_packaged_release import smoke_executable  # noqa: E402
from scripts.validate_release_artifact import validate_artifact  # noqa: E402


def _run_checked(command: list[str], *, cwd: Path) -> None:
    result = subprocess.run(command, cwd=cwd, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed with exit code {result.returncode}: {command[0]}"
        )


def _silent_uninstall(uninstaller: Path, install_root: Path) -> None:
    _run_checked(
        [
            str(uninstaller),
            "/VERYSILENT",
            "/SUPPRESSMSGBOXES",
            "/NORESTART",
        ],
        cwd=install_root,
    )


def _wait_for_payload_removal(executable: Path, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while executable.exists() and time.monotonic() < deadline:
        time.sleep(0.1)
    if executable.exists():
        raise RuntimeError(f"Installer uninstall left the application payload behind: {executable}")


def smoke_installer_release(setup_path: Path) -> None:
    if sys.platform != "win32":
        raise RuntimeError("P7-B installer smoke is supported only on Windows")
    setup_path = setup_path.resolve()
    if not setup_path.is_file():
        raise FileNotFoundError(setup_path)

    with tempfile.TemporaryDirectory(prefix="pixelscope-installer-") as temp_dir:
        install_root = Path(temp_dir) / "installed" / "PixelScope"
        executable = install_root / "PixelScope.exe"
        uninstaller = install_root / "unins000.exe"
        installed = False
        try:
            _run_checked(
                [
                    str(setup_path),
                    "/VERYSILENT",
                    "/SUPPRESSMSGBOXES",
                    "/NORESTART",
                    "/SP-",
                    f"/DIR={install_root}",
                ],
                cwd=setup_path.parent,
            )
            installed = True

            manifest_path = install_root / MANIFEST_MEMBER_NAME
            notice_path = install_root / NOTICE_MEMBER_NAME
            if not manifest_path.is_file():
                raise RuntimeError("Installed PixelScope is missing release-manifest.json")
            if not notice_path.is_file() or notice_path.stat().st_size == 0:
                raise RuntimeError("Installed PixelScope is missing THIRD_PARTY_NOTICES.txt")

            manifest = load_payload_manifest(manifest_path)
            validate_payload_manifest(
                install_root,
                manifest,
                allow_distribution_metadata=True,
            )
            validate_artifact(install_root)
            smoke_executable(executable)

            if not uninstaller.is_file():
                raise RuntimeError("Installed PixelScope is missing the Inno Setup uninstaller")
            _silent_uninstall(uninstaller, install_root)
            installed = False
            _wait_for_payload_removal(executable)
        finally:
            if installed and uninstaller.is_file():
                try:
                    _silent_uninstall(uninstaller, install_root)
                except RuntimeError:
                    pass


def main() -> int:
    setup = installer_path()
    smoke_installer_release(setup)
    print(f"PixelScope installer smoke PASS: {setup.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
