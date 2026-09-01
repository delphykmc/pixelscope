from __future__ import annotations

from typing import Any

from pixelscope.core.image_document import ImageDocument
from pixelscope.core.preload import PreloadMemberRequest
from pixelscope.io.raw_profile import RawProfile
from pixelscope.io.yuv_profile import YuvProfile

InputProfile = RawProfile | YuvProfile


class NativeYuvRuntimeContracts:
    """Widen legacy preload-result guards to resolved native YUV profiles."""

    def __init__(self, window: Any) -> None:
        self.window = window

    def install(self) -> None:
        # NativeYuvSemanticsController forwards resolved profiles into the established
        # worker path. Only the legacy RawProfile-only result guards need widening so
        # YUV gets identical stale-drop and foreground-promotion behavior.
        self.window._promoted_preload_is_current = self.promoted_preload_is_current
        self.window._preload_succeeded = self.preload_succeeded
        self.window.__dict__["native_yuv_runtime_contracts"] = self

    @staticmethod
    def _resolved_profile(profile: object) -> InputProfile | None:
        return profile if isinstance(profile, (RawProfile, YuvProfile)) else None

    def promoted_preload_is_current(
        self,
        task_id: str,
        request: PreloadMemberRequest,
        *,
        require_result: ImageDocument | None = None,
    ) -> bool:
        foreground_token = self.window._promoted_preload_tokens.get(task_id)
        if foreground_token is None or not self.window.preload_controller.request_is_promoted(
            request
        ):
            return False
        document = self.window.documents.get(request.document_id)
        profile = self.window._raw_profiles.get(request.document_id)
        if not (
            document is not None
            and document.source is None
            and document.loading_state == "loading"
            and document.source_path is not None
            and document.generation == request.document_generation
            and self.window._path_key(document.source_path) == request.source_path_identity
            and self.window._raw_profile_identity(profile) == request.profile_identity
            and self.window.application_settings.require_exact_raw_file_size
            == request.require_exact_raw_size
            and self.window._load_tokens.get(request.document_id) == foreground_token
            and request.document_id not in self.window._load_worker_targets.values()
        ):
            return False
        if require_result is None:
            return True
        return (
            require_result.source_path is not None
            and self.window._path_key(require_result.source_path) == request.source_path_identity
            and self.window._raw_profile_identity(
                self._resolved_profile(require_result.raw_profile)
            )
            == request.profile_identity
        )

    def preload_succeeded(self, task_id: str, result: object) -> None:
        request = self.window._preload_worker_requests.get(task_id)
        promoted_token = self.window._promoted_preload_tokens.get(task_id)
        if request is None:
            if promoted_token is not None:
                self.window._normal_load_stale_drop_count += 1
            else:
                self.window.preload_controller.record_stale_drop()
            return
        if promoted_token is not None:
            if not isinstance(result, ImageDocument) or not self.promoted_preload_is_current(
                task_id,
                request,
                require_result=result,
            ):
                self.window._normal_load_stale_drop_count += 1
                return
            self.window._load_succeeded(request.document_id, promoted_token, result)
            return
        if not isinstance(result, ImageDocument):
            self.window.preload_controller.record_stale_drop()
            return

        document = self.window.documents.get(request.document_id)
        current_plan = self.window.preload_controller.current_plan
        profile = self.window._raw_profiles.get(request.document_id)
        valid = (
            current_plan is not None
            and current_plan.generation == request.plan_generation
            and request.document_id in current_plan.document_ids
            and self.window.preload_controller.request_is_current(request)
            and document is not None
            and document.source is None
            and document.source_path is not None
            and document.generation == request.document_generation
            and self.window._path_key(document.source_path) == request.source_path_identity
            and result.source_path is not None
            and self.window._path_key(result.source_path) == request.source_path_identity
            and self.window._raw_profile_identity(profile) == request.profile_identity
            and self.window._raw_profile_identity(self._resolved_profile(result.raw_profile))
            == request.profile_identity
            and self.window.application_settings.require_exact_raw_file_size
            == request.require_exact_raw_size
            and self.window._load_tokens.get(request.document_id, 0) == request.normal_load_token
            and request.document_id not in self.window._load_worker_targets.values()
        )
        if not valid:
            self.window.preload_controller.record_stale_drop()
            return

        result.document_id = request.document_id
        result.generation = request.document_generation
        self.window.documents[request.document_id] = result
        self.window._record_resident_source(result)
        self.window.residency_manager.touch(request.document_id)
        self.window._update_document_item(result)
        self.window._evict_resident_documents()
        retained = self.window.documents[request.document_id].source is not None
        self.window.preload_controller.accept_success(
            request.plan_generation,
            request.document_id,
            retained=retained,
        )


def install_native_yuv_runtime_contracts(window: Any) -> NativeYuvRuntimeContracts:
    existing = getattr(window, "native_yuv_runtime_contracts", None)
    if isinstance(existing, NativeYuvRuntimeContracts):
        return existing
    controller = NativeYuvRuntimeContracts(window)
    controller.install()
    return controller
