# ruff: noqa: E721  # Strict primitives: bool is not an integer.
"""Atomic local .pxreview repository and consent-gated source verification.

All IO here is Qt-free. Call streaming hashes and disk writes on bounded workers;
the repository never searches, relinks, imports or restores UI sources itself.
"""
from __future__ import annotations

import hashlib
import os
import stat
import tempfile
import threading
from collections.abc import Callable, Iterable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from pixelscope.core.review_record import (
    MAX_REVIEW_BYTES,
    ReviewDocumentV1,
    ReviewNativeSignatureV1,
    ReviewSourceV1,
    ReviewValidationError,
)

REVIEW_SUFFIX = ".pxreview"
HASH_CHUNK_BYTES = 1024 * 1024
CancelCheck = Callable[[], bool]
ProgressCallback = Callable[[int, int], None]
SignatureProvider = Callable[[Path], ReviewNativeSignatureV1]


class ReviewRepositoryError(OSError):
    """Safe persistence failure, without mutating any live workspace."""


class ReviewConflictError(ReviewRepositoryError):
    """Destination changed, cannot overwrite, or save already in progress."""


class ReviewCancelled(ReviewRepositoryError):
    """Cancellation before the repository's atomic publish point."""


class SourceHashUnstable(ReviewRepositoryError):
    """The on-disk source changed while its SHA-256 was being evaluated."""


@dataclass(frozen=True)
class ReviewSaveResult:
    path: Path
    revision_sha256: str
    committed: bool = True


@dataclass(frozen=True)
class SourceHashV1:
    sha256: str
    size_bytes: int
    mtime_ns: int


@dataclass(frozen=True)
class SourceResolutionV1:
    source_key: str
    status: str
    candidate_path: str | None
    confirmed_by_user: bool
    verification: str
    reason: str

    def __post_init__(self) -> None:
        try:
            if type(self.source_key) is not str or str(UUID(self.source_key)) != self.source_key:
                raise ValueError("noncanonical source UUID")
        except (ValueError, AttributeError) as exc:
            raise ReviewValidationError("invalid source resolution UUID") from exc
        if type(self.reason) is not str or not self.reason.strip() or len(self.reason) > 1024:
            raise ReviewValidationError("source resolution requires a bounded reason")
        if self.candidate_path is not None and (
            type(self.candidate_path) is not str or not Path(self.candidate_path).is_absolute()
        ):
            raise ReviewValidationError("candidate_path must be an absolute path")
        if self.status not in (
            "verified",
            "candidate_unverified",
            "changed",
            "missing",
            "unsupported_profile",
        ):
            raise ReviewValidationError("unknown source resolution status")
        if self.verification not in ("digest_match", "digest_mismatch", "unavailable"):
            raise ReviewValidationError("unknown source resolution evidence")
        if type(self.confirmed_by_user) is not bool or (
            self.status == "verified"
            and (self.verification != "digest_match" or self.candidate_path is None)
        ):
            raise ReviewValidationError("verified source requires digest and candidate")
        if self.status == "changed" and self.verification != "digest_mismatch":
            raise ReviewValidationError("changed source requires digest mismatch evidence")
        if self.status == "missing" and self.verification != "unavailable":
            raise ReviewValidationError("missing source cannot claim digest verification")

    @property
    def may_bind_historical_finding(self) -> bool:
        return self.status == "verified"


def _cancel_if_requested(cancel: CancelCheck | None) -> None:
    if cancel is not None and cancel():
        raise ReviewCancelled("review operation cancelled before commit")


