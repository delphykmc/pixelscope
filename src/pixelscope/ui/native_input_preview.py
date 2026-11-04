"""Asynchronous, revocable presentation-only native RAW/YUV preview."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from PySide6.QtCore import QObject, Signal, Slot

from pixelscope.core.cancellation import cancellation_checkpoint
from pixelscope.core.raw_display import render_raw_preview
from pixelscope.core.yuv import NativeYuvFrame, bt601_full_rgb_preview
from pixelscope.io.input_profile_batch import FileRevision, InputProfile, interpretation_key
from pixelscope.io.raw_profile import RawProfile
from pixelscope.io.raw_reader import read_raw
from pixelscope.io.yuv_reader import read_yuv
from pixelscope.workers.task_worker import TaskWorker
from pixelscope.workers.thread_pools import analysis_thread_pool

PREVIEW_MAX_SIDE = 256


@dataclass(frozen=True)
class NativeInputPreview:
    """Display pixels are never substituted for numeric/native source samples."""

    pixels: NDArray[np.uint8]
    source_path: Path
    interpretation: str
    source_generation: int
    width: int
    height: int


def _file_revision(path: Path) -> FileRevision:
    info = path.stat()
    return FileRevision(info.st_size, info.st_mtime_ns, info.st_dev, info.st_ino)


def native_interpretation_preview(
    path: Path,
    profile: InputProfile,
    source_generation: int,
) -> NativeInputPreview:
    """Read native semantics on a worker and return at most a 256px crop.

    The RAW reader receives a row-stride-preserving top-left crop profile to
    avoid full-frame allocation for packed formats. YUV uses the existing
    native plane reader and crops on native chroma cell boundaries.
    """

    before = _file_revision(path)
    cancellation_checkpoint()
    if isinstance(profile, RawProfile):
        width = min(profile.width, PREVIEW_MAX_SIDE)
        height = min(profile.height, PREVIEW_MAX_SIDE)
        if profile.storage_format in ("mipi_raw10", "mipi_raw14"):
            width -= width % 4
            height -= height % 2
        elif profile.storage_format == "mipi_raw12":
            width -= width % 2
            height -= height % 2
        if width <= 0 or height <= 0:
            raise ValueError("RAW dimensions are too small for this storage format")
        crop_profile = RawProfile.parse_obj({**profile.dict(), "width": width, "height": height})
        native = read_raw(path, crop_profile)
        cancellation_checkpoint()
        pixels = render_raw_preview(
            native,
            channel_layout=profile.channel_layout,
            bit_depth=profile.bit_depth,
            black_level=profile.black_level,
            bayer_pattern=profile.bayer_pattern,
        )
    else:
        frame = read_yuv(path, profile)
        cancellation_checkpoint()
        scale_x, scale_y = frame.chroma_scale
        width = min(profile.width, PREVIEW_MAX_SIDE)
        height = min(profile.height, PREVIEW_MAX_SIDE)
        width -= width % scale_x
        height -= height % scale_y
        native_crop = NativeYuvFrame(
            y=frame.y[:height, :width],
            u=frame.u[: height // scale_y, : width // scale_x],
            v=frame.v[: height // scale_y, : width // scale_x],
            layout=frame.layout,
        )
        pixels = bt601_full_rgb_preview(native_crop)
    cancellation_checkpoint()
    if _file_revision(path) != before:
        raise ValueError("Source changed while preparing preview")
    return NativeInputPreview(
        pixels=np.ascontiguousarray(pixels),
        source_path=path,
        interpretation=interpretation_key(profile),
        source_generation=source_generation,
        width=width,
        height=height,
    )


class NativeInputPreviewController(QObject):
    """One active request; discard callbacks after epoch/profile/generation changes."""

    preview_ready = Signal(int, object)
    preview_failed = Signal(int, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._epoch = 0
        self._active_worker: TaskWorker | None = None
        self._active_task_id: str | None = None
        self._requested_profile: str | None = None
        self._requested_generation: int | None = None
        self._closing = False

    @property
    def epoch(self) -> int:
        return self._epoch

    def request(self, path: Path, profile: InputProfile, *, generation: int = 0) -> int:
        self.cancel()
        if self._closing:
            raise RuntimeError("Preview controller is shut down")
        epoch = self._epoch
        self._requested_profile = interpretation_key(profile)
        self._requested_generation = generation
        worker = TaskWorker(
            native_interpretation_preview,
            Path(path),
            profile.copy(deep=True),
            generation,
            generation=epoch,
        )
        self._active_worker = worker
        self._active_task_id = worker.task_id
        worker.signals.succeeded.connect(self._succeeded)
        worker.signals.failed.connect(self._failed)
        worker.signals.cancelled.connect(self._cancelled)
        worker.signals.finished.connect(self._finished)
        analysis_thread_pool().start(worker)
        return epoch

    def cancel(self) -> None:
        self._epoch += 1
        if self._active_worker is not None:
            self._active_worker.cancel()
        self._active_worker = None
        self._active_task_id = None
        self._requested_profile = None
        self._requested_generation = None

    def shutdown(self) -> None:
        if not self._closing:
            self._closing = True
            self.cancel()

    def _is_current(self, task_id: str, epoch: int) -> bool:
        return not self._closing and epoch == self._epoch and task_id == self._active_task_id

    @Slot(str, object, int, object)
    def _succeeded(self, task_id: str, _document_id: object, epoch: int, result: object) -> None:
        if not self._is_current(task_id, epoch):
            return
        if not isinstance(result, NativeInputPreview):
            self.preview_failed.emit(epoch, "Invalid native preview result")
            return
        if (
            result.interpretation != self._requested_profile
            or result.source_generation != self._requested_generation
        ):
            return
        self.preview_ready.emit(epoch, result)

    @Slot(str, object, int, object)
    def _failed(self, task_id: str, _document_id: object, epoch: int, error: object) -> None:
        if self._is_current(task_id, epoch):
            self.preview_failed.emit(epoch, str(getattr(error, "message", error)))

    @Slot(str, object, int)
    def _cancelled(self, _task_id: str, _document_id: object, _epoch: int) -> None:
        pass

    @Slot(str)
    def _finished(self, task_id: str) -> None:
        if task_id == self._active_task_id:
            self._active_worker = None
            self._active_task_id = None
