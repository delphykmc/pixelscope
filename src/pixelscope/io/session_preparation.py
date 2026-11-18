"""Filesystem-only preparation for GUI Session restore transactions."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pixelscope.core.cancellation import cancellation_checkpoint
from pixelscope.core.comparison_set import Session, SessionSource
from pixelscope.io.comparison_set_repository import ComparisonSetRepository
from pixelscope.io.path_discovery import (
    RegistrationInput,
    image_input_for_path,
    natural_sort_key,
    recent_path_state,
)


@dataclass(frozen=True)
class PreparedSession:
    path: Path
    state: str
    session: Session | None = None
    sources: tuple[tuple[SessionSource, RegistrationInput], ...] = ()
    missing: tuple[Path, ...] = ()


def prepare_recent_session(path: Path, repository: ComparisonSetRepository) -> PreparedSession:
    cancellation_checkpoint()
    state = recent_path_state(path)
    cancellation_checkpoint()
    if state in ("missing", "wrong_type"):
        return PreparedSession(path, state)
    session = repository.load(path)
    cancellation_checkpoint()
    sources: list[tuple[SessionSource, RegistrationInput]] = []
    missing: list[Path] = []
    for source in session.registered_sources:
        cancellation_checkpoint()
        source_path = Path(source.path)
        image_input = image_input_for_path(source_path)
        cancellation_checkpoint()
        if image_input is None:
            missing.append(source_path)
            continue
        canonical = image_input.path
        record = RegistrationInput(
            image_input,
            False,
            False,
            False,
            str(canonical).casefold(),
            canonical.parent,
            str(canonical.parent).casefold(),
            natural_sort_key(canonical),
        )
        sources.append((source, record))
    return PreparedSession(path, "usable", session, tuple(sources), tuple(missing))