def _identity(st: os.stat_result) -> tuple[int, int, int, int, int]:
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def stream_source_sha256(
    path: str | Path,
    *,
    cancel: CancelCheck | None = None,
    progress: ProgressCallback | None = None,
    max_bytes: int | None = None,
) -> SourceHashV1:
    """Full-file streaming SHA-256 with cancel, bounded memory and TOCTOU check.

    Stat and file-descriptor identity must remain stable across the read.
    Callers must also validate native interpretation from the same stable revision.
    """
    source = Path(path)
    _cancel_if_requested(cancel)
    before = source.stat()
    if not stat.S_ISREG(before.st_mode):
        raise ReviewRepositoryError("source must be a regular file")
    if max_bytes is not None and before.st_size > max_bytes:
        raise ReviewRepositoryError("source size exceeds user-approved hash budget")
    sha = hashlib.sha256()
    processed = 0
    with source.open("rb") as handle:
        opened = os.fstat(handle.fileno())
        if _identity(before) != _identity(opened):
            raise SourceHashUnstable("source changed before SHA-256 read")
        while True:
            _cancel_if_requested(cancel)
            chunk = handle.read(HASH_CHUNK_BYTES)
            if not chunk:
                break
            processed += len(chunk)
            if max_bytes is not None and processed > max_bytes:
                raise ReviewRepositoryError("source hash budget exceeded")
            sha.update(chunk)
            if progress is not None:
                progress(processed, before.st_size)
        at_end = os.fstat(handle.fileno())
    _cancel_if_requested(cancel)
    after = source.stat()
    if (
        processed != before.st_size
        or _identity(before) != _identity(at_end)
        or _identity(before) != _identity(after)
    ):
        raise SourceHashUnstable("source revision changed during SHA-256")
    return SourceHashV1(sha.hexdigest(), processed, before.st_mtime_ns)


def verify_review_source(
    source: ReviewSourceV1,
    candidate_path: str | Path | None,
    native_signature: ReviewNativeSignatureV1 | SignatureProvider | None,
    *,
    confirmed_by_user: bool = False,
    cancel: CancelCheck | None = None,
    progress: ProgressCallback | None = None,
    max_bytes: int | None = None,
) -> SourceResolutionV1:
    """Probe one explicit candidate, never auto-search/relink or mutate source keys.

    Exact same saved local path may be verified without a new relocation approval.
    Every other candidate, including one with a matching digest, requires consent.
    User approval is NOT sufficient when the digest is absent or mismatched.
    """
    _cancel_if_requested(cancel)
    if not isinstance(source, ReviewSourceV1):
        raise ReviewValidationError("ReviewSourceV1 expected")
    if type(confirmed_by_user) is not bool:
        raise ReviewValidationError("confirmed_by_user must be bool")

    def outcome(status: str, verification: str, reason: str) -> SourceResolutionV1:
        return SourceResolutionV1(
            source.source_key,
            status,
            str(Path(candidate_path).absolute()) if candidate_path is not None else None,
            confirmed_by_user,
            verification,
            reason,
        )

    if candidate_path is None:
        return outcome("missing", "unavailable", "no candidate supplied")
    path = Path(candidate_path)
    try:
        is_file = path.is_file()
    except OSError:
        is_file = False
    if not is_file:
        return outcome("missing", "unavailable", "candidate file is missing")
    saved_path = source.locator.local_path
    same_saved_path = saved_path is not None and os.path.normcase(
        os.path.realpath(path)
    ) == os.path.normcase(os.path.realpath(saved_path))
    try:
        initial_revision = _identity(path.stat())
        probe = stream_source_sha256(path, cancel=cancel, progress=progress, max_bytes=max_bytes)
    except (ReviewCancelled, KeyboardInterrupt):
        raise
    except OSError as exc:
        return outcome(
            "candidate_unverified",
            "unavailable",
            f"cannot safely hash candidate: {type(exc).__name__}",
        )

    prior_sha = source.fingerprint.digest
    if prior_sha is None:
        return outcome(
            "candidate_unverified",
            "unavailable",
            "saved SHA-256 is absent; metadata cannot prove identity",
        )
    if probe.sha256 != prior_sha:
        return outcome("changed", "digest_mismatch", "source SHA-256 differs")
    # A signature object computed outside this stat window is not sufficient
    # evidence that the decoder interpretation describes the hashed revision.
    # Pass the *specific candidate path* into the provider to prevent accidental
    # use of the current runtime source or a stale captured interpretation.
    if not callable(native_signature):
        return outcome(
            "candidate_unverified",
            "digest_match",
            "native decoder signature requires revision-bound provider",
        )
    try:
        _cancel_if_requested(cancel)
        current_signature = native_signature(path)
        _cancel_if_requested(cancel)
        if _identity(path.stat()) != initial_revision:
            raise SourceHashUnstable("file changed during decoder signature evaluation")
    except (ReviewCancelled, KeyboardInterrupt):
        raise
    except (ValueError, TypeError) as exc:
        return outcome(
            "unsupported_profile", "digest_match", f"decoder rejected profile: {type(exc).__name__}"
        )
    except OSError as exc:
        return outcome(
            "candidate_unverified",
            "digest_match",
            f"cannot verify stable decoder revision: {type(exc).__name__}",
        )
    if not isinstance(current_signature, ReviewNativeSignatureV1):
        return outcome(
            "unsupported_profile", "digest_match", "native decoder signature is unavailable"
        )
    if current_signature != source.native_signature:
        return outcome("unsupported_profile", "digest_match", "native decode signature differs")
    if not same_saved_path and not confirmed_by_user:
        return outcome(
            "candidate_unverified",
            "digest_match",
            "verified bytes require explicit relocation confirmation",
        )
    return outcome(
        "verified", "digest_match", "SHA-256 and revision-bound native decoder signature both match"
    )


