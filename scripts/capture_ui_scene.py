"""WP-Help-E1: capture one real PixelScope scene per OS process.

This is a feasibility probe, not the E2 manifest or a replacement for the existing
ten-scene manual-review script. The two PoC scenarios reuse its synthetic document
builder and the production application composition.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from types import TracebackType

import pyqtgraph
from PySide6 import __version__ as pyside_version
from PySide6.QtCore import QCoreApplication, QEvent, QEventLoop, QSettings, qVersion
from PySide6.QtWidgets import QApplication, QDialog, QWidget

from pixelscope.app.application import (
    _compose_main_window_presentation,
    analysis_thread_pool,
    create_application,
    load_startup_settings,
    remote_iqa_thread_pool,
)
from pixelscope.app.main_window import MainWindow
from pixelscope.core.line_profile import LineSelection
from pixelscope.version import __version__ as app_version

# Direct script invocation has scripts/ as sys.path[0]. This path is repository
# tooling only and never modifies the installed application's module search path.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pixelscope.io.path_discovery import ImageInput  # noqa: E402
from pixelscope.ui.raw_open_dialog import RawOpenDialog  # noqa: E402
from scripts.capture_ui_review import review_document  # noqa: E402
from scripts.screenshot_fixture_identity import single_view_fixture_identity  # noqa: E402

PROFILE = "windows-e1-poc-v1"
WINDOW_SIZE = (1680, 980)
DIALOG_SIZE = (280, 685)
SINGLE_VIEW_ZOOM_FACTOR = 1.5
TIMEOUT_SECONDS = 15.0
CALLBACK_ERROR_MARKER = "PIXELSCOPE_E1_QT_CALLBACK_EXCEPTION"


def sanitized_diagnostic(exc: BaseException) -> str:
    """Bound messages and redact sensitive filesystem locations from artifacts."""
    message = " ".join(str(exc).splitlines())
    for prefix in (str(ROOT), str(Path.home())):
        if prefix:
            message = message.replace(prefix, "<path>")
    message = re.sub(
        r"[A-Za-z]:[/\\][^\s'\"<>]*|/(?:home|Users|mnt|tmp|var|opt)/[^\s'\"<>]*",
        "<path>",
        message,
    )
    return message[:300]


class CallbackExceptionMonitor:
    """Capture PySide slot exceptions routed through sys.excepthook.

    A Qt callback exception can be printed without propagating from processEvents.
    The parent additionally recognizes traceback stderr for other Qt callback paths.
    """

    def __init__(self) -> None:
        self.errors: list[str] = []
        self._previous = sys.excepthook

    def install(self) -> None:
        self._previous = sys.excepthook
        sys.excepthook = self._handle

    def restore(self) -> None:
        sys.excepthook = self._previous

    def _handle(
        self,
        exception_type: type[BaseException],
        exception: BaseException,
        _traceback: TracebackType | None,
    ) -> None:
        diagnostic = f"{exception_type.__name__}: {sanitized_diagnostic(exception)}"
        if len(self.errors) < 8:
            self.errors.append(diagnostic)
        print(f"{CALLBACK_ERROR_MARKER}: {diagnostic}", file=sys.stderr)


def statistics_ready(panel: object, document: object) -> bool:
    """Require successful current-request analysis, not a displayed preview alone."""
    # Use the owner's existing request/result authority, without joining pools.
    status = panel.status.text()  # type: ignore[attr-defined]
    if status.startswith("Error:"):
        raise RuntimeError(f"Statistics analysis failed: {status}")
    request = panel._request_signature  # type: ignore[attr-defined]
    return bool(
        request
        and request == panel._completed_signature  # type: ignore[attr-defined]
        and len(panel.last_results) == 1  # type: ignore[attr-defined]
        and len(panel._documents) == 1  # type: ignore[attr-defined]
        and panel._documents[0] is document  # type: ignore[attr-defined]
        and panel.image_summary.rowCount() == 1  # type: ignore[attr-defined]
        and panel.table.rowCount() >= 3  # type: ignore[attr-defined]
        and panel.status.text() == ""  # type: ignore[attr-defined]
        and not panel.busy.isVisible()  # type: ignore[attr-defined]
    )


def apply_single_view_capture_zoom(viewer: object) -> None:
    """Set the real viewer state used by the guide candidate capture."""
    viewer.zoom_by(1.0 / SINGLE_VIEW_ZOOM_FACTOR)  # type: ignore[attr-defined]


def _fixture_identity(documents: list[object], scene: str) -> str:
    digest = hashlib.sha256(scene.encode("utf-8"))
    for document in documents:
        digest.update(document.source.tobytes())  # type: ignore[attr-defined]
        digest.update(document.display_name.encode("utf-8"))  # type: ignore[attr-defined]
        source_path = document.source_path  # type: ignore[attr-defined]
        digest.update(source_path.as_posix().encode("utf-8"))
    return digest.hexdigest()


def _populated_window(
    app: QApplication,
    count: int,
    layout: str,
) -> tuple[MainWindow, list[object]]:
    repository, settings, performance = load_startup_settings()
    analysis_thread_pool()
    result_pool = remote_iqa_thread_pool()
    window = MainWindow(settings, performance, repository, iqa_result_pool=result_pool)
    _compose_main_window_presentation(window)
    window.setWindowIcon(app.windowIcon())
    documents = [review_document(index) for index in range(count)]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    window.set_layout_mode(layout)
    window.resize(*WINDOW_SIZE)
    window.setFixedSize(*WINDOW_SIZE)
    window.bottom_dock.hide()
    return window, documents


def _documents_presented(window: MainWindow, documents: list[object]) -> bool:
    presented = [viewer.document for viewer in window.multi_compare_view.occupied_viewers]
    return len(presented) == len(documents) and all(
        actual is expected for actual, expected in zip(presented, documents, strict=True)
    )


def _analysis_ready(panel: object, documents: list[object]) -> bool:
    status = panel.status.text()  # type: ignore[attr-defined]
    if status.startswith("Error:"):
        raise RuntimeError(f"Analysis failed: {status}")
    return bool(
        panel._request_signature  # type: ignore[attr-defined]
        and panel._request_signature  # type: ignore[attr-defined]
        == panel._completed_signature  # type: ignore[attr-defined]
        and list(panel._documents) == documents  # type: ignore[attr-defined]
        and len(panel.last_results) == len(documents)  # type: ignore[attr-defined]
        and panel.status.text() == ""  # type: ignore[attr-defined]
        and not panel.busy.isVisible()  # type: ignore[attr-defined]
    )


def _configure_isolated_settings(directory: Path) -> None:
    """Ensure QSettings cannot clear, write or read the owner's real preferences."""
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(directory))
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.SystemScope, str(directory))


