from __future__ import annotations

import argparse
import ctypes
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

from scripts.release_contract import EXECUTABLE_PATH

WM_CLOSE = 0x0010


def _find_visible_window(process_id: int, title_fragment: str = "PixelScope") -> int | None:
    if sys.platform != "win32":
        raise RuntimeError("Packaged executable smoke is supported only on Windows")

    user32 = ctypes.windll.user32
    matches: list[int] = []
    enum_proc_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd: int, _lparam: int) -> bool:
        window_pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
        if window_pid.value != process_id or not user32.IsWindowVisible(hwnd):
            return True
        length = int(user32.GetWindowTextLengthW(hwnd))
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        if title_fragment.casefold() in buffer.value.casefold():
            matches.append(int(hwnd))
            return False
        return True

    callback_ref = enum_proc_type(callback)
    user32.EnumWindows(callback_ref, 0)
    return matches[0] if matches else None


def smoke_executable(executable: Path, *, startup_timeout: float = 20.0) -> None:
    if sys.platform != "win32":
        raise RuntimeError("Packaged executable smoke is supported only on Windows")
    executable = executable.resolve()
    if not executable.is_file():
        raise FileNotFoundError(executable)

    process = subprocess.Popen([str(executable)], cwd=executable.parent)
    deadline = time.monotonic() + startup_timeout
    window: int | None = None
    try:
        while time.monotonic() < deadline:
            return_code = process.poll()
            if return_code is not None:
                raise RuntimeError(
                    f"PixelScope exited before showing its main window: {return_code}"
                )
            window = _find_visible_window(process.pid)
            if window is not None:
                break
            time.sleep(0.1)
        if window is None:
            raise RuntimeError("Timed out waiting for the packaged PixelScope main window")

        ctypes.windll.user32.PostMessageW(window, WM_CLOSE, 0, 0)
        try:
            return_code = process.wait(timeout=12.0)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Packaged PixelScope did not shut down after WM_CLOSE") from exc
        if return_code != 0:
            raise RuntimeError(f"Packaged PixelScope exited with code {return_code}")
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3.0)


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test the packaged PixelScope executable")
    parser.add_argument(
        "executable",
        nargs="?",
        type=Path,
        default=EXECUTABLE_PATH,
        help="executable path (default: dist/PixelScope/PixelScope.exe)",
    )
    parser.add_argument("--startup-timeout", type=float, default=20.0)
    args = parser.parse_args()
    smoke_executable(args.executable, startup_timeout=args.startup_timeout)
    print(f"Packaged PixelScope smoke PASS: {args.executable.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
