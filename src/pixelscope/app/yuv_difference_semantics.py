from __future__ import annotations

from typing import Any

from pixelscope.core.difference_cache import DifferenceCacheKey


class NativeYuvDifferencePresentationLifecycle:
    """Bind presented Difference state to the panel's full cache/result identity."""

    def __init__(self, window: Any) -> None:
        self.window = window
        self.panel = window.difference_panel
        self._pending_visible_key: DifferenceCacheKey | None = None

    def install(self) -> None:
        self.window.__dict__["_difference_result_key"] = None
        curation = getattr(self.window, "difference_curation_lifecycle", None)
        if curation is not None:
            # P4's pair-only active binding predates channel-specific YUV maps. Keep
            # the existing curation lifecycle, but make its active-result predicate
            # use the authoritative Difference cache key for every family.
            curation._active_result_bound = self.active_result_matches_current
        self.window._difference_result_matches_current_pair = self.active_result_matches_current

        # MainWindow's existing slots were connected during construction, so these
        # observers run after presentation storage and attach the exact identity that
        # produced the newly presented Difference document.
        self.panel.result_ready.connect(self.result_presented)
        self.panel.preview_updated.connect(self.result_presented)
        self.panel.channel.currentIndexChanged.connect(self.channel_changed)
        self.panel.a_selector.currentIndexChanged.connect(self.pair_changed)
        self.panel.b_selector.currentIndexChanged.connect(self.pair_changed)
        self.window.__dict__["native_yuv_difference_presentation_lifecycle"] = self

    def current_result_key(self) -> DifferenceCacheKey | None:
        return self.panel._cache_key()

    def active_result_matches_current(self) -> bool:
        return (
            getattr(self.window, "_difference_document", None) is not None
            and self.window.__dict__.get("_difference_result_key") == self.current_result_key()
        )

    def _native_yuv_pair_selected(self) -> bool:
        pair = self.panel.selected_documents()
        return pair is not None and all(document.yuv_frame is not None for document in pair)

    def pair_changed(self, _value: object = None) -> None:
        # Visibility intent belongs to one exact pair/channel identity and must never
        # migrate to a different A/B selection.
        self._pending_visible_key = None

    def channel_changed(self, _value: object = None) -> None:
        if not self._native_yuv_pair_selected():
            return
        current_key = self.current_result_key()
        presented_key = self.window.__dict__.get("_difference_result_key")
        if current_key is None or presented_key == current_key:
            return

        difference = getattr(self.window, "_difference_document", None)
        if difference is None:
            if self._pending_visible_key is not None:
                self._pending_visible_key = current_key
            return

        if self.window.diff_action.isChecked():
            self._pending_visible_key = current_key
        self.window.__dict__["_difference_result_key"] = None

        curation = getattr(self.window, "difference_curation_lifecycle", None)
        if curation is not None:
            curation._reset_active_difference()
        else:
            # Defensive fallback for non-production tests/composition. Production
            # always installs DifferenceCurationLifecycle before native YUV semantics.
            self.window.diff_action.blockSignals(True)
            self.window.diff_action.setChecked(False)
            self.window.diff_action.blockSignals(False)
            self.window._difference_document = None
            self.window._difference_source_ids = None
            self.window._update_action_states()

    def result_presented(
        self,
        _title: object,
        _numerical: object,
        _preview: object,
    ) -> None:
        if getattr(self.window, "_difference_document", None) is None:
            return
        current_key = self.current_result_key()
        if current_key is None:
            return
        self.window.__dict__["_difference_result_key"] = current_key
        self.window._update_action_states()

        if self._pending_visible_key != current_key:
            return
        self._pending_visible_key = None
        # The previous plane was visible when its identity became stale. Restore that
        # explicit visibility intent only after the new exact-key result is published.
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
