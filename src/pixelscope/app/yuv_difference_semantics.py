from __future__ import annotations

from typing import Any, cast

from pixelscope.core.difference_cache import DifferenceCacheKey


class NativeYuvDifferencePresentationLifecycle:
    """Bind native-YUV presentation to the exact Difference cache identity."""

    def __init__(self, window: Any) -> None:
        self.window = window
        self.panel = window.difference_panel
        self._pending_visible_key: DifferenceCacheKey | None = None
        self._original_store_difference_document = window._store_difference_document
        self._original_result_matches_current = window._difference_result_matches_current_pair
        self._original_set_documents = self.panel.set_documents

    def install(self) -> None:
        self.window.__dict__["_difference_result_key"] = None
        self.window._store_difference_document = self.store_difference_document
        self.window._difference_result_matches_current_pair = self.result_matches_current
        self.panel.set_documents = self.set_documents
        self.panel.channel.currentIndexChanged.connect(self.request_identity_changed)
        self.panel.a_selector.currentIndexChanged.connect(self.request_identity_changed)
        self.panel.b_selector.currentIndexChanged.connect(self.request_identity_changed)
        self.window.__dict__["native_yuv_difference_presentation_lifecycle"] = self

    def current_result_key(self) -> DifferenceCacheKey | None:
        return cast(DifferenceCacheKey | None, self.panel._cache_key())

    def _native_yuv_pair_selected(self) -> bool:
        pair = self.panel.selected_documents()
        return pair is not None and all(document.yuv_frame is not None for document in pair)

    def result_matches_current(self) -> bool:
        """Use exact identity for WP-C2 while preserving every legacy predicate."""

        presented_key = self.window.__dict__.get("_difference_result_key")
        if presented_key is not None:
            return (
                getattr(self.window, "_difference_document", None) is not None
                and presented_key == self.current_result_key()
            )
        if self._native_yuv_pair_selected() and getattr(
            self.window, "_difference_document", None
        ) is not None:
            return False
        return bool(self._original_result_matches_current())

    def set_documents(self, *args: object, **kwargs: object) -> None:
        """Preserve panel rebinding while retiring stale active YUV generations/layouts."""

        self._original_set_documents(*args, **kwargs)
        self.request_identity_changed()

    def request_identity_changed(self, _value: object = None) -> None:
        """Retire an active YUV result as soon as its exact request identity diverges."""

        presented_key = self.window.__dict__.get("_difference_result_key")
        if presented_key is None:
            return
        current_key = self.current_result_key()
        if current_key == presented_key:
            return

        if (
            self.window.diff_action.isChecked()
            and current_key is not None
            and self._native_yuv_pair_selected()
        ):
            self._pending_visible_key = current_key
        else:
            self._pending_visible_key = None

        self.window.__dict__["_difference_result_key"] = None
        curation = getattr(self.window, "difference_curation_lifecycle", None)
        if curation is not None:
            curation._reset_active_difference()
            return

        # Defensive fallback for reduced compositions. Production installs the
        # established DifferenceCurationLifecycle before WP-C2.
        self.window.diff_action.blockSignals(True)
        self.window.diff_action.setChecked(False)
        self.window.diff_action.blockSignals(False)
        self.window._difference_document = None
        self.window._difference_source_ids = None
        self.window._update_action_states()

    def store_difference_document(self, *args: object, **kwargs: object) -> None:
        """Attach exact YUV cache identity whenever MainWindow stores a derived result."""

        self._original_store_difference_document(*args, **kwargs)
        current_key = self.current_result_key()
        if (
            getattr(self.window, "_difference_document", None) is not None
            and current_key is not None
            and self._native_yuv_pair_selected()
        ):
            self.window.__dict__["_difference_result_key"] = current_key
        else:
            self.window.__dict__["_difference_result_key"] = None

        if self._pending_visible_key != current_key:
            return
        self._pending_visible_key = None
        # Restore explicit visibility only after the exact requested Y/U/V result has
        # actually been stored. An uncached switch never leaves the previous plane up.
        if not self.window.diff_action.isChecked():
            self.window.diff_action.setChecked(True)


def install_native_yuv_difference(window: Any) -> NativeYuvDifferencePresentationLifecycle:
    """Retire WP-C1's temporary block and install WP-C2 result-identity semantics."""

    existing = window.__dict__.get("native_yuv_difference_presentation_lifecycle")
    if isinstance(existing, NativeYuvDifferencePresentationLifecycle):
        return existing

    controller = window.__dict__.get("native_yuv_semantics_controller")
    if controller is None:
        raise RuntimeError("native YUV semantics must be installed before YUV Difference")

    difference = window.difference_panel
    difference.set_documents = controller._difference_set_documents_original
    difference.calculate_difference = controller._difference_calculate_original
    controller._difference_yuv_blocked = False

    lifecycle = NativeYuvDifferencePresentationLifecycle(window)
    lifecycle.install()
    window.__dict__["native_yuv_difference_installed"] = True
    return lifecycle
