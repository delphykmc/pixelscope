from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_user_guide import SHIM_SHA256  # noqa: E402
from scripts.check_user_guide_site import find_site_problems  # noqa: E402
from scripts.release_contract import APP_DIR  # noqa: E402


class ArtifactValidationError(RuntimeError):
    """Raised when a built onedir tree violates the P7-A artifact contract."""


_REQUIRED_FILES = (
    Path("PixelScope.exe"),
    Path("help/index.html"),
    Path("help/llms.txt"),
    Path("help/search/search_index.js"),
    Path("help/assets/vendor/iframe-worker-1.0.4.js"),
    Path("pixelscope/assets/icons/pixelscope.svg"),
    Path("pixelscope/assets/icons/pixelscope.png"),
    Path("pixelscope/assets/icons/pixelscope.ico"),
)
_REQUIRED_NATIVE_PATTERNS = {
    "Python runtime": ("python310.dll",),
    "Qt Windows platform plugin": ("qwindows.dll",),
    "PySide6 QtCore": ("QtCore.pyd",),
    "PySide6 QtGui": ("QtGui.pyd",),
    "PySide6 QtWidgets": ("QtWidgets.pyd",),
    "NumPy native core": ("_multiarray_umath*.pyd",),
    "OpenCV native module": ("cv2*.pyd",),
}
_FORBIDDEN_TOP_LEVEL = frozenset(
    {
        ".git",
        ".github",
        "docs",
        "examples",
        "requirements",
        "scripts",
        "server",
        "src",
        "test_data",
        "tests",
        "pyproject.toml",
    }
)


def _matches_any(root: Path, patterns: tuple[str, ...]) -> bool:
    return any(any(root.rglob(pattern)) for pattern in patterns)


def validate_artifact(root: Path = APP_DIR) -> None:
    """Validate the structural contract of one canonical PixelScope onedir tree."""

    root = root.resolve()
    errors: list[str] = []
    if not root.is_dir():
        raise ArtifactValidationError(f"Artifact directory does not exist: {root}")

    for relative_path in _REQUIRED_FILES:
        path = root / relative_path
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"missing required file: {relative_path.as_posix()}")

    for label, patterns in _REQUIRED_NATIVE_PATTERNS.items():
        if not _matches_any(root, patterns):
            errors.append(f"missing required runtime component: {label}")

    top_level_names = {path.name.casefold() for path in root.iterdir()}
    forbidden = sorted(top_level_names & _FORBIDDEN_TOP_LEVEL)
    if forbidden:
        errors.append("forbidden source/dev artifact(s): " + ", ".join(forbidden))

    if any(root.rglob("__pycache__")):
        errors.append("forbidden source cache directory: __pycache__")

    help_root = root / "help"
    if help_root.is_dir():
        errors.extend(f"offline User Guide: {message}" for message in find_site_problems(help_root))
        shim = help_root / "assets/vendor/iframe-worker-1.0.4.js"
        if shim.is_file():
            actual = hashlib.sha256(shim.read_bytes()).hexdigest()
            if actual != SHIM_SHA256:
                errors.append("offline User Guide shim SHA-256 mismatch")

    if errors:
        joined = "\n - ".join(errors)
        raise ArtifactValidationError(f"Invalid PixelScope onedir artifact:\n - {joined}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the PixelScope PyInstaller onedir tree")
    parser.add_argument(
        "artifact",
        nargs="?",
        type=Path,
        default=APP_DIR,
        help="onedir root (default: dist/PixelScope)",
    )
    args = parser.parse_args()
    validate_artifact(args.artifact)
    print(f"Validated PixelScope onedir artifact: {args.artifact.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
