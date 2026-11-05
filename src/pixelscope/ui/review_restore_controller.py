"""Epoch-safe W09b verification and restore transaction, independently wired.

Source hashing/native decoding runs in a dedicated bounded worker. UI commits
only after all original Finding source keys are Verified and owner preflight
succeeds; late worker results cannot authorize a newer Finding.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Literal, Protocol

from PySide6.QtCore import QObject, QThreadPool, Signal, Slot

from pixelscope.core.review_record import ReviewFindingV1, ReviewSourceV1
from pixelscope.core.review_workflow import ReviewLibrary
from pixelscope.io.raw_profile import RawProfile
from pixelscope.io.review_native_decoder import (
    MAX_NATIVE_VERIFY_BYTES,
    ProductionNativeCandidateDecoder,
)
from pixelscope.io.review_repository import (
    ReviewCancelled,
    SourceResolutionV1,
    verify_review_source,
)
from pixelscope.io.yuv_profile import YuvProfile
from pixelscope.workers.task_worker import TaskWorker


def _revision(path: Path) -> tuple[int, int, int, int, int]:
    stat = path.stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


@dataclass(frozen=True)
class ApprovedCandidate:
    """One user-supplied candidate and separately user-approved native profile."""

    source_key: str
    path: Path
    profile: RawProfile | YuvProfile
    confirmed_by_user: bool

    def __post_init__(self) -> None:
        if not isinstance(self.path, Path) or not self.path.is_absolute():
            raise ValueError("candidate path must be explicit and absolute")
        if not isinstance(self.profile, RawProfile | YuvProfile):
            raise ValueError("approved candidate requires native RAW/YUV profile")
        if not isinstance(self.confirmed_by_user, bool):
            raise ValueError("relocation consent must be explicit")
        object.__setattr__(self, "profile", self.profile.copy(deep=True))


@dataclass(frozen=True)
class VerifiedCandidate:
    approved: ApprovedCandidate
    resolution: SourceResolutionV1
    file_revision: tuple[int, int, int, int, int] | None

    @property
    def verified(self) -> bool:
        return self.resolution.may_bind_historical_finding and self.file_revision is not None

    def still_current(self) -> bool:
        if not self.verified:
            return False
        try:
            return _revision(self.approved.path) == self.file_revision
        except OSError:
            return False


@dataclass(frozen=True)
class RestorePlan:
    epoch: int
    finding: ReviewFindingV1
    candidates: tuple[VerifiedCandidate, ...]


@dataclass(frozen=True)
class RestoreReport:
    epoch: int
    status: Literal["applied", "pending", "unavailable", "interrupted"]
    reason: str
    partial_state: bool = False


class CanonicalReviewRestoreAuthority(Protocol):
    """MainWindow-owner seam; no second registry or implicit Difference calculate.

    prepare() MUST be read-only and check candidates, profile and page intent
    before commit(). Commit may call canonical registration/selection/load APIs.
    retry() may be invoked ONLY on owner terminal load/layout notifications.
    """

    def prepare(self, plan: RestorePlan) -> object:
        ...

    def commit(self, prepared: object, plan: RestorePlan) -> RestoreReport:
        ...

    def retry(self, plan: RestorePlan) -> RestoreReport:
        ...

    def cancel(self, epoch: int) -> None:
        ...


def _verify_batch(
    sources: tuple[ReviewSourceV1, ...],
    candidates: tuple[ApprovedCandidate, ...],
    cancel: Event,
) -> tuple[VerifiedCandidate, ...]:
    """Worker-only, maximum six files, bounded and individually approved."""
    if len(sources) > 6 or len(sources) != len(candidates):
        raise ValueError("invalid Finding source verification cardinality")
    output: list[VerifiedCandidate] = []
    for source, candidate in zip(sources, candidates, strict=True):
        if cancel.is_set():
            raise ReviewCancelled("Finding verification was superseded")
        if source.source_key != candidate.source_key:
            raise ValueError("candidate identity/order changed")
        try:
            before = _revision(candidate.path)
        except OSError:
            before = None
        result = verify_review_source(
            source,
            candidate.path,
            ProductionNativeCandidateDecoder(candidate.profile),
            confirmed_by_user=candidate.confirmed_by_user,
            cancel=cancel.is_set,
            max_bytes=MAX_NATIVE_VERIFY_BYTES,
        )
        try:
            after = _revision(candidate.path)
        except OSError:
            after = None
        if before is None or after != before:
            result = SourceResolutionV1(
                source.source_key,
                "candidate_unverified",
                str(candidate.path),
                candidate.confirmed_by_user,
                "unavailable",
                "candidate revision changed",
            )
        output.append(
            VerifiedCandidate(
                candidate,
                result,
                after if result.may_bind_historical_finding else None,
            )
        )
    if cancel.is_set():
        raise ReviewCancelled("Finding verification was superseded")
    return tuple(output)


class ReviewRestoreController(QObject):
    """Single active epoch; no GUI callbacks from worker threads."""

    verification_completed = Signal(int, object)
    verification_failed = Signal(int, str)
    restore_completed = Signal(object)

    def __init__(
        self,
        library: ReviewLibrary,
        authority: CanonicalReviewRestoreAuthority,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.library = library
        self.authority = authority
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._epoch = 0
        self._closing = False
        self._task: TaskWorker | None = None
        self._task_id: str | None = None
        self._cancel_event: Event | None = None
        self._finding_id: str | None = None
        self._verified: tuple[VerifiedCandidate, ...] = ()
        self._pending: RestorePlan | None = None
        self._phase = "idle"

    @property
    def epoch(self) -> int:
        return self._epoch

    @property
    def phase(self) -> str:
        return self._phase

    @property
    def resolutions(self) -> dict[str, SourceResolutionV1]:
        return {item.approved.source_key: item.resolution for item in self._verified}

    def cancel(self) -> None:
        prior = self._pending
        self._epoch += 1
        if self._cancel_event is not None:
            self._cancel_event.set()
        if self._task is not None:
            self._task.cancel()
        self._cancel_event = None
        self._task = None
        self._task_id = None
        self._verified = ()
        self._finding_id = None
        self._pending = None
        self._phase = "idle"
        if prior is not None:
            self.authority.cancel(prior.epoch)

    def change_finding(self, finding_id: str | None) -> None:
        """Every Finding switch revokes pending hash/decode/load callbacks."""
        self.cancel()
        self._finding_id = finding_id

    def verify(
        self,
        finding_id: str,
        approved: Mapping[str, ApprovedCandidate],
    ) -> int:
        self.cancel()
        if self._closing:
            raise RuntimeError("Review controller is closed")
        finding = self.library.get(finding_id)
        source_lookup = {item.source_key: item for item in self.library.document.sources}
        sources = tuple(source_lookup[key] for key in finding.source_keys)
        if set(finding.source_keys) != set(approved):
            raise ValueError("each Finding source needs an explicit candidate and profile")
        candidates = tuple(approved[key] for key in finding.source_keys)
        if any(
            item.source_key != key
            for item, key in zip(candidates, finding.source_keys, strict=True)
        ):
            raise ValueError("candidate source key changed")
        self._finding_id = finding_id
        self._phase = "verifying"
        epoch = self._epoch
        event = Event()
        self._cancel_event = event
        worker = TaskWorker(_verify_batch, sources, candidates, event, generation=epoch)
        self._task = worker
        self._task_id = worker.task_id
        worker.signals.succeeded.connect(self._verified_ready)
        worker.signals.failed.connect(self._verify_failed)
        worker.signals.cancelled.connect(self._verify_cancelled)
        worker.signals.finished.connect(self._worker_finished)
        self._pool.start(worker)
        return epoch

    @Slot(str, object, int, object)
    def _verified_ready(
        self,
        task_id: str,
        _document: object,
        epoch: int,
        value: object,
    ) -> None:
        if (
            self._closing
            or epoch != self._epoch
            or task_id != self._task_id
            or self._phase != "verifying"
            or not isinstance(value, tuple)
            or any(not isinstance(item, VerifiedCandidate) for item in value)
        ):
            return
        self._verified = value
        self._phase = "verified"
        self.verification_completed.emit(epoch, self.resolutions)

    @Slot(str, object, int, object)
    def _verify_failed(
        self,
        task_id: str,
        _document: object,
        epoch: int,
        error: object,
    ) -> None:
        if self._closing or epoch != self._epoch or task_id != self._task_id:
            return
        self._phase = "unavailable"
        self.verification_failed.emit(epoch, str(getattr(error, "message", error)))

    @Slot(str, object, int)
    def _verify_cancelled(self, _task_id: str, _document: object, _epoch: int) -> None:
        # Already cancelled/revoked by current owner; never update new epochs.
        pass

    @Slot(str)
    def _worker_finished(self, task_id: str) -> None:
        if task_id == self._task_id:
            self._task = None
            self._task_id = None

    def activate(self, finding_id: str) -> RestoreReport:
        if self._closing:
            raise RuntimeError("Review controller is closed")
        if self._phase != "verified" or self._finding_id != finding_id:
            return RestoreReport(self._epoch, "unavailable", "Finding is not verified")
        resolutions = self.resolutions
        try:
            finding = self.library.preflight_finding(finding_id, resolutions)
            if any(not item.still_current() for item in self._verified):
                return RestoreReport(
                    self._epoch, "unavailable", "source changed after verification"
                )
            if tuple(item.approved.source_key for item in self._verified) != finding.source_keys:
                return RestoreReport(self._epoch, "unavailable", "source order changed")
            plan = RestorePlan(self._epoch, finding, self._verified)
            # prepare must not mutate the live Workspace. No commit if it raises.
            prepared = self.authority.prepare(plan)
        except (OSError, ValueError, RuntimeError) as exc:
            report = RestoreReport(self._epoch, "unavailable", str(exc))
            self.restore_completed.emit(report)
            return report
        # Commit is a point of no return for canonical source registration.
        # Failure after this line is PARTIAL, not a claimed atomic rollback.
        self._phase = "committing"
        try:
            report = self.authority.commit(prepared, plan)
        except Exception as exc:  # noqa: BLE001 - post-commit failures are partial
            report = RestoreReport(
                self._epoch,
                "unavailable",
                f"post-commit failure: {exc}",
                partial_state=True,
            )
        if report.epoch != self._epoch or self._closing:
            return RestoreReport(plan.epoch, "interrupted", "epoch superseded", True)
        if report.status == "pending":
            self._pending = plan
            self._phase = "pending"
        else:
            self._phase = report.status
        self.restore_completed.emit(report)
        return report

    def owner_terminal_notification(self, epoch: int) -> RestoreReport | None:
        """Only call after authoritative foreground-load/layout completion."""
        plan = self._pending
        if (
            self._closing
            or plan is None
            or epoch != self._epoch
            or plan.epoch != epoch
            or self._phase != "pending"
        ):
            return None
        if any(not item.still_current() for item in plan.candidates):
            report = RestoreReport(epoch, "unavailable", "verified candidate changed", True)
        else:
            try:
                report = self.authority.retry(plan)
            except Exception as exc:  # noqa: BLE001 - committed state may be partial
                report = RestoreReport(epoch, "unavailable", f"restore retry failure: {exc}", True)
        if report.status != "pending":
            self._pending = None
            self._phase = report.status
        self.restore_completed.emit(report)
        return report

    def shutdown(self) -> bool:
        if self._closing:
            return self._pool.waitForDone(3000)
        self.cancel()
        self._closing = True
        return self._pool.waitForDone(3000)
