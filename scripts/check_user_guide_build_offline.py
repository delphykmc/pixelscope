from __future__ import annotations

import runpy
import shutil
import socket
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_user_guide import (  # noqa: E402
    REPO_ROOT,
    SHIM_PATH,
    SITE_ROOT,
    validate_source_shim,
)
from scripts.check_user_guide_site import find_site_problems  # noqa: E402


def _deny_network(*_args: object, **_kwargs: object) -> None:
    raise RuntimeError("Documentation build attempted an outbound network connection")


def main() -> int:
    """Exercise a cold-cache strict MkDocs build with socket connections forbidden."""
    validate_source_shim()
    if not SHIM_PATH.is_file():
        raise RuntimeError("Vendored shim is missing")
    shutil.rmtree(SITE_ROOT, ignore_errors=True)
    shutil.rmtree(REPO_ROOT / ".cache/plugin/privacy", ignore_errors=True)

    # This check runs in CI, not in the end-user app. Patch sockets before
    # loading MkDocs/plugins so a cache miss cannot silently reach a CDN.
    socket.socket.connect = _deny_network  # type: ignore[method-assign]
    socket.socket.connect_ex = _deny_network  # type: ignore[method-assign]
    socket.create_connection = _deny_network  # type: ignore[assignment]
    sys.argv = ["mkdocs", "build", "--strict"]
    try:
        runpy.run_module("mkdocs", run_name="__main__", alter_sys=True)
    except SystemExit as exc:
        if exc.code not in (0, None):
            return int(exc.code) if isinstance(exc.code, int) else 1

    problems = find_site_problems(SITE_ROOT)
    if problems:
        for problem in problems:
            print(f"Offline documentation contract: {problem}")
        return 1
    print("Cold-cache network-blocked User Guide build PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
