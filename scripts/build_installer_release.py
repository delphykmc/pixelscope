from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_third_party_notices import write_third_party_notices  # noqa: E402
from scripts.distribution_contract import (  # noqa: E402
    RELEASE_ROOT,
    installer_path,
    release_stem,
    write_payload_manifest,
)
from scripts.release_contract import (  # noqa: E402
    APP_DIR,
    REPO_ROOT,
    release_version,
    windows_version_tuple,
)
from scripts.validate_release_artifact import validate_artifact  # noqa: E402

INNO_SCRIPT = REPO_ROOT / "packaging" / "installer" / "pixelscope.iss"
PRODUCTION_APP_ID = "{6FA0AB08-AB41-4F77-93E8-16CE6FF53E5C}"
SMOKE_APP_ID = "PixelScope.P7B.Smoke"
_MIN_INNO_VERSION = (6, 1, 0, 0)
_MAX_INNO_VERSION_EXCLUSIVE = (8, 0, 0, 0)
_VERSION_TEXT_RE = re.compile(
    r"(?<!\d)(\d+)\.(\d+)(?:\.(\d+))?(?:\.(\d+))?(?!\d)"
)


def smoke_installer_path(version: str | None = None) -> Path:
    return RELEASE_ROOT / f"{release_stem(version)}-smoke-setup.exe"


def _candidate_iscc_paths() -> tuple[Path, ...]:
    candidates: list[Path] = []
    env_path = os.environ.get("ISCC_PATH")
    if env_path:
        candidates.append(Path(env_path))
    path_hit = shutil.which("ISCC.exe") or shutil.which("iscc")
    if path_hit:
        candidates.append(Path(path_hit))
    for env_name in ("ProgramFiles(x86)", "ProgramFiles"):
        root = os.environ.get(env_name)
        if not root:
            continue
        for major in (7, 6):
            candidates.append(Path(root) / f"Inno Setup {major}" / "ISCC.exe")
    return tuple(candidates)


def find_iscc(explicit: Path | None = None) -> Path:
    candidates = (explicit,) if explicit is not None else _candidate_iscc_paths()
    for candidate in candidates:
        if candidate is None:
            continue
        resolved = candidate.expanduser().resolve()
        if resolved.is_file():
            return resolved
    raise FileNotFoundError(
        "Inno Setup ISCC.exe was not found; pass --iscc, set ISCC_PATH, "
        "or install a supported Inno Setup compiler"
    )


def _parse_version_text(value: str | bytes) -> tuple[int, int, int, int] | None:
    text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
    match = _VERSION_TEXT_RE.search(text)
    if match is None:
        return None
    return tuple(int(part or 0) for part in match.groups())  # type: ignore[return-value]


def _version_from_pe_info(pe: Any) -> tuple[int, int, int, int] | None:
    for group in getattr(pe, "FileInfo", None) or ():
        file_infos = group if isinstance(group, (list, tuple)) else (group,)
        for file_info in file_infos:
            key = getattr(file_info, "Key", None)
            if key not in (b"StringFileInfo", "StringFileInfo"):
                continue
            for table in getattr(file_info, "StringTable", None) or ():
                entries = getattr(table, "entries", None) or {}
                for entry_name in (
                    b"FileVersion",
                    "FileVersion",
                    b"ProductVersion",
                    "ProductVersion",
                ):
                    if entry_name not in entries:
                        continue
                    parsed = _parse_version_text(entries[entry_name])
                    if parsed is not None and any(parsed):
                        return parsed

    fixed_entries = getattr(pe, "VS_FIXEDFILEINFO", None) or ()
    if fixed_entries:
        info = fixed_entries[0]
        fixed_version = (
            (int(info.FileVersionMS) >> 16) & 0xFFFF,
            int(info.FileVersionMS) & 0xFFFF,
            (int(info.FileVersionLS) >> 16) & 0xFFFF,
            int(info.FileVersionLS) & 0xFFFF,
        )
        if any(fixed_version):
            return fixed_version
    return None


def _inno_file_version(iscc: Path) -> tuple[int, int, int, int]:
    try:
        import pefile
    except ImportError as exc:
        raise RuntimeError(
            "pefile is required to validate the Inno Setup compiler version; "
            "install requirements/release.txt"
        ) from exc

    pe = pefile.PE(str(iscc), fast_load=False)
    try:
        version = _version_from_pe_info(pe)
        if version is None:
            raise RuntimeError(f"Unable to read Inno Setup file version from {iscc}")
        return version
    finally:
        pe.close()


def validate_inno_version(version: tuple[int, int, int, int]) -> None:
    if not _MIN_INNO_VERSION <= version < _MAX_INNO_VERSION_EXCLUSIVE:
        found = ".".join(str(part) for part in version)
        raise RuntimeError(f"P7-B requires Inno Setup >=6.1,<8; found {found}")


def validate_iscc(iscc: Path) -> None:
    validate_inno_version(_inno_file_version(iscc))


def _ispp_define(name: str, value: str) -> str:
    if '"' in value or "\n" in value or "\r" in value:
        raise ValueError(f"Unsafe Inno Setup define value for {name}")
    return f"-d{name}={value}"


def installer_command(
    iscc: Path,
    *,
    app_id: str | None = None,
    smoke_build: bool = False,
) -> list[str]:
    version = release_version()
    version_parts = windows_version_tuple(version)
    file_version = ".".join(str(part) for part in version_parts)
    command = [
        str(iscc),
        "/Qp",
        _ispp_define("AppVersion", version),
        _ispp_define("AppFileVersion", file_version),
        _ispp_define("AppVersionMajor", str(version_parts[0])),
        _ispp_define("AppVersionMinor", str(version_parts[1])),
        _ispp_define("AppVersionRevision", str(version_parts[2])),
        _ispp_define("AppVersionBuild", str(version_parts[3])),
    ]
    if app_id is not None:
        command.append(_ispp_define("AppIdValue", app_id))
    if smoke_build:
        command.append(_ispp_define("SmokeBuild", "1"))
    command.append(str(INNO_SCRIPT.resolve()))
    return command


def build_installer_release(
    iscc: Path | None = None,
    *,
    app_id: str | None = None,
    smoke_build: bool = False,
) -> Path:
    if sys.platform != "win32":
        raise RuntimeError("P7-B installer compilation is supported only on Windows")
    if smoke_build and app_id is None:
        raise ValueError("Smoke installer builds require a disposable AppId override")

    validate_artifact(APP_DIR)
    compiler = find_iscc(iscc)
    validate_iscc(compiler)
    RELEASE_ROOT.mkdir(parents=True, exist_ok=True)
    write_payload_manifest(APP_DIR)
    write_third_party_notices()

    output = smoke_installer_path() if smoke_build else installer_path()
    output.unlink(missing_ok=True)
    subprocess.run(
        installer_command(compiler, app_id=app_id, smoke_build=smoke_build),
        cwd=REPO_ROOT,
        check=True,
    )
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(f"Inno Setup did not produce the expected installer: {output}")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the PixelScope Inno Setup installer")
    parser.add_argument(
        "--iscc",
        type=Path,
        default=None,
        help="path to ISCC.exe (otherwise ISCC_PATH/PATH/common install paths)",
    )
    args = parser.parse_args()
    output = build_installer_release(args.iscc)
    print(f"PixelScope installer written: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