def _single_image(app: QApplication) -> tuple[QWidget, Callable[[], bool], str]:
    window, documents = _populated_window(app, 1, "Single View")
    document = documents[0]
    if document.source_path is None:
        raise ValueError("Single View fixture must carry a synthetic displayed source path")
    fixture_sha256 = single_view_fixture_identity(
        document.source.tobytes(), document.display_name, document.source_path.as_posix()
    )
    zoom_applied = False

    def ready() -> bool:
        nonlocal zoom_applied
        base_ready = (
            document.document_id in window.documents
            and window.central_stack.currentWidget() is not window.empty_workspace
            and window.central_stack.currentWidget().isVisible()
            and window.viewer.document is document
            and window.viewer._displayed_preview is document.preview
            and document.preview is not None
            and statistics_ready(window.comparison_analysis_panel, document)
        )
        if base_ready and not zoom_applied:
            # Change the real ImageViewer state before capture. This produces a useful
            # 60-75% central-canvas image footprint without cropping or post-processing.
            apply_single_view_capture_zoom(window.viewer)
            zoom_applied = True
            return False
        return base_ready and zoom_applied

    return window, ready, fixture_sha256


def _six_image_multiview(app: QApplication) -> tuple[QWidget, Callable[[], bool], str]:
    window, documents = _populated_window(app, 6, "Multi View")
    return (
        window,
        lambda: (
            _documents_presented(window, documents)
            and _analysis_ready(window.comparison_analysis_panel, documents)
        ),
        _fixture_identity(documents, "six_image_multiview"),
    )


def _difference_analysis(app: QApplication) -> tuple[QWidget, Callable[[], bool], str]:
    window, documents = _populated_window(app, 2, "Multi View")
    started = False

    def ready() -> bool:
        nonlocal started
        if not started:
            if not _documents_presented(window, documents):
                return False
            window.analysis_tabs.setCurrentWidget(window.difference_panel)
            window.difference_panel.calculate_difference()
            started = True
            return False
        return bool(
            window._difference_document is not None
            and window.difference_panel.last_result is not None
            and window.difference_panel._worker is None
        )

    return window, ready, _fixture_identity(documents, "difference_analysis")


def _histogram_docked(app: QApplication) -> tuple[QWidget, Callable[[], bool], str]:
    window, documents = _populated_window(app, 3, "Multi View")
    configured = False

    def ready() -> bool:
        nonlocal configured
        if not _documents_presented(window, documents):
            return False
        if not configured:
            window._show_bottom_results()
            window.bottom_tabs.setCurrentWidget(window.comparison_analysis_panel.histogram_panel)
            configured = True
            return False
        panel = window.comparison_analysis_panel
        return bool(
            window.bottom_dock.isVisible()
            and _analysis_ready(panel, documents)
            and any(panel._histogram_series)
        )

    return window, ready, _fixture_identity(documents, "histogram_docked")


