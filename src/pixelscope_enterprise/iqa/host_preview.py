"""Opt-in PUBLIC-SAFE UX-3C MainWindow preview; no PRIVATE SUB provider.

Run from the source tree with:
    python -m pixelscope_enterprise.iqa.host_preview --rgb

The selected MAIN files are NEVER submitted or evaluated. Each IQA > Run IQA
schedules an independent synthetic job. Runs 1/2 complete/fail; run 3 waits
for explicit operator cancellation, then acknowledges cancelled. The same
three-state pattern repeats for subsequent runs.
Do not register this developer-only module as a production executable.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread

from PySide6.QtCore import QSettings

from pixelscope.app.bootstrap import (
    compose_main_window_presentation,
    create_application,
)
from pixelscope.app.main_window import MainWindow
from pixelscope.app.settings import QSettingsAdapter, SettingsRepository
from pixelscope.workers.thread_pools import analysis_thread_pool
from pixelscope_enterprise.iqa.composition import IqaJobSnapshot, IqaWindowContribution
from pixelscope_enterprise.iqa.demo import create_synthetic_rgb, make_synthetic_result


def main(arguments: Sequence[str] | None = None) -> int:
    """Show real MAIN + Enterprise U6/UX-3C UI with synthetic job callbacks."""

    argv = list(arguments) if arguments is not None else sys.argv[1:]
    unknown = [argument for argument in argv if argument != "--rgb"]
    if unknown:
        raise ValueError(f"unsupported host preview arguments: {unknown}")
    app = create_application()
    analysis_thread_pool()
    stop = Event()
    workers: list[Thread] = []

    with TemporaryDirectory(prefix="pixelscope-iqa-host-preview-") as temporary:
        root = Path(temporary)
        repository = SettingsRepository(
            QSettingsAdapter(QSettings(str(root / "main.ini"), QSettings.Format.IniFormat))
        )
        settings = repository.load()
        result = make_synthetic_result("synthetic-host-preview")
        if "--rgb" in argv:
            source_a = root / "synthetic-source-a.png"
            source_b = root / "synthetic-source-b.png"
            create_synthetic_rgb(source_a)
            create_synthetic_rgb(source_b, source_b=True)
            result = replace(result, source_a=source_a, source_b=source_b)

        next_job = 0
        cancel_events: dict[str, Event] = {}

        def run_synthetic(_selected_sources: tuple[Path | None, ...]) -> None:
            """Demo callback only: selected files are intentionally ignored."""

            nonlocal next_job
            next_job += 1
            ordinal = next_job
            job_id = f"synthetic-host-{ordinal:03d}"
            terminal = ("completed", "failed", "cancelled")[(ordinal - 1) % 3]
            label = f"Synthetic demo #{ordinal} (NOT real IQA)"
            cancellation = Event()
            cancel_events[job_id] = cancellation
            host.statusBar().showMessage(
                "Synthetic preview: selected files were NOT evaluated", 9000
            )

            def worker() -> None:
                """Publish verified synthetic states, not a fabricated Cancel acknowledgement."""

                def emit(state: str, *, active: bool = False) -> bool:
                    if stop.is_set():
                        return False
                    try:
                        contribution.post_job(
                            IqaJobSnapshot(
                                job_id=job_id,
                                label=label,
                                status=state,
                                result=replace(result, result_id=job_id)
                                if state == "completed"
                                else None,
                                can_cancel=active,
                            )
                        )
                    except RuntimeError:
                        # MAIN shutdown may race with this synthetic producer.
                        return False
                    return True

                if not emit("queued", active=True):
                    return
                if cancellation.wait(0.8):
                    emit("cancelled")
                    return
                if not emit("running", active=True):
                    return

                if terminal == "cancelled":
                    # Job #3 (and every third job) stays running until user
                    # actually requests cancellation for THIS job.
                    while not stop.is_set() and not cancellation.wait(0.1):
                        pass
                else:
                    cancellation.wait(0.8)

                if stop.is_set():
                    return
                emit("cancelled" if cancellation.is_set() else terminal)

            thread = Thread(target=worker, name=f"iqa-host-preview-{ordinal}", daemon=True)
            workers.append(thread)
            thread.start()

        def cancel_synthetic(job_id: str) -> None:
            """Request cancellation; worker alone acknowledges the terminal state."""

            cancellation = cancel_events.get(job_id)
            if cancellation is None:
                raise ValueError("unknown synthetic job")
            cancellation.set()
            host.statusBar().showMessage(
                f"Synthetic cancellation requested: {job_id} (awaiting confirmation)",
                9000,
            )

        def private_preview_settings() -> QSettings:
            return QSettings(str(root / "iqa.ini"), QSettings.Format.IniFormat)

        contribution = IqaWindowContribution(
            start_job=run_synthetic,
            cancel_job=cancel_synthetic,
            settings_factory=private_preview_settings,
        )
        host = MainWindow(
            settings,
            settings.performance_settings(),
            repository,
            window_contributions=(contribution,),
        )
        compose_main_window_presentation(host, runtime_contributions=(contribution,))
        host.setWindowTitle("PixelScope - SYNTHETIC Enterprise IQA Host Preview")
        app.aboutToQuit.connect(stop.set)  # type: ignore[attr-defined]
        host.show()
        print(
            "UX-3C synthetic host: IQA > Run IQA / Cancel Selected IQA Job, "
            "View > Show IQA Jobs, then select a job. "
            "Runs 1/2 complete/fail; run 3 awaits explicit cancellation. "
            "No actual image evaluation."
        )
        try:
            return app.exec()
        finally:
            stop.set()
            for worker in workers:
                worker.join(timeout=2)


if __name__ == "__main__":
    raise SystemExit(main())
