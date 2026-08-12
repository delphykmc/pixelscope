from __future__ import annotations

from pathlib import Path
from typing import Any

from pixelscope.ui.comparison_set import SessionController as _BaseSessionController


class SessionController(_BaseSessionController):
    """Session-specific completion semantics layered on the P4-B loader bridge."""

    def open_from_path(self, path: str | Path) -> tuple[int, tuple[Path, ...]]:
        original_ensure_loaded = self.window._ensure_loaded
        ensured_ids: set[str] = set()

        def ensure_loaded_once(document: Any) -> None:
            document_id = str(document.document_id)
            if document_id in ensured_ids:
                return
            ensured_ids.add(document_id)
            original_ensure_loaded(document)

        self.window._ensure_loaded = ensure_loaded_once
        try:
            loaded, missing = super().open_from_path(path)
        finally:
            self.window._ensure_loaded = original_ensure_loaded

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


class _ComparisonSetControllerFacade:
    """Preserve P4-B internal API semantics while product/runtime ownership moves to Session."""

    def __init__(self, controller: SessionController) -> None:
        self._controller = controller

    def __getattr__(self, name: str) -> Any:
        return getattr(self._controller, name)

    def open_from_path(self, path: str | Path) -> tuple[int, tuple[Path, ...]]:
        loaded, missing = self._controller.open_from_path(path)
        if loaded == 0:
            return 0, missing
        return len(self._controller.window.selected_documents), missing


def install_session(window: Any) -> SessionController:
    existing = getattr(window, "session_controller", None)
    if isinstance(existing, SessionController):
        return existing
    controller = SessionController(window)
    window.session_controller = controller
    window.comparison_set_controller = _ComparisonSetControllerFacade(controller)
    return controller