def normalize_review_path(path: str | Path) -> Path:
    """Append, not replace, a supplied suffix; collision checks use this exact path."""
    value = Path(path).expanduser()
    if not value.name or value.name in (".", ".."):
        raise ReviewRepositoryError("invalid Review destination")
    if value.suffix.lower() != REVIEW_SUFFIX:
        value = value.with_name(value.name + REVIEW_SUFFIX)
    return value.absolute()


_lock_registry_guard = threading.Lock()
_lock_registry: dict[str, threading.RLock] = {}


def _lock_for(path: Path) -> threading.RLock:
    name = os.path.normcase(os.path.abspath(path))
    with _lock_registry_guard:
        if name not in _lock_registry:
            _lock_registry[name] = threading.RLock()
        return _lock_registry[name]


def _fsync_directory(directory: Path) -> None:
    if os.name == "nt":
        return
    try:
        fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        # Not all filesystems/operating systems permit syncing directory handles.
        pass


def _same_file(a: Path, b: Path) -> bool:
    try:
        return a.samefile(b)
    except OSError:
        return False


def _ensure_no_source_collision(
    destination: Path,
    document: ReviewDocumentV1,
    protected_paths: Iterable[str | Path],
) -> None:
    protected = [Path(path) for path in protected_paths]
    protected += [
        Path(source.locator.local_path)
        for source in document.sources
        if source.locator.local_path is not None
    ]
    if any(
        _same_file(destination, path)
        or (
            os.path.normcase(os.path.abspath(destination))
            == os.path.normcase(os.path.abspath(path))
        )
        for path in protected
    ):
        raise ReviewConflictError("Review destination conflicts with a source/protected file")


