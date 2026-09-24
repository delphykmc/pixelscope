from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from scripts import capture_ui_scene
from scripts.capture_ui_scene import apply_single_view_capture_zoom, statistics_ready
from scripts.run_ui_capture_poc import (
    assess_capture_process,
    changed_fraction,
    sanitized_stderr,
    stderr_has_callback_exception,
    validate_capture,
)


def _pattern(path: Path) -> None:
    image = Image.new("RGB", (500, 400))
    pixels = image.load()
    assert pixels is not None
    for y in range(400):
        for x in range(500):
            pixels[x, y] = (x % 256, y % 256, (x + y) % 256)
    image.save(path)


def _metadata(path: Path, image: Path, source_sha: str) -> None:
    path.write_text(
        json.dumps(
            {
                "status": "captured",
                "scenario": "single_image",
                "source_sha": source_sha,
                "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
                "geometry": {"pixel_png": [500, 400], "logical_widget": [500, 400]},
            }
        ),
        encoding="utf-8",
    )


def test_poc_validator_requires_decodable_nonblank_png_and_exact_identity(tmp_path: Path) -> None:
    png, metadata = tmp_path / "capture.png", tmp_path / "capture.json"
    sha = "1" * 40
    _pattern(png)
    _metadata(metadata, png, sha)
    assert validate_capture(png, metadata, "single_image", sha)["status"] == "captured"

    pinned = json.loads(metadata.read_text(encoding="utf-8"))
    pinned["capture_profile"] = "windows-e1-poc-v1"
    metadata.write_text(json.dumps(pinned), encoding="utf-8")
    with pytest.raises(ValueError, match="pinned capture profile"):
        validate_capture(png, metadata, "single_image", sha)
    pinned.pop("capture_profile")
    metadata.write_text(json.dumps(pinned), encoding="utf-8")

    with pytest.raises(ValueError, match="source SHA mismatch"):
        validate_capture(png, metadata, "single_image", "2" * 40)

    Image.new("RGB", (500, 400), (20, 20, 20)).save(png)
    _metadata(metadata, png, sha)
    with pytest.raises(ValueError, match="insufficient pixel variation"):
        validate_capture(png, metadata, "single_image", sha)

    png.write_bytes(b"not a PNG")
    _metadata(metadata, png, sha)
    with pytest.raises(OSError):
        validate_capture(png, metadata, "single_image", sha)


def test_poc_repeatability_is_exact_pixel_not_png_metadata(tmp_path: Path) -> None:
    first, second = tmp_path / "first.png", tmp_path / "second.png"
    _pattern(first)
    _pattern(second)
    assert changed_fraction(first, second) == 0
    with Image.open(second) as opened:
        changed = opened.copy()
    changed.putpixel((20, 20), (1, 2, 3))
    changed.save(second)
    assert 0 < changed_fraction(first, second) < 0.01
    Image.new("RGB", (450, 400)).save(second)
    assert changed_fraction(first, second) == 1.0


def test_statistics_readiness_waits_for_successful_current_request_and_rows() -> None:
    document = object()
    panel = SimpleNamespace(
        status=SimpleNamespace(text=lambda: "Preparing analysis..."),
        busy=SimpleNamespace(isVisible=lambda: True),
        _request_signature=("current",),
        _completed_signature=(),
        _documents=[document],
        last_results=(),
        image_summary=SimpleNamespace(rowCount=lambda: 0),
        table=SimpleNamespace(rowCount=lambda: 0),
    )
    assert not statistics_ready(panel, document)
    # A stale result must not authorize capturing the currently requested document.
    panel._completed_signature = ("previous",)
    panel.last_results = (object(),)
    panel.image_summary = SimpleNamespace(rowCount=lambda: 1)
    panel.table = SimpleNamespace(rowCount=lambda: 3)
    assert not statistics_ready(panel, document)
    panel._completed_signature = ("current",)
    panel.status = SimpleNamespace(text=lambda: "")
    panel.busy = SimpleNamespace(isVisible=lambda: False)
    assert statistics_ready(panel, document)

    panel.status = SimpleNamespace(text=lambda: "Error: synthetic worker failure")
    with pytest.raises(RuntimeError, match="Statistics analysis failed"):
        statistics_ready(panel, document)

    panel.status = SimpleNamespace(text=lambda: "Calculating...")
    assert not statistics_ready(panel, document)


def test_single_view_candidate_changes_real_viewer_zoom_state() -> None:
    factors: list[float] = []
    viewer = SimpleNamespace(zoom_by=factors.append)

    apply_single_view_capture_zoom(viewer)

    assert factors == [pytest.approx(2.0 / 3.0)]


def test_zero_exit_callback_error_fails_even_with_valid_png(tmp_path: Path) -> None:
    png, metadata = tmp_path / "capture.png", tmp_path / "capture.json"
    sha = "a" * 40
    _pattern(png)
    _metadata(metadata, png, sha)
    quiet = subprocess.CompletedProcess([], 0, "", "QWindowsWindow: harmless warning\n")
    assert assess_capture_process(quiet, png, metadata, "single_image", sha)["status"] == "captured"

    # A real QCoreApplication callback raises while processEvents returns normally.
    script = """
from PySide6.QtCore import QCoreApplication, QTimer
from scripts.capture_ui_scene import CallbackExceptionMonitor
app = QCoreApplication([])
monitor = CallbackExceptionMonitor()
monitor.install()
def broken_slot():
    raise RuntimeError("intentional test callback failure")
QTimer.singleShot(0, broken_slot)
app.processEvents()
monitor.restore()
print(len(monitor.errors))
"""
    process = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert process.returncode == 0
    assert "1" in process.stdout
    assert stderr_has_callback_exception(process.stderr)
    with pytest.raises(ValueError, match="qt_callback_exception"):
        assess_capture_process(process, png, metadata, "single_image", sha)

    pinned = json.loads(metadata.read_text(encoding="utf-8"))
    pinned["callback_errors"] = ["RuntimeError: recorded Qt callback failure"]
    metadata.write_text(json.dumps(pinned), encoding="utf-8")
    with pytest.raises(ValueError, match="Qt callback exception"):
        validate_capture(png, metadata, "single_image", sha)
    assert "<path>" in sanitized_stderr(r"C:\Users\someone\sensitive.txt")


def test_scene_wait_times_out_without_async_completion(monkeypatch: pytest.MonkeyPatch) -> None:
    class WaitingApp:
        def processEvents(self, *_args: object) -> None:
            pass

    class VisibleWidget:
        def isVisible(self) -> bool:
            return True

        def width(self) -> int:
            return 1680

        def height(self) -> int:
            return 980

    monkeypatch.setattr(capture_ui_scene, "TIMEOUT_SECONDS", 0.0)
    with pytest.raises(TimeoutError, match="visible and ready"):
        capture_ui_scene._wait_until_ready(WaitingApp(), VisibleWidget(), lambda: False)
