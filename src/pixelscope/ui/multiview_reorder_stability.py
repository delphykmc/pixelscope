from __future__ import annotations

import weakref
from typing import Any

from pixelscope.ui.lifecycle_hooks import OwnerCallback


class MultiViewReorderStabilityController:
    """Keep each source bound to its viewer while presentation order changes."""

    def __init__(self, window: Any) -> None:
        self._window_ref = weakref.ref(window)
        self._view_ref = weakref.ref(window.multi_compare_view)
        self._install()

    @property
    def window(self) -> Any:
        window = self._window_ref()
        if window is None:
            raise RuntimeError("Multi-view window was destroyed")
        return window

    @property
    def view(self) -> Any:
        view = self._view_ref()
        if view is None:
            raise RuntimeError("Multi-view was destroyed")
        return view

    def _install(self) -> None:
        self.view._prepare_viewers_for_documents = OwnerCallback(self.prepare_viewers_for_documents)

    def prepare_viewers_for_documents(self, documents: list[Any]) -> None:
        view = self.view
        target_documents = documents[: view.capacity]
        target_ids = tuple(document.document_id for document in target_documents)
        target_has_difference = any(
            document.channel_layout == "DIFFERENCE" for document in target_documents
        )
        if target_ids == view._presentation_document_ids:
            return

        # Reuse viewers by document identity for every presentation reorder, not
        # only when Difference membership changes. This preserves viewer-local
        # Display Gain previews and prevents a canonical 1x frame from flashing
        # while gain>1 is regenerated after Primary swaps.
        view._reuse_viewers_for_documents(target_documents)
        view._presentation_document_ids = target_ids
        view._presentation_has_difference = target_has_difference


def install_multiview_reorder_stability(window: Any) -> MultiViewReorderStabilityController:
    existing = getattr(window, "multiview_reorder_stability_controller", None)
    if isinstance(existing, MultiViewReorderStabilityController):
        return existing
    controller = MultiViewReorderStabilityController(window)
    window.multiview_reorder_stability_controller = controller
    return controller
