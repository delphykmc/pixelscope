from __future__ import annotations

import traceback
from collections.abc import Callable
from dataclasses import dataclass
from threading import Event
from typing import Any
from uuid import uuid4

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


@dataclass(frozen=True)
class TaskError:
    task_id: str
    document_id: str | None
    generation: int
    message: str
    exception_type: str
    traceback_text: str


class TaskSignals(QObject):
    started = Signal(str, object, int)
    progress = Signal(str, object, int, int)
    succeeded = Signal(str, object, int, object)
    failed = Signal(str, object, int, object)
    cancelled = Signal(str, object, int)
    finished = Signal(str)


class TaskWorker(QRunnable):
    """QRunnable with IDs, cooperative cancellation, and structured errors."""

    def __init__(
        self,
        function: Callable[..., Any],
        *args: Any,
        document_id: str | None = None,
        generation: int = 0,
        **kwargs: Any,
    ) -> None:
        super().__init__()
        self.task_id = str(uuid4())
        self.document_id = document_id
        self.generation = generation
        self.signals = TaskSignals()
        self._function = function
        self._args = args
        self._kwargs = kwargs
        self._cancel_event = Event()
        self.setAutoDelete(True)

    def cancel(self) -> None:
        self._cancel_event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    @Slot()
    def run(self) -> None:
        self.signals.started.emit(self.task_id, self.document_id, self.generation)
        if self.is_cancelled:
            self.signals.cancelled.emit(self.task_id, self.document_id, self.generation)
            self.signals.finished.emit(self.task_id)
            return
        try:
            result = self._function(*self._args, **self._kwargs)
            if self.is_cancelled:
                self.signals.cancelled.emit(self.task_id, self.document_id, self.generation)
            else:
                self.signals.succeeded.emit(self.task_id, self.document_id, self.generation, result)
        except Exception as exc:  # noqa: BLE001 - worker boundary must report every failure
            error = TaskError(
                task_id=self.task_id,
                document_id=self.document_id,
                generation=self.generation,
                message=str(exc),
                exception_type=type(exc).__name__,
                traceback_text=traceback.format_exc(),
            )
            self.signals.failed.emit(self.task_id, self.document_id, self.generation, error)
        finally:
            self.signals.finished.emit(self.task_id)
