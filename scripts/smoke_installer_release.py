from __future__ import annotations

import contextlib
import subprocess
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath

if sys.platform == "win32":
    import winreg
else:
    winreg = None  # type: ignore[assignment]

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_installer_release import (  # noqa: E402
    SMOKE_APP_ID,
    build_installer_release,
)
from scripts.distribution_contract import (  # noqa: E402
    MANIFEST_MEMBER_NAME,
    NOTICE_MEMBER_NAME,
    load_payload_manifest,
    validate_payload_manifest,
)
from scripts.release_contract import release_version  # noqa: E402
from scripts.smoke_packaged_release import smoke_executable  # noqa: E402
from scripts.validate_release_artifact import validate_artifact  # noqa: E402

_UNINSTALL_ROOT = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"


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


def _uninstall_key_path(app_id: str) -> str:
    return f"{_UNINSTALL_ROOT}\\{app_id}_is1"


def _uninstall_registration_exists(app_id: str) -> bool:
    if winreg is None:
        raise RuntimeError("Installer registration checks are supported only on Windows")
    access = winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0)
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            _uninstall_key_path(app_id),
            0,
            access,
        ):
            return True
    except FileNotFoundError:
        return False


def _installer_owned_files(install_root: Path) -> frozenset[str]:
    return frozenset(
        path.relative_to(install_root).as_posix()
        for path in install_root.glob("unins*")
        if path.is_file()
    )


def _manifest_owned_paths(root: Path, manifest: dict[str, object]) -> tuple[Path, ...]:
    raw_files = manifest.get("files")
    if not isinstance(raw_files, list):
        raise RuntimeError("Installed release manifest has no file inventory")
    paths: list[Path] = []
    for entry in raw_files:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise RuntimeError("Installed release manifest contains an invalid file entry")
        relative = PurePosixPath(entry["path"])
        paths.append(root / Path(*relative.parts))
    return tuple(paths)


def _wait_for_install_cleanup(
    install_root: Path,
    owned_paths: tuple[Path, ...],
    *,
    app_id: str,
    timeout: float = 10.0,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        payload_left = any(path.exists() for path in owned_paths)
        inno_left = any(path.is_file() for path in install_root.glob("unins*"))
        registered = _uninstall_registration_exists(app_id)
        if not payload_left and not inno_left and not registered and not install_root.exists():
            return
        time.sleep(0.1)

    leftovers = [str(path) for path in owned_paths if path.exists()]
    leftovers.extend(str(path) for path in install_root.glob("unins*") if path.is_file())
    if install_root.exists():
        leftovers.append(str(install_root))
    if _uninstall_registration_exists(app_id):
        leftovers.append(f"HKCU\\{_uninstall_key_path(app_id)}")
    raise RuntimeError(f"Installer uninstall left smoke artifacts behind: {leftovers}")


def smoke_installer_release(setup_path: Path, *, app_id: str = SMOKE_APP_ID) -> None:
    if sys.platform != "win32":
        raise RuntimeError("P7-B installer smoke is supported only on Windows")
    setup_path = setup_path.resolve()
    if not setup_path.is_file():
        raise FileNotFoundError(setup_path)
    if _uninstall_registration_exists(app_id):
        raise RuntimeError(
            "A stale PixelScope installer-smoke registration already exists; "
            "clean that disposable test install before retrying"
        )

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
                raise RuntimeError(
                    "Installed PixelScope is missing THIRD_PARTY_NOTICES.txt"
                )
            if not _uninstall_registration_exists(app_id):
                raise RuntimeError("Installer smoke did not create its disposable registration")

            manifest = load_payload_manifest(manifest_path)
            validate_payload_manifest(
                install_root,
                manifest,
                allow_distribution_metadata=True,
                allowed_extra_names=_installer_owned_files(install_root),
                expected_version=release_version(),
            )
            validate_artifact(install_root)
            smoke_executable(executable)

            if not uninstaller.is_file():
                raise RuntimeError(
                    "Installed PixelScope is missing the Inno Setup uninstaller"
                )
            owned_paths = _manifest_owned_paths(install_root, manifest) + (
                manifest_path,
                notice_path,
            )
            _silent_uninstall(uninstaller, install_root)
            installed = False
            _wait_for_install_cleanup(install_root, owned_paths, app_id=app_id)
        finally:
            if installed and uninstaller.is_file():
                with contextlib.suppress(RuntimeError):
                    _silent_uninstall(uninstaller, install_root)


def main() -> int:
    setup = build_installer_release(app_id=SMOKE_APP_ID, smoke_build=True)
    try:
        smoke_installer_release(setup)
        print(f"PixelScope installer smoke PASS: {setup.resolve()}")
    finally:
        setup.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