def _line_profile_docked(app: QApplication) -> tuple[QWidget, Callable[[], bool], str]:
    window, documents = _populated_window(app, 2, "Multi View")
    configured = False

    def ready() -> bool:
        nonlocal configured
        if not _documents_presented(window, documents):
            return False
        if not configured:
            window._show_bottom_results()
            window._shared_line_changed(LineSelection(40, 180, 580))
            window.bottom_tabs.setCurrentWidget(window.line_profile_panel)
            configured = True
            return False
        panel = window.line_profile_panel
        return bool(
            window.bottom_dock.isVisible()
            and panel._selection is not None
            and panel._worker is None
            and len(panel.last_results) == len(documents)
            and any(panel._profile_series)
        )

    return window, ready, _fixture_identity(documents, "line_profile_docked")


def _plots_floating(app: QApplication) -> tuple[QWidget, Callable[[], bool], str]:
    window, documents = _populated_window(app, 2, "Multi View")
    configured = False

    def ready() -> bool:
        nonlocal configured
        if not _documents_presented(window, documents):
            return False
        if not configured:
            window._show_bottom_results()
            window.bottom_tabs.setCurrentWidget(window.comparison_analysis_panel.histogram_panel)
            window.bottom_dock.setFloating(True)
            window.bottom_dock.resize(1200, 520)
            configured = True
            return False
        panel = window.comparison_analysis_panel
        return bool(
            window.bottom_dock.isVisible()
            and window.bottom_dock.isFloating()
            and _analysis_ready(panel, documents)
            and any(panel._histogram_series)
        )

    window.show()
    dock = window.bottom_dock
    dock._capture_parent_window = window  # type: ignore[attr-defined]
    return dock, ready, _fixture_identity(documents, "plots_floating")


