from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_third_party_notices import write_third_party_notices  # noqa: E402
from scripts.distribution_contract import (  # noqa: E402
    RELEASE_ROOT,
    installer_path,
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
_SUPPORTED_INNO_MAJORS = frozenset({6, 7})


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
        for major in sorted(_SUPPORTED_INNO_MAJORS, reverse=True):
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


def inno_major_version(iscc: Path) -> int:
    result = subprocess.run(
        [str(iscc), "/?"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    text = f"{result.stdout}\n{result.stderr}"
    match = re.search(r"Inno Setup\s+(\d+)", text, flags=re.IGNORECASE)
    if match is None:
        raise RuntimeError(f"Unable to determine Inno Setup version from {iscc}")
    return int(match.group(1))


def validate_iscc(iscc: Path) -> None:
    major = inno_major_version(iscc)
    if major not in _SUPPORTED_INNO_MAJORS:
        supported = ", ".join(str(value) for value in sorted(_SUPPORTED_INNO_MAJORS))
        raise RuntimeError(
            f"P7-B requires Inno Setup major {supported}; found major version {major}"
        )


def _ispp_define(name: str, value: str) -> str:
    if '"' in value or "\n" in value or "\r" in value:
        raise ValueError(f"Unsafe Inno Setup define value for {name}")
    return f'-d{name}="{value}"'


def installer_command(iscc: Path) -> list[str]:
    version = release_version()
    file_version = ".".join(str(part) for part in windows_version_tuple(version))
    return [
        str(iscc),
        "/Qp",
        _ispp_define("AppVersion", version),
        _ispp_define("AppFileVersion", file_version),
        str(INNO_SCRIPT.resolve()),
    ]


def build_installer_release(iscc: Path | None = None) -> Path:
    if sys.platform != "win32":
        raise RuntimeError("P7-B installer compilation is supported only on Windows")
    validate_artifact(APP_DIR)
    compiler = find_iscc(iscc)
    validate_iscc(compiler)
    RELEASE_ROOT.mkdir(parents=True, exist_ok=True)
    write_payload_manifest(APP_DIR)
    write_third_party_notices()
    output = installer_path()
    output.unlink(missing_ok=True)
    subprocess.run(installer_command(compiler), cwd=REPO_ROOT, check=True)
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
