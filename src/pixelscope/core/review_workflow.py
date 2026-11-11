"""W09b immutable Finding library and save/open authority.

Pure domain operations. Source registration, decoded pixels and W04 mutation
are deliberately not stored here; this model never opens or restores images.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path

from pixelscope.core.review_record import (
    ReviewDocumentV1,
    ReviewFindingV1,
    ReviewSourceV1,
    ReviewValidationError,
    ReviewWorkspaceIntentV1,
    new_review,
    utc_now,
)
from pixelscope.io.review_repository import (
    ReviewRepository,
    ReviewSaveResult,
    SourceResolutionV1,
    normalize_review_path,
)


class ReviewLibrary:
    """One editable local Review; history remains immutable by DTO replacement."""

    def __init__(self, repository: ReviewRepository | None = None) -> None:
        self.repository = repository or ReviewRepository()
        self.document = new_review()
        self.path: Path | None = None
        self.revision: str | None = None
        self.dirty = False

    def open(self, path: str | Path) -> ReviewDocumentV1:
        # Fully parse and validate *before* touching the currently open library.
        loaded, revision = self.repository.load_with_revision(path)
        self.document = loaded
        self.path = Path(path).absolute()
        self.revision = revision
        self.dirty = False
        return loaded

    def reset(self) -> None:
        self.document = new_review()
        self.path = None
        self.revision = None
        self.dirty = False

    def _replace(self, document: ReviewDocumentV1) -> None:
        self.document = replace(document, updated_utc=utc_now())
        self.dirty = True

    def add(
        self,
        finding: ReviewFindingV1,
        sources: Iterable[ReviewSourceV1],
    ) -> ReviewFindingV1:
        if not isinstance(finding, ReviewFindingV1):
            raise ReviewValidationError("ReviewFindingV1 expected")
        if any(f.id == finding.id for f in self.document.findings):
            raise ReviewValidationError("duplicate finding UUID")
        existing = {s.source_key: s for s in self.document.sources}
        ordered = list(self.document.sources)
        for source in sources:
            if not isinstance(source, ReviewSourceV1):
                raise ReviewValidationError("ReviewSourceV1 expected")
            prior = existing.get(source.source_key)
            if prior is not None and prior != source:
                raise ReviewValidationError("source UUID is bound to different historical content")
            if prior is None:
                ordered.append(source)
                existing[source.source_key] = source
        if not set(finding.source_keys) <= set(existing):
            raise ReviewValidationError("finding references unavailable Review source")
        old = self.document
        intent = replace(
            old.workspace_intent,
            source_order=tuple(s.source_key for s in ordered),
        )
        updated = replace(
            old,
            sources=tuple(ordered),
            workspace_intent=intent,
            findings=old.findings + (finding,),
            # A local editable Memo may retain its original file locations.
            # Portable reports must never inherit these private paths.
            allow_local_paths=old.allow_local_paths
            or any(source.locator.local_path is not None for source in ordered),
        )
        self._replace(updated)
        return finding

    def edit(self, finding_id: str, *, title: str, note: str, tags: tuple[str, ...]) -> None:
        if not any(f.id == finding_id for f in self.document.findings):
            raise KeyError(finding_id)
        # Replace metadata only; existing immutable evidence is never rebuilt.
        findings = tuple(
            replace(f, title=title, note=note, tags=tags) if f.id == finding_id else f
            for f in self.document.findings
        )
        self._replace(replace(self.document, findings=findings))

    def delete(self, finding_id: str) -> None:
        remaining = tuple(f for f in self.document.findings if f.id != finding_id)
        if len(remaining) == len(self.document.findings):
            raise KeyError(finding_id)
        # Keep historical source registration; sources may be used by other
        # findings or workspace intent, and pruning requires a separate policy.
        self._replace(replace(self.document, findings=remaining))

    def get(self, finding_id: str) -> ReviewFindingV1:
        return next(f for f in self.document.findings if f.id == finding_id)

    def save(
        self,
        path: str | Path,
        *,
        overwrite: bool = False,
        protected_paths: Iterable[str | Path] = (),
    ) -> ReviewSaveResult:
        target = normalize_review_path(path)
        same_revision = self.path == target and self.revision is not None
        if overwrite and not same_revision:
            raise ReviewValidationError(
                "cannot overwrite without a loaded revision of this exact Review"
            )
        # Commit can change only after the repository's exclusive/CAS barrier.
        result = self.repository.save(
            target,
            self.document,
            overwrite=overwrite,
            expected_revision=self.revision if overwrite else None,
            protected_paths=protected_paths,
        )
        if result.committed:
            self.path = result.path
            self.revision = result.revision_sha256
            self.dirty = False
        return result

    def preflight_finding(
        self,
        finding_id: str,
        verified: dict[str, SourceResolutionV1],
    ) -> ReviewFindingV1:
        """All-or-none historical activation; never 'fix' missing source roles."""
        finding = self.get(finding_id)
        for key in finding.source_keys:
            result = verified.get(key)
            if result is None or result.source_key != key or not result.may_bind_historical_finding:
                raise ReviewValidationError(f"cannot activate unverified source: {key}")
        return finding

    def replace_workspace_intent(self, intent: ReviewWorkspaceIntentV1) -> None:
        if not isinstance(intent, ReviewWorkspaceIntentV1):
            raise ReviewValidationError("ReviewWorkspaceIntentV1 expected")
        self._replace(replace(self.document, workspace_intent=intent))