def _raw_dialog(app: QApplication) -> tuple[QWidget, Callable[[], bool], str]:
    repository, settings, performance = load_startup_settings()
    analysis_thread_pool()
    result_pool = remote_iqa_thread_pool()
    window = MainWindow(settings, performance, repository, iqa_result_pool=result_pool)
    _compose_main_window_presentation(window)
    window.setWindowIcon(app.windowIcon())

    settings_root = Path(QSettings().fileName()).parent
    source = settings_root / "public-safe-capture.raw"
    source.write_bytes(bytes(640 * 480 * 2))
    captured: list[RawOpenDialog] = []
    original_exec = RawOpenDialog.exec

    def intercept_exec(dialog: RawOpenDialog) -> QDialog.DialogCode:
        captured.append(dialog)
        return QDialog.DialogCode.Rejected

    try:
        RawOpenDialog.exec = intercept_exec  # type: ignore[method-assign]
        window._confirm_raw_profile(ImageInput(source, None), None)
    finally:
        RawOpenDialog.exec = original_exec  # type: ignore[method-assign]
    if len(captured) != 1:
        raise RuntimeError("RAW open path did not create exactly one profile dialog")
    dialog = captured[0]
    dialog.setFixedWidth(DIALOG_SIZE[0])
    dialog._resize_dialog_to_content()
    # Retain the production parent for the complete capture lifetime.
    dialog._capture_parent_window = window  # type: ignore[attr-defined]
    fixture_sha256 = hashlib.sha256(
        json.dumps(
            {
                "source_size": source.stat().st_size,
                "width": dialog.width_box.value(),
                "height": dialog.height_box.value(),
                "stride_bytes": dialog.stride.value(),
                "bit_depth": dialog.bit_depth.value(),
                "pixel_layout": dialog.layout_kind.currentText(),
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return (
        dialog,
        lambda: (
            dialog.width_box.value() == 640
            and dialog.height_box.value() == 480
            and dialog.actual_file_size_value.text() == "614,400 bytes"
            and dialog.file_size_state == "match"
            and dialog.footer.isVisible()
            and dialog.ok_button.isVisible()
            and dialog.cancel_button.isVisible()
        ),
        fixture_sha256,
    )


BUILDERS = {
    "single_image": _single_image,
    "six_image_multiview": _six_image_multiview,
    "difference_analysis": _difference_analysis,
    "histogram_docked": _histogram_docked,
    "line_profile_docked": _line_profile_docked,
    "plots_floating": _plots_floating,
    "raw_profile_dialog": _raw_dialog,
}

SCENARIOS = tuple(BUILDERS)


def _wait_until_ready(app: QApplication, widget: QWidget, ready: Callable[[], bool]) -> None:
    """Process Qt events until concrete scene state and geometry are realized.

    No arbitrary settling sleep, global pool wait, GC suppression or full-suite
    workaround. A pending async UI state times out as a capture failure.
    """
    deadline = time.monotonic() + TIMEOUT_SECONDS
    consecutive = 0
    while time.monotonic() < deadline:
        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
        realized = widget.isVisible() and widget.width() > 0 and widget.height() > 0
        if realized and ready():
            consecutive += 1
            if consecutive >= 3:
                return
        else:
            consecutive = 0
    raise TimeoutError("scene did not reach a visible and ready QWidget state")


def capture(scene: str, output: Path, metadata_path: Path, source_sha: str) -> int:
    if scene not in BUILDERS:
        raise ValueError("unknown capture scenario")
    if not output.parent.is_dir() or not metadata_path.parent.is_dir():
        raise ValueError("capture output and metadata parent directories must exist")
    if output.resolve() == metadata_path.resolve():
        raise ValueError("PNG and metadata paths must differ")

    report: dict[str, object] = {
        "schema_version": 1,
        "status": "failed",
        "scenario": scene,
        "capture_profile": PROFILE,
        "source_sha": source_sha,
        "application_version": app_version,
        "python": platform.python_version(),
        "pyside6": pyside_version,
        "qt": qVersion(),
        "pyqtgraph": pyqtgraph.__version__,
        "os": platform.platform(),
        "fixture_sha256": None,
        "geometry": None,
        "screen": None,
        "error_type": None,
        "error_detail": None,
        "callback_errors": [],
    }
    widget: QWidget | None = None
    app: QApplication | None = None
    directory: tempfile.TemporaryDirectory[str] | None = None
    monitor = CallbackExceptionMonitor()
    monitor.install()
    try:
        directory = tempfile.TemporaryDirectory(prefix="pixelscope-e1-settings-")
        _configure_isolated_settings(Path(directory.name))
        app = create_application([])
        widget, ready, fixture_sha256 = BUILDERS[scene](app)
        report["fixture_sha256"] = fixture_sha256
        widget.show()
        _wait_until_ready(app, widget, ready)
        if monitor.errors:
            raise RuntimeError("Qt callback exception before capture")
        # Native QWidget grab. Neither a PIL composition nor fake UI.
        pixmap = widget.grab()
        if pixmap.isNull():
            raise RuntimeError("QWidget.grab returned a null pixmap")
        if not pixmap.save(str(output), "PNG"):
            raise RuntimeError("QWidget.grab PNG save failed")
        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError("saved PNG is empty")
        screen = widget.screen() or app.primaryScreen()
        report["screen"] = (
            {
                "name": screen.name(),
                "logical_dpi": screen.logicalDotsPerInch(),
                "physical_dpi": screen.physicalDotsPerInch(),
                "device_pixel_ratio": screen.devicePixelRatio(),
                "geometry": [screen.geometry().width(), screen.geometry().height()],
                "available_geometry": [
                    screen.availableGeometry().width(),
                    screen.availableGeometry().height(),
                ],
            }
            if screen is not None
            else None
        )
        report["geometry"] = {
            "logical_widget": [widget.width(), widget.height()],
            "pixel_png": [pixmap.width(), pixmap.height()],
            "device_pixel_ratio": pixmap.devicePixelRatio(),
        }
        report["image_sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
        report["status"] = "captured"
    except Exception as exc:
        report["error_type"] = type(exc).__name__
        report["error_detail"] = sanitized_diagnostic(exc)
        print(
            f"E1 capture failed: {report['error_type']}: {report['error_detail']}",
            file=sys.stderr,
        )
    finally:
        try:
            if widget is not None:
                widget.close()
                parent_window = getattr(widget, "_capture_parent_window", None)
                if parent_window is not None:
                    parent_window.close()
            if app is not None:
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                app.processEvents()
        except Exception as exc:
            report["error_type"] = type(exc).__name__
            report["error_detail"] = "Qt teardown: " + sanitized_diagnostic(exc)
        finally:
            monitor.restore()
            if directory is not None:
                directory.cleanup()
        if monitor.errors:
            report["callback_errors"] = monitor.errors
            report["error_type"] = "QtCallbackException"
            report["error_detail"] = "Qt signal/event callback raised"
        if report["error_type"] is not None:
            report["status"] = "failed"
            output.unlink(missing_ok=True)
        metadata_path.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return 0 if report["status"] == "captured" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", choices=SCENARIOS, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    if len(args.source_sha) != 40 or not all(ch in "0123456789abcdef" for ch in args.source_sha):
        parser.error("--source-sha requires the exact lowercase 40-character Git SHA")
    return capture(args.scene, args.output, args.metadata, args.source_sha)


if __name__ == "__main__":
    raise SystemExit(main())
