from __future__ import annotations

from typing import Any


class MultiViewReorderStabilityController:
    """Keep each source bound to its viewer while presentation order changes."""

    def __init__(self, window: Any) -> None:
        self.window = window
        self.view = window.multi_compare_view
        self._original_prepare = self.view._prepare_viewers_for_documents
        self._install()

    def _install(self) -> None:
        view = self.view

        def prepare_viewers_for_documents(documents: list[Any]) -> None:
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

        view._prepare_viewers_for_documents = prepare_viewers_for_documents


def install_multiview_reorder_stability(window: Any) -> MultiViewReorderStabilityController:
    existing = getattr(window, "multiview_reorder_stability_controller", None)
    if isinstance(existing, MultiViewReorderStabilityController):
        return existing
    controller = MultiViewReorderStabilityController(window)
    window.multiview_reorder_stability_controller = controller
    return controller
