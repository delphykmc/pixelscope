from __future__ import annotations

import re
import runpy
import struct
import sys
from pathlib import Path
from typing import Final

REPO_ROOT: Final = Path(__file__).resolve().parents[1]
SOURCE_ROOT: Final = REPO_ROOT / "src"
SPEC_PATH: Final = REPO_ROOT / "packaging" / "pixelscope.spec"
BUILD_ROOT: Final = REPO_ROOT / "build" / "pyinstaller"
GENERATED_ROOT: Final = REPO_ROOT / "build" / "release"
VERSION_INFO_PATH: Final = GENERATED_ROOT / "PixelScope.version.txt"
DIST_ROOT: Final = REPO_ROOT / "dist"
APP_DIR: Final = DIST_ROOT / "PixelScope"
EXECUTABLE_PATH: Final = APP_DIR / "PixelScope.exe"
VERSION_SOURCE: Final = SOURCE_ROOT / "pixelscope" / "version.py"
EXPECTED_PYINSTALLER_VERSIONS: Final = frozenset({"5.7", "5.7.0"})
MIN_RELEASE_PYTHON: Final = (3, 10, 8)
MAX_RELEASE_PYTHON_EXCLUSIVE: Final = (3, 11, 0)


def release_version() -> str:
    """Read the canonical version without importing the application package."""

    namespace = runpy.run_path(str(VERSION_SOURCE))
    version = namespace.get("__version__")
    if not isinstance(version, str) or not version.strip():
        raise RuntimeError(f"Invalid release version in {VERSION_SOURCE}")
    return version.strip()


def windows_version_tuple(version: str | None = None) -> tuple[int, int, int, int]:
    """Convert the leading X.Y.Z release version into Windows file-version fields."""

    value = version or release_version()
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", value)
    if match is None:
        raise ValueError(f"Release version must begin with X.Y.Z: {value!r}")
    parts = tuple(int(part) for part in match.groups())
    if any(part > 65535 for part in parts):
        raise ValueError(f"Windows version components must be <= 65535: {value!r}")
    return parts[0], parts[1], parts[2], 0


def render_windows_version_info(version: str | None = None) -> str:
    """Render a PyInstaller Windows version-resource file from the canonical version."""

    value = version or release_version()
    file_version = windows_version_tuple(value)
    tuple_text = ", ".join(str(part) for part in file_version)
    return f'''# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({tuple_text}),
    prodvers=({tuple_text}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        "040904B0",
        [
          StringStruct("FileDescription", "PixelScope"),
          StringStruct("FileVersion", "{value}"),
          StringStruct("InternalName", "PixelScope"),
          StringStruct("OriginalFilename", "PixelScope.exe"),
          StringStruct("ProductName", "PixelScope"),
          StringStruct("ProductVersion", "{value}")
        ]
      )
    ]),
    VarFileInfo([VarStruct("Translation", [1033, 1200])])
  ]
)
'''


def write_windows_version_info(version: str | None = None) -> Path:
    """Write generated executable metadata outside the source tree."""

    GENERATED_ROOT.mkdir(parents=True, exist_ok=True)
    VERSION_INFO_PATH.write_text(render_windows_version_info(version), encoding="utf-8")
    return VERSION_INFO_PATH


def pyinstaller_version() -> str:
    """Return the installed PyInstaller version or fail with an actionable message."""

    try:
        import PyInstaller
    except ImportError as exc:
        raise RuntimeError(
            "PyInstaller is not installed; install requirements/release.txt first"
        ) from exc
    return str(PyInstaller.__version__)


def validate_release_python(version: tuple[int, int, int]) -> None:
    """Enforce the owner-selected CPython 3.10.8+ release-build baseline."""

    if not MIN_RELEASE_PYTHON <= version < MAX_RELEASE_PYTHON_EXCLUSIVE:
        raise RuntimeError("P7-A release builds require CPython >=3.10.8,<3.11")


def validate_release_host() -> None:
    """Enforce the supported Windows x64 / Python / PyInstaller build host."""

    if sys.platform != "win32":
        raise RuntimeError("P7-A release builds are supported only on Windows")
    validate_release_python(sys.version_info[:3])
    if struct.calcsize("P") * 8 != 64:
        raise RuntimeError("P7-A release builds require a 64-bit Python interpreter")
    installed = pyinstaller_version()
    if installed not in EXPECTED_PYINSTALLER_VERSIONS:
        raise RuntimeError(f"P7-A requires exactly PyInstaller 5.7; found {installed}")
