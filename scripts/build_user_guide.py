from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.check_user_guide_site import find_site_problems  # noqa: E402
from scripts.release_contract import REPO_ROOT  # noqa: E402

SITE_ROOT = REPO_ROOT / "site"
SHIM_PATH = REPO_ROOT / "docs/user-guide/assets/vendor/iframe-worker-1.0.4.js"
SHIM_SHA256 = "e8e412dbcfea9b7e31b5ffa288d7b6035915e714c542f4176a0cdbe262fc9609"


def validate_source_shim() -> None:
    if not SHIM_PATH.is_file():
        raise RuntimeError(f"Missing vendored offline-search shim: {SHIM_PATH}")
    actual = hashlib.sha256(SHIM_PATH.read_bytes()).hexdigest()
    if actual != SHIM_SHA256:
        raise RuntimeError(f"Vendored offline-search shim SHA-256 mismatch: {actual}")


def build_user_guide(*, python: Path | None = None) -> Path:
    """Build a fresh guide without depending on CDN assets or warm caches."""
    validate_source_shim()
    subprocess.run(
        [str(python or sys.executable), "-m", "mkdocs", "build", "--strict"],
        cwd=REPO_ROOT,
        check=True,
    )
    problems = find_site_problems(SITE_ROOT)
    if problems:
        raise RuntimeError("Generated User Guide is invalid:\\n - " + "\\n - ".join(problems))
    return SITE_ROOT


def main() -> int:
    site = build_user_guide()
    print(f"Validated locally built User Guide: {site.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
