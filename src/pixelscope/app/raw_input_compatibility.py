from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QDialog, QMessageBox

from pixelscope.core.image_document import ImageDocument
from pixelscope.io.path_discovery import ImageInput, is_raw_like_path
from pixelscope.io.raw_profile import RawProfile
from pixelscope.ui.raw_open_dialog import RawOpenDialog


class RawInputCompatibilityController:
    """Extend the established RAW lifecycle to WP-B raw-like binary inputs.

    The existing MainWindow remains authoritative for ordinary images and legacy
    ``.raw`` behavior. This controller only widens the same profile-resolution,
    foreground-load, and preload guards to ``.data``/``.yuv`` while adding the
    lower-priority ``.imgprops`` sidecar path.
    """

    def __init__(self, window: Any) -> None:
        self.window = window
        self._register_input_original: Callable[..., str | None] = window._register_input
        self._confirm_raw_profile_original: Callable[
            [ImageInput, str | None], RawProfile | None
        ] = window._confirm_raw_profile
        self._ensure_loaded_original: Callable[[ImageDocument], None] = window._ensure_loaded

    def install(self) -> None:
        self.window._register_input = self.register_input
        self.window._confirm_raw_profile = self.confirm_raw_profile
        self.window._ensure_loaded = self.ensure_loaded
        self.window._refresh_preload_plan = self.refresh_preload_plan
        self.window.__dict__["raw_input_compatibility_controller"] = self

    def register_input(
        self,
        image_input: ImageInput,
        *,
        resolve_raw_profile: bool = True,
    ) -> str | None:
        """Route ``.data`` and ``.yuv`` through the same generic RAW profile flow."""

        if image_input.path.suffix.casefold() == ".raw" or not is_raw_like_path(
            image_input.path
        ):
            return self._register_input_original(
                image_input,
                resolve_raw_profile=resolve_raw_profile,
            )

        key = self.window._path_key(image_input.path)
        existing = self.window._document_id_by_path.get(key)
        raw_profile: RawProfile | None = None
        if resolve_raw_profile:
            raw_profile = self.window._confirm_raw_profile(image_input, existing)
            if raw_profile is None:
                return None
        if existing is not None:
            if image_input.raw_profile_path is not None:
                self.window._raw_profile_paths[existing] = image_input.raw_profile_path
            if raw_profile is not None:
                self.window._raw_profiles[existing] = raw_profile
                self.window._mark_raw_for_reload(existing, raw_profile)
            return existing

        document = ImageDocument.pending_document(image_input.path)
        self.window.documents[document.document_id] = document
        self.window._document_id_by_path[key] = document.document_id
        self.window._add_document_to_folder(document.document_id, image_input.path)
        if image_input.raw_profile_path is not None:
            self.window._raw_profile_paths[document.document_id] = image_input.raw_profile_path
        if raw_profile is not None:
            self.window._raw_profiles[document.document_id] = raw_profile
        self.window.document_list.add_document_item(
            document.document_id,
            self.window._document_item_text(document),
            image_input.path,
            str(image_input.path),
            loading_state=document.loading_state,
            resident=False,
        )
        return document.document_id

    def confirm_raw_profile(
        self,
        image_input: ImageInput,
        existing_id: str | None,
    ) -> RawProfile | None:
        """Insert ``.imgprops`` below JSON and above editable/default resolution."""

        sidecar = image_input.raw_profile_path
        if sidecar is None or sidecar.suffix.casefold() != ".imgprops":
            return self._confirm_raw_profile_original(image_input, existing_id)

        try:
            initial_profile = RawProfile.load_imgprops(sidecar)
        except Exception as exc:  # noqa: BLE001 - user may correct it in the dialog
            QMessageBox.warning(
                self.window,
                "Cannot load RAW sidecar",
                f"{sidecar.name}: {exc}\nUsing editable defaults.",
            )
            return self._confirm_raw_profile_original(
                ImageInput(image_input.path, None),
                existing_id,
            )

        dialog = RawOpenDialog(self.window)
        set_source_path = getattr(dialog, "set_source_path", None)
        if callable(set_source_path):
            set_source_path(image_input.path)
        dialog.set_profile(initial_profile, stride_is_auto=True)
        set_option_visible = getattr(
            dialog,
            "set_json_confirmation_option_visible",
            None,
        )
        if callable(set_option_visible):
            set_option_visible(False)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.profile()

    def ensure_loaded(self, document: ImageDocument) -> None:
        """Require a RAW profile before decoding non-``.raw`` raw-like sources."""

        source_path = document.source_path
        if (
            source_path is None
            or source_path.suffix.casefold() == ".raw"
            or not is_raw_like_path(source_path)
        ):
            self._ensure_loaded_original(document)
            return
        if document.loading_state != "pending":
            return

        profile = self.window._raw_profiles.get(document.document_id)
        if profile is None:
            if document.document_id in self.window._raw_profile_prompt_suppressed:
                return
            profile = self.window._confirm_raw_profile(
                ImageInput(
                    source_path,
                    self.window._raw_profile_paths.get(document.document_id),
                ),
                document.document_id,
            )
            if profile is None:
                self.window._raw_profile_prompt_suppressed.add(document.document_id)
                self.window.statusBar().showMessage(
                    f"RAW profile required to load {document.display_name}",
                    4000,
                )
                return
            self.window._raw_profile_prompt_suppressed.discard(document.document_id)
            self.window._raw_profiles[document.document_id] = profile
            document.channel_layout = profile.channel_layout
            document.bit_depth = profile.bit_depth
            document.raw_profile = profile

        if self.window._preload_workers:
            self.window._invalidate_preload_plan()
        document.loading_state = "loading"
        self.window._update_document_item(document)
        self.window._start_load(document.document_id, source_path, profile)

    def refresh_preload_plan(self) -> None:
        """Keep profile-less raw-like inputs out of speculative ordinary decoding."""

        if self.window._closing:
            self.window._invalidate_preload_plan()
            return
        navigation_plan = (
            self.window._plan_folder_navigation(1)
            if self.window.preload_controller.enabled
            else None
        )
        target_ids = navigation_plan.document_ids if navigation_plan is not None else ()
        previous = self.window.preload_controller.current_plan
        current = self.window.preload_controller.set_plan(target_ids)
        if previous is not current:
            self.window._cancel_preload_workers()
        if current is None or self.window._workers or self.window._preload_workers:
            return

        for document_id in self.window.preload_controller.pending_document_ids:
            document = self.window.documents.get(document_id)
            if document is None:
                self.window.preload_controller.complete_available_member(
                    current.generation,
                    document_id,
                )
                continue
            if document.source is not None or document.loading_state == "error":
                self.window.preload_controller.complete_available_member(
                    current.generation,
                    document_id,
                )
                continue
            if document.source_path is None or document.loading_state != "pending":
                self.window.preload_controller.complete_available_member(
                    current.generation,
                    document_id,
                )
                continue

            profile = self.window._raw_profiles.get(document_id)
            if is_raw_like_path(document.source_path) and profile is None:
                self.window.preload_controller.complete_available_member(
                    current.generation,
                    document_id,
                )
                continue
            self.window._start_preload(current.generation, document, profile)
            return


def install_raw_input_compatibility(window: Any) -> RawInputCompatibilityController:
    existing = getattr(window, "raw_input_compatibility_controller", None)
    if isinstance(existing, RawInputCompatibilityController):
        return existing
    controller = RawInputCompatibilityController(window)
    controller.install()
    return controller