class ReviewRepository:
    """Fail-closed atomic writer with local destination locks and revision checks.

    Creation: save(path, doc) rejects existing targets; hardlink-based publication
    is exclusive and atomic. Updates: load_with_revision, then explicit
    save(..., overwrite=True, expected_revision=<loaded SHA-256>) of the same
    document UUID. A sibling exclusive .lock guards across processes; stale
    locks are NOT stolen automatically. No implicit session/source overwrites.
    """

    def load_with_revision(self, path: str | Path) -> tuple[ReviewDocumentV1, str]:
        target = Path(path)
        try:
            with target.open("rb") as handle:
                raw = handle.read(MAX_REVIEW_BYTES + 2)
            if len(raw) > MAX_REVIEW_BYTES:
                raise ReviewValidationError("Review input exceeds maximum byte budget")
            document = ReviewDocumentV1.from_bytes(raw)
            return document, hashlib.sha256(raw).hexdigest()
        except (OSError, UnicodeError, ValueError) as exc:
            raise ReviewRepositoryError(f"cannot load Review v1: {exc}") from exc

    def load(self, path: str | Path) -> ReviewDocumentV1:
        return self.load_with_revision(path)[0]

    def save(
        self,
        path: str | Path,
        document: ReviewDocumentV1,
        *,
        overwrite: bool = False,
        expected_revision: str | None = None,
        cancel: CancelCheck | None = None,
        protected_paths: Iterable[str | Path] = (),
    ) -> ReviewSaveResult:
        if not isinstance(document, ReviewDocumentV1):
            raise ReviewValidationError("ReviewDocumentV1 required")
        if type(overwrite) is not bool:
            raise ReviewValidationError("overwrite must be bool")
        if overwrite:
            if (
                type(expected_revision) is not str
                or len(expected_revision) != 64
                or any(char not in "0123456789abcdef" for char in expected_revision)
            ):
                raise ReviewConflictError("overwrite requires prior loaded SHA-256 revision")
        elif expected_revision is not None:
            raise ReviewConflictError("expected_revision applies only to explicit overwrite")
        target = normalize_review_path(path)
        protected_paths = tuple(protected_paths)
        _cancel_if_requested(cancel)
        if not target.parent.is_dir():
            raise ReviewRepositoryError("Review destination directory does not exist")
        if target.is_symlink():
            raise ReviewConflictError("refuse writing through destination symlink")
        _ensure_no_source_collision(target, document, protected_paths)
        raw = document.to_bytes()  # complete validation before filesystem mutations
        if len(raw) > MAX_REVIEW_BYTES:
            raise ReviewValidationError("Review input exceeds maximum byte budget")
        revision = hashlib.sha256(raw).hexdigest()

        with _lock_for(target):
            _cancel_if_requested(cancel)
            lock_path = target.with_name(f".{target.name}.lock")
            lock_fd: int | None = None
            temp_path: Path | None = None
            committed = False
            try:
                try:
                    lock_fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                except FileExistsError as exc:
                    raise ReviewConflictError("Review save in progress; lock exists") from exc
                # Check the final .pxreview destination under the cross-process lock.
                if target.is_symlink():
                    raise ReviewConflictError("destination became a symlink")
                _ensure_no_source_collision(target, document, protected_paths)
                if target.exists():
                    if not overwrite:
                        raise ReviewConflictError(
                            "Review destination exists; explicit overwrite required"
                        )
                    try:
                        mode = target.stat().st_mode
                        if not mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH):
                            raise ReviewConflictError("existing Review is read-only")
                        current, current_revision = self.load_with_revision(target)
                    except ReviewRepositoryError as exc:
                        raise ReviewConflictError(
                            "existing destination is not a valid Review"
                        ) from exc
                    if current.document_id != document.document_id:
                        raise ReviewConflictError("cannot overwrite unrelated Review document")
                    if current_revision != expected_revision:
                        raise ReviewConflictError("Review changed since loaded (CAS conflict)")
                elif overwrite:
                    raise ReviewConflictError("requested Review overwrite target is missing")
                _cancel_if_requested(cancel)
                fd, temp_name = tempfile.mkstemp(
                    dir=target.parent, prefix=f".{target.name}.", suffix=".tmp"
                )
                temp_path = Path(temp_name)
                with os.fdopen(fd, "wb") as handle:
                    handle.write(raw)
                    handle.flush()
                    os.fsync(handle.fileno())
                _cancel_if_requested(cancel)
                if overwrite:
                    # A second check catches competing non-cooperating writes
                    # before replacement (cross-process locking is advisory).
                    existing, revision_now = self.load_with_revision(target)
                    if existing.document_id != document.document_id or (
                        revision_now != expected_revision
                    ):
                        raise ReviewConflictError("Review changed during save")
                    os.replace(temp_path, target)
                else:
                    # os.replace is unsafe for create-only: a new target could
                    # have appeared after the initial collision check.
                    os.link(temp_path, target)
                committed = True  # publication point; cancellation now means success
                _fsync_directory(target.parent)
            except (OSError, ReviewValidationError):
                if committed:
                    return ReviewSaveResult(target, revision)
                raise
            finally:
                if temp_path is not None:
                    with suppress(OSError):
                        temp_path.unlink(missing_ok=True)
                if lock_fd is not None:
                    with suppress(OSError):
                        os.close(lock_fd)
                    with suppress(OSError):
                        lock_path.unlink(missing_ok=True)
                    _fsync_directory(target.parent)
            return ReviewSaveResult(target, revision)
