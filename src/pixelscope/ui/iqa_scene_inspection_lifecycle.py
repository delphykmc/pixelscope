"""P5-D lifecycle hardening around the viewer-linked Scene inspection controller."""

from __future__ import annotations

from types import MethodType
from typing import Any

from PySide6.QtCore import QObject, Slot

import pixelscope.ui.iqa_scene_inspection as inspection_module
from pixelscope.io.path_discovery import ImageInput
from pixelscope.remote.iqa_scene_inspection import (
    SceneVerificationOutcome,
    VerifiedSceneSource,
)
from pixelscope.remote.iqa_v2_domain import ResultV2
from pixelscope.workers.task_worker import TaskWorker


class IqaSceneInspectionLifecycle(QObject):
    """Bind native Inspect to decoded identity and newer local/settings intent."""

    def __init__(self, controller: Any, parent: QObject) -> None:
        super().__init__(parent)
        self.controller = controller
        self.window = controller.window
        self._settings_revision = 0
        self._inspect_settings_revision: int | None = None
        self._document_variant_aliases: dict[str, tuple[str, ...]] = {}

        self._original_return_to_local_workspace = controller.return_to_local_workspace
        self._original_sync_controls = controller._sync_controls
        self._original_cancel_inspect_worker = controller._cancel_inspect_worker
        self._original_verification_succeeded = controller._verification_succeeded
        self._original_verification_failed = controller._verification_failed

        remote_controller = getattr(self.window, "remote_iqa_controller", None)
        self._original_remote_settings_changed = (
            remote_controller.settings_changed if remote_controller is not None else None
        )

        def start_scene_verification(
            _controller: Any,
            result: ResultV2,
            scene_id: str,
        ) -> None:
            self._start_scene_verification(result, scene_id)

        def verification_succeeded(
            _controller: Any,
            task_id: str,
            document_id: object,
            generation: int,
            value: object,
        ) -> None:
            self._verification_succeeded(
                task_id,
                document_id,
                generation,
                value,
            )

        def verification_failed(
            _controller: Any,
            task_id: str,
            document_id: object,
            generation: int,
            error: object,
        ) -> None:
            self._verification_failed(
                task_id,
                document_id,
                generation,
                error,
            )

        def apply_verified_scene(
            _controller: Any,
            result: ResultV2,
            outcome: SceneVerificationOutcome,
        ) -> None:
            self._apply_verified_scene(result, outcome)

        def return_to_local_workspace(_controller: Any) -> None:
            self._return_to_local_workspace()

        def cancel_inspect_worker(_controller: Any) -> None:
            self._cancel_inspect_worker()

        def sync_controls(_controller: Any) -> None:
            self._sync_controls()

        def settings_changed(_controller: Any) -> None:
            self.settings_changed()

        controller._start_scene_verification = MethodType(
            start_scene_verification,
            controller,
        )
        controller._verification_succeeded = MethodType(
            verification_succeeded,
            controller,
        )
        controller._verification_failed = MethodType(
            verification_failed,
            controller,
        )
        controller._apply_verified_scene = MethodType(apply_verified_scene, controller)
        controller.return_to_local_workspace = MethodType(
            return_to_local_workspace,
            controller,
        )
        controller._cancel_inspect_worker = MethodType(cancel_inspect_worker, controller)
        controller._sync_controls = MethodType(sync_controls, controller)
        controller.settings_changed = MethodType(settings_changed, controller)

        if remote_controller is not None and self._original_remote_settings_changed is not None:

            def remote_settings_changed(_remote_controller: Any) -> None:
                assert self._original_remote_settings_changed is not None
                self._original_remote_settings_changed()
                self.settings_changed()

            remote_controller.settings_changed = MethodType(
                remote_settings_changed,
                remote_controller,
            )

        # The Return button was connected before this lifecycle wrapper was installed.
        # It is P5-D-owned, so reconnect it to the guarded method without touching any
        # unrelated MainWindow signal wiring.
        controller.return_button.clicked.disconnect()
        controller.return_button.clicked.connect(controller.return_to_local_workspace)

        # ReviewSelection owns Pick state. This listener observes the post-Pick state
        # only to invalidate P5-D Return; it never changes or clears curation itself.
        for viewer in controller._all_viewers():
            viewer.header.pick_requested.connect(self._review_pick_changed)

        self._sync_controls()

    @property
    def settings_revision(self) -> int:
        return self._settings_revision

    @property
    def document_variant_aliases(self) -> dict[str, tuple[str, ...]]:
        return dict(self._document_variant_aliases)

    def settings_changed(self) -> None:
        """Invalidate locator-dependent pending verification and refresh availability."""

        if not getattr(self.controller, "_active", False):
            return
        self._settings_revision += 1
        had_pending = self.controller._inspect_worker is not None
        self._cancel_inspect_worker()
        if had_pending:
            self.controller._set_status(
                "Remote IQA storage mappings changed · pending Inspect verification cancelled"
            )
        self._sync_controls()

    def _start_scene_verification(self, result: ResultV2, scene_id: str) -> None:
        self._cancel_inspect_worker()
        self.controller._inspect_generation += 1
        generation = self.controller._inspect_generation
        self.controller._inspect_local_intent_generation = self.controller._local_intent_generation
        self._inspect_settings_revision = self._settings_revision
        self.controller._inspect_result_identity = (result.result_id, id(result))
        self.controller._set_status(f"Verifying and decoding published sources for {scene_id}…")
        verify_scene_sources = vars(inspection_module)["verify_scene_sources"]
        worker = TaskWorker(
            verify_scene_sources,
            result,
            scene_id,
            self.window.application_settings.remote_iqa,
            generation=generation,
        )
        worker.signals.succeeded.connect(self.controller._verification_succeeded)
        worker.signals.failed.connect(self.controller._verification_failed)
        worker.signals.finished.connect(self.controller._verification_finished)
        self.controller._inspect_worker = worker
        self.controller._pool.start(worker)
        self._sync_controls()

    @Slot(str, object, int, object)
    def _verification_succeeded(
        self,
        task_id: str,
        document_id: object,
        generation: int,
        value: object,
    ) -> None:
        if self._inspect_settings_revision != self._settings_revision:
            return
        self._original_verification_succeeded(
            task_id,
            document_id,
            generation,
            value,
        )

    @Slot(str, object, int, object)
    def _verification_failed(
        self,
        task_id: str,
        document_id: object,
        generation: int,
        error: object,
    ) -> None:
        if self._inspect_settings_revision != self._settings_revision:
            return
        self._original_verification_failed(
            task_id,
            document_id,
            generation,
            error,
        )

    def _apply_verified_scene(
        self,
        result: ResultV2,
        outcome: SceneVerificationOutcome,
    ) -> None:
        """Commit only the exact decoded documents proven by the verification worker."""

        unique_sources: list[VerifiedSceneSource] = []
        variants_by_source: dict[str, list[str]] = {}
        for binding in outcome.sources:
            aliases = variants_by_source.setdefault(binding.source.source_id, [])
            aliases.append(binding.variant_id)
            if len(aliases) == 1:
                unique_sources.append(binding)

        if not unique_sources:
            self.controller._set_status("Scene has no verified native sources")
            self._sync_controls()
            return

        for binding in unique_sources:
            decoded = binding.decoded_document
            if decoded is None:
                self.controller._set_status(
                    "Inspect verification did not provide a decoded source generation"
                )
                self._sync_controls()
                return
            if decoded.encoded_source_sha256 != binding.source.sha256:
                self.controller._set_status("Decoded source identity no longer matches the result")
                self._sync_controls()
                return
            if decoded.shape[:2] != (binding.source.height, binding.source.width):
                self.controller._set_status("Decoded source dimensions no longer match the result")
                self._sync_controls()
                return

        captured_now = self.controller._return_snapshot is None
        if captured_now:
            self.controller._return_snapshot = self.controller._capture_return_snapshot()
            self.controller._return_valid = True

        inputs = tuple(ImageInput(item.local_path) for item in unique_sources)
        before_ids = set(self.window.documents)
        with self.controller._owned_mutation():
            document_ids = self.window._register_inputs(inputs, resolve_raw_profiles=False)
            if len(document_ids) != len(unique_sources):
                self._rollback_new_registrations(before_ids)
                if captured_now:
                    self.controller._return_snapshot = None
                    self.controller._return_valid = False
                self.controller._set_status(
                    "Scene registration failed; local workspace was preserved"
                )
                self._sync_controls()
                return

            # Publish every exact verified decoded generation before Selected/render can
            # make the Scene visible to viewer or analysis consumers. Load-token bumps
            # stale-drop any ordinary foreground/preload decode already in flight.
            for document_id, binding in zip(document_ids, unique_sources, strict=True):
                decoded = binding.decoded_document
                assert decoded is not None
                previous = self.window.documents[document_id]
                previous_sha = previous.encoded_source_sha256
                content_changed = previous_sha != decoded.encoded_source_sha256 and (
                    previous_sha is not None or previous.source is not None
                )

                self.window._load_tokens[document_id] = (
                    self.window._load_tokens.get(document_id, 0) + 1
                )
                decoded.document_id = document_id
                decoded.generation = previous.generation + int(content_changed)
                self.window.documents[document_id] = decoded
                if content_changed:
                    self.window._invalidate_channel_views(document_id)
                self.window._record_resident_source(decoded)
                self.window.residency_manager.touch(document_id)
                self.window._update_document_item(decoded)

            # Only now may the canonical Selected/current-page path render or start
            # analysis, so no stale resident generation is observable to consumers.
            self.window._select_document_ids(document_ids)
            self.window._evict_resident_documents()

        self.controller._inspect_scene_id = outcome.scene_id
        self.controller._inspected_result = result
        self.controller._inspected_document_variants = {
            document_id: variants_by_source[binding.source.source_id][0]
            for document_id, binding in zip(document_ids, unique_sources, strict=True)
        }
        self._document_variant_aliases = {
            document_id: tuple(variants_by_source[binding.source.source_id])
            for document_id, binding in zip(document_ids, unique_sources, strict=True)
        }
        self.controller._clear_spatial_overlay()
        binding_count = len(outcome.sources)
        source_count = len(unique_sources)
        if binding_count == source_count:
            identity_text = f"{source_count} native source(s)"
        else:
            identity_text = (
                f"{source_count} native source(s) / {binding_count} variant binding(s)"
            )
        self.controller._set_status(
            f"Inspecting {outcome.scene_id} · {identity_text} · decoded SHA verified"
        )
        self.controller._request_spatial_overlay()
        self._sync_controls()

    def _rollback_new_registrations(self, before_ids: set[str]) -> None:
        newly_registered = [
            document_id for document_id in self.window.documents if document_id not in before_ids
        ]
        if newly_registered:
            self.controller._original_remove_document_ids(newly_registered)

    def _return_to_local_workspace(self) -> None:
        review = getattr(self.window, "review_selection_controller", None)
        if bool(getattr(review, "active", False)):
            if self.controller._return_snapshot is not None:
                self.controller._local_intent_generation += 1
                self.controller._invalidate_return(
                    "Return invalidated by newer temporary Pick intent"
                )
            else:
                self.controller._set_status(
                    "Return is unavailable while temporary Picks are active"
                )
            self._sync_controls()
            return
        self._original_return_to_local_workspace()
        if not self.controller.return_valid:
            self._document_variant_aliases.clear()

    @Slot(bool)
    def _review_pick_changed(self, checked: bool) -> None:
        if not checked or self.controller._return_snapshot is None:
            return
        review = getattr(self.window, "review_selection_controller", None)
        if not bool(getattr(review, "active", False)):
            return
        self.controller._local_intent_generation += 1
        self.controller._invalidate_return("Return invalidated by newer temporary Pick intent")
        self._sync_controls()

    def _cancel_inspect_worker(self) -> None:
        self._original_cancel_inspect_worker()
        self._inspect_settings_revision = None

    def _sync_controls(self) -> None:
        self._original_sync_controls()
        review = getattr(self.window, "review_selection_controller", None)
        picks_active = bool(getattr(review, "active", False))
        self.controller.return_button.setEnabled(self.controller.return_valid and not picks_active)
        if picks_active and self.controller.return_valid:
            self.controller.return_button.setToolTip(
                "Return is disabled while temporary Picks are active"
            )
        elif self.controller.return_valid:
            self.controller.return_button.setToolTip(
                "Restore the captured pre-Inspect local comparison"
            )
        else:
            self.controller.return_button.setToolTip("No valid pre-Inspect Return target")


def install_iqa_scene_inspection_lifecycle(window: Any) -> IqaSceneInspectionLifecycle:
    """Install P5-D lifecycle hardening without creating another source authority."""

    controller = getattr(window, "iqa_scene_inspection_controller", None)
    if controller is None:
        raise RuntimeError("P5-D Scene inspection must be installed before lifecycle hardening")
    existing = getattr(window, "iqa_scene_inspection_lifecycle", None)
    if isinstance(existing, IqaSceneInspectionLifecycle):
        return existing
    guard = IqaSceneInspectionLifecycle(controller, window)
    window.iqa_scene_inspection_lifecycle = guard
    return guard
