from __future__ import annotations

from pathlib import Path
from typing import Any

from pixelscope.ui.comparison_set import SessionController as _BaseSessionController


class SessionController(_BaseSessionController):
    """Session-specific completion semantics layered on the P4-B loader bridge."""

    def open_from_path(self, path: str | Path) -> tuple[int, tuple[Path, ...]]:
        loaded, missing = super().open_from_path(path)
        if loaded == 0:
            return loaded, missing

        session = self.repository.load(path)
        if session.active_path is None:
            return loaded, missing
        active_key = session.active_path.casefold()
        active_document = next(
            (
                document
                for document in self.window.selected_documents
                if document.source_path is not None
                and str(document.source_path.resolve(strict=False)).casefold() == active_key
            ),
            None,
        )
        if active_document is not None:
            self.window._set_active_document(active_document)
        return loaded, missing


def install_session(window: Any) -> SessionController:
    existing = getattr(window, "session_controller", None)
    if isinstance(existing, SessionController):
        return existing
    controller = SessionController(window)
    window.session_controller = controller
    window.comparison_set_controller = controller
    return controller
