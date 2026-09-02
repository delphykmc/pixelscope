from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from contextlib import suppress
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QDialog, QMessageBox

from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineProfileResult, LineSelection
from pixelscope.core.roi import RoiAnalysisResult, RoiBounds
from pixelscope.core.yuv import analyze_yuv_roi, selected_yuv_line_profile
from pixelscope.io.path_discovery import ImageInput
from pixelscope.io.yuv_profile import YuvProfile
from pixelscope.ui.comparison_analysis_panel import automatic_histogram_spec
from pixelscope.ui.design_tokens import channel_button_style
from pixelscope.ui.plot_colors import channel_color
from pixelscope.ui.yuv_open_dialog import YuvOpenDialog
from pixelscope.workers.task_worker import TaskWorker


class NativeYuvSemanticsController:
    """Compose WP-C1 YUV authority into the existing document/UI lifecycle."""

    def __init__(self, window: Any) -> None:
        self.window = window
        self._confirm_profile_original: Callable[..., object | None] = window._confirm_raw_profile
        self._start_preload_original: Callable[..., None] = window._start_preload
        self._record_resident_original: Callable[[ImageDocument], None] = (
            window._record_resident_source
        )
        self._evict_original: Callable[[], None] = window._evict_resident_documents
        self._mark_reload_original: Callable[..., None] = window._mark_raw_for_reload
        self._update_actions_original: Callable[[], None] = window._update_action_states
        self._inspect_pixel_original: Callable[[int, int, object], None] = window._inspect_pixel
        self._pixel_status_original: Callable[..., str] = window._pixel_status_text

        analysis = window.comparison_analysis_panel
        self._analysis_set_documents_original = analysis.set_documents
        self._analysis_refresh_original = analysis.refresh
        self._analysis_buttons_original = dict(analysis.channel_buttons)

        line = window.line_profile_panel
        self._line_set_documents_original = line.set_documents
        self._line_refresh_original = line.refresh
        self._line_buttons_original = dict(line.channel_buttons)

        difference = window.difference_panel
        self._difference_set_documents_original = difference.set_documents
        self._difference_calculate_original = difference.calculate_difference
        self._difference_yuv_blocked = False

    def install(self) -> None:
        window = self.window
        window._confirm_raw_profile = self.confirm_profile
        window._start_preload = self.start_preload
        window._record_resident_source = self.record_resident_source
        window._evict_resident_documents = self.evict_resident_documents
        window._mark_raw_for_reload = self.mark_for_reload
        window._update_action_states = self.update_action_states
        window._pixel_status_text = self.pixel_status_text

        with suppress(RuntimeError, TypeError):
            window.viewer.cursor_moved.disconnect(self._inspect_pixel_original)
        window.viewer.cursor_moved.connect(self.inspect_pixel)

        analysis = window.comparison_analysis_panel
        analysis.set_documents = self.set_analysis_documents
        with suppress(RuntimeError, TypeError):
            analysis._refresh_timer.timeout.disconnect(self._analysis_refresh_original)
        analysis._refresh_timer.timeout.connect(self.refresh_analysis)

        line = window.line_profile_panel
        line.set_documents = self.set_line_documents
        line.refresh = self.refresh_line_profile

        difference = window.difference_panel
        difference.set_documents = self.set_difference_documents
        difference.calculate_difference = self.calculate_difference
        window.__dict__["native_yuv_semantics_controller"] = self
        self.update_action_states()

    def confirm_profile(
        self,
        image_input: ImageInput,
        existing_id: str | None,
    ) -> object | None:
        """Use native YUV only when explicitly selected or described by a YUV JSON."""

        if image_input.path.suffix.casefold() != ".yuv":
            return self._confirm_profile_original(image_input, existing_id)

        sidecar = image_input.raw_profile_path
        if sidecar is not None and sidecar.suffix.casefold() == ".json":
            try:
                payload = json.loads(sidecar.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = None
            layout = payload.get("channel_layout") if isinstance(payload, dict) else None
            if layout in ("YUV444", "YUV422", "YUV420"):
                try:
                    return YuvProfile.parse_obj(payload)
                except ValidationError as exc:
                    QMessageBox.warning(
                        self.window,
                        "Cannot load YUV sidecar",
                        f"{sidecar.name}: {exc}\nUsing editable YUV settings.",
                    )
                    return self._show_yuv_dialog(image_input.path, existing_id, None)
            # A valid legacy RAW JSON remains authoritative for `.yuv` under WP-B.
            return self._confirm_profile_original(image_input, existing_id)

        # `.imgprops` is a WP-B RAW/Bayer contract. Do not reinterpret it as YUV.
        if sidecar is not None and sidecar.suffix.casefold() == ".imgprops":
            return self._confirm_profile_original(image_input, existing_id)

        initial = None
        if existing_id is not None:
            existing = self.window._raw_profiles.get(existing_id)
            if isinstance(existing, YuvProfile):
                initial = existing
            elif isinstance(self.window.documents.get(existing_id), ImageDocument):
                document = self.window.documents[existing_id]
                if isinstance(document.raw_profile, YuvProfile):
                    initial = document.raw_profile
        return self._show_yuv_dialog(image_input.path, existing_id, initial)

    def _show_yuv_dialog(
        self,
        path: Path,
        existing_id: str | None,
        initial: YuvProfile | None,
    ) -> object | None:
        dialog = YuvOpenDialog(self.window)
        dialog.set_source_path(path)
        if initial is not None:
            dialog.set_profile(initial)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        if dialog.uses_generic_raw():
            return self._confirm_profile_original(ImageInput(path, None), existing_id)
        return dialog.profile()

    def start_preload(
        self,
        plan_generation: int,
        document: ImageDocument,
        profile: object | None,
    ) -> None:
        """Reuse the established bounded preload worker path for resolved profiles."""

        self._start_preload_original(plan_generation, document, profile)

    def record_resident_source(self, document: ImageDocument) -> None:
        if document.yuv_frame is None:
            self._record_resident_original(document)
            return
        self.window.residency_manager.record(document.document_id, document.native_nbytes)

    def evict_resident_documents(self) -> None:
        self._evict_original()
        for document in self.window.documents.values():
            if (
                document.source is None
                and document.source_path is not None
                and document.yuv_frame is not None
            ):
                document.yuv_frame = None

    def mark_for_reload(self, document_id: str, profile: object) -> None:
        self._mark_reload_original(document_id, profile)
        document = self.window.documents.get(document_id)
        if document is not None:
            document.yuv_frame = None

    def update_action_states(self) -> None:
        self._update_actions_original()
        documents = self.window.selected_documents
        action = self.window.action_map.get("Split Channels")
        if action is None or len(documents) != 1:
            return
        document = documents[0]
        if document.yuv_frame is None:
            return
        action.setEnabled(True)
        tooltip = (
            "Return to the combined image view"
            if action.isChecked()
            else "Split native Y, U, and V planes at their native resolutions"
        )
        action.setToolTip(tooltip)
        action.setStatusTip(tooltip)

    def inspect_pixel(self, x: int, y: int, _value: object) -> None:
        document = self.window.viewer.document
        if document is None:
            return
        value = document.pixel_at(x, y)
        self.window._set_pixel_status(self.pixel_status_text(x, y, [value], [document]))
        self.window._set_active_document(document)

    def pixel_status_text(
        self,
        x: int,
        y: int,
        values: Sequence[object],
        documents: Sequence[ImageDocument] | None = None,
    ) -> str:
        documents = tuple(documents or ())
        has_yuv = any(
            index < len(documents) and documents[index].yuv_frame is not None
            for index in range(len(values))
        )
        if not has_yuv:
            return self._pixel_status_original(x, y, values, documents)

        entries: list[str] = []
        yuv_values: list[tuple[int, int, int]] = []
        for index, value in enumerate(values):
            document = documents[index] if index < len(documents) else None
            if (
                document is not None
                and document.yuv_frame is not None
                and isinstance(value, tuple)
                and len(value) >= 3
            ):
                native = (int(value[0]), int(value[1]), int(value[2]))
                yuv_values.append(native)
                formatted = ", ".join(
                    f"{name}{component:4d}"
                    for name, component in zip(("Y", "U", "V"), native, strict=True)
                )
                entries.append(f"{index + 1} ({formatted})")
                continue
            fallback = self._pixel_status_original(
                x,
                y,
                [value],
                [document] if document else [],
            )
            _coordinate, _separator, formatted = fallback.partition("  |  ")
            entries.append(formatted or f"{index + 1} —")

        if len(yuv_values) == 2 and len(values) == 2:
            delta = tuple(b - a for a, b in zip(yuv_values[0], yuv_values[1], strict=True))
            entries.append(
                "Δ ("
                + ", ".join(
                    f"{name}{component:+d}"
                    for name, component in zip(("Y", "U", "V"), delta, strict=True)
                )
                + ")"
            )
        suffix = "  |  " + "  |  ".join(entries) if entries else ""
        return f"Position ({x:4d}, {y:4d}){suffix}"

    @staticmethod
    def _has_yuv(documents: Sequence[ImageDocument]) -> bool:
        return any(document.yuv_frame is not None for document in documents)

    @staticmethod
    def _mixed_yuv_family(documents: Sequence[ImageDocument]) -> bool:
        ready = [document for document in documents if document.source is not None]
        return bool(ready) and NativeYuvSemanticsController._has_yuv(ready) and any(
            document.yuv_frame is None for document in ready
        )

    def set_analysis_documents(
        self,
        documents: list[ImageDocument],
        bounds: RoiBounds | None,
        region_name: str | None = None,
    ) -> None:
        panel = self.window.comparison_analysis_panel
        if self._mixed_yuv_family(documents):
            panel.clear()
            self._hide_analysis_channels()
            panel._set_activity(
                "Mixed YUV/non-YUV Statistics and Histogram are disabled to preserve semantics.",
                busy=False,
            )
            return
        self._configure_analysis_channels(self._has_yuv(documents))
        self._analysis_set_documents_original(documents, bounds, region_name)

    def refresh_analysis(self) -> None:
        panel = self.window.comparison_analysis_panel
        documents = panel._documents
        if not documents or not all(document.yuv_frame is not None for document in documents):
            self._analysis_refresh_original()
            return

        bounds = panel._bounds
        requested_bins = panel._selected_histogram_bins()
        histogram_specs = [
            automatic_histogram_spec(document, requested_bins) for document in documents
        ]
        signature = panel._analysis_request_signature(documents, bounds, histogram_specs)
        panel._histogram_specs = histogram_specs
        if signature == panel._request_signature:
            if panel._worker is not None and not panel._worker.is_cancelled:
                return
            if signature == panel._completed_signature:
                return
        else:
            if panel._worker is not None:
                panel._worker.cancel()
            panel._request_signature = signature
            panel._completed_signature = ()
            panel._invalidate_histogram_presentation()

        active_bounds = [
            bounds or RoiBounds(0, 0, document.shape[1], document.shape[0])
            for document in documents
        ]
        cache_keys = [
            (
                "comparison-yuv",
                selected_bounds,
                bins,
                value_range,
                document.generation,
                document.channel_layout,
            )
            for document, selected_bounds, (bins, value_range) in zip(
                documents, active_bounds, histogram_specs, strict=True
            )
        ]
        cached_results = [
            document.statistics_cache.get(key)
            for document, key in zip(documents, cache_keys, strict=True)
        ]
        if all(isinstance(result, RoiAnalysisResult) for result in cached_results):
            typed = tuple(cached_results)
            panel.last_results = typed
            panel._completed_signature = signature
            panel._render(typed, histogram_specs)
            self._annotate_yuv_sample_counts(typed)
            return

        def calculate() -> tuple[RoiAnalysisResult, ...]:
            results: list[RoiAnalysisResult] = []
            for document, selected_bounds, spec, cached in zip(
                documents,
                active_bounds,
                histogram_specs,
                cached_results,
                strict=True,
            ):
                if isinstance(cached, RoiAnalysisResult):
                    results.append(cached)
                    continue
                frame = document.yuv_frame
                assert frame is not None
                bins, value_range = spec
                results.append(analyze_yuv_roi(frame, selected_bounds, bins, value_range))
            return tuple(results)

        panel._set_activity("Calculating native YUV...", busy=True)
        worker = TaskWorker(calculate)
        worker.signals.succeeded.connect(
            lambda _task_id, _document_id, _generation, result: self._on_yuv_analysis_result(
                signature,
                cache_keys,
                histogram_specs,
                result,
            )
        )
        worker.signals.failed.connect(panel._on_error)
        worker.signals.finished.connect(panel._on_finished)
        panel._worker = worker
        panel._pool.start(worker)

    def _on_yuv_analysis_result(
        self,
        signature: tuple[object, ...],
        cache_keys: Sequence[tuple[object, ...]],
        histogram_specs: list[tuple[int, tuple[float, float] | None]],
        result: object,
    ) -> None:
        panel = self.window.comparison_analysis_panel
        if signature != panel._request_signature or not isinstance(result, tuple):
            return
        if len(result) != len(panel._documents) or not all(
            isinstance(item, RoiAnalysisResult) for item in result
        ):
            return
        typed = tuple(result)
        for document, key, item in zip(panel._documents, cache_keys, typed, strict=True):
            document.statistics_cache[key] = item
        panel.last_results = typed
        panel._completed_signature = signature
        panel._render(typed, histogram_specs)
        self._annotate_yuv_sample_counts(typed)

    def _annotate_yuv_sample_counts(self, results: tuple[RoiAnalysisResult, ...]) -> None:
        panel = self.window.comparison_analysis_panel
        header = panel.image_summary.horizontalHeaderItem(3)
        if header is not None:
            header.setText("Luma pixels")
        row = 0
        for result in results:
            for name, count in zip(
                result.channel_names,
                result.channel_sample_counts,
                strict=True,
            ):
                item = panel.table.item(row, 1)
                if item is not None:
                    item.setToolTip(f"{name} native samples: {count:,}")
                row += 1

    def _configure_analysis_channels(self, yuv: bool) -> None:
        panel = self.window.comparison_analysis_panel
        if yuv:
            buttons = (
                self._analysis_buttons_original["R"],
                self._analysis_buttons_original["G"],
                self._analysis_buttons_original["B"],
            )
            panel.channel_buttons = dict(zip(("Y", "U", "V"), buttons, strict=True))
            for name, button in panel.channel_buttons.items():
                button.setText(name)
                button.setStyleSheet(channel_button_style(channel_color(name)))
                button.show()
            return
        panel.channel_buttons = dict(self._analysis_buttons_original)
        for name, button in panel.channel_buttons.items():
            button.setText(name)
            button.setStyleSheet(channel_button_style(channel_color(name)))
            button.show()
        header = panel.image_summary.horizontalHeaderItem(3)
        if header is not None:
            header.setText("Pixels")

    def _hide_analysis_channels(self) -> None:
        panel = self.window.comparison_analysis_panel
        panel.channel_buttons = dict(self._analysis_buttons_original)
        for button in self._analysis_buttons_original.values():
            button.hide()

    def set_line_documents(
        self,
        documents: list[ImageDocument],
        selection: LineSelection | None,
        *,
        reference_priority_ids: tuple[str, ...] = (),
    ) -> None:
        panel = self.window.line_profile_panel
        if self._mixed_yuv_family(documents):
            panel.clear()
            self._hide_line_channels()
            panel._set_status(
                "Mixed YUV/non-YUV Line Profile is disabled to preserve semantics."
            )
            return
        self._configure_line_channels(self._has_yuv(documents))
        self._line_set_documents_original(
            documents,
            selection,
            reference_priority_ids=reference_priority_ids,
        )

    def refresh_line_profile(self) -> None:
        panel = self.window.line_profile_panel
        documents = panel._documents
        selection = panel._selection
        if not documents or not all(document.yuv_frame is not None for document in documents):
            self._line_refresh_original()
            return
        if selection is None:
            panel.last_results = ()
            panel._clear_plot()
            return

        signature = (
            tuple(
                (
                    document.document_id,
                    document.generation,
                    document.channel_layout,
                    id(document.yuv_frame),
                )
                for document in documents
            ),
            selection,
        )
        panel._request_signature = signature
        if panel._worker is not None:
            panel._worker.cancel()
        cache_keys = [
            (
                "line-profile-yuv",
                selection,
                document.generation,
                document.channel_layout,
            )
            for document in documents
        ]
        cached_results = [
            document.statistics_cache.get(key)
            for document, key in zip(documents, cache_keys, strict=True)
        ]
        if all(isinstance(result, LineProfileResult) for result in cached_results):
            typed = tuple(cached_results)
            panel.last_results = typed
            panel._render(typed)
            return

        def calculate() -> tuple[LineProfileResult, ...]:
            results: list[LineProfileResult] = []
            for document, cached in zip(documents, cached_results, strict=True):
                if isinstance(cached, LineProfileResult):
                    results.append(cached)
                    continue
                frame = document.yuv_frame
                assert frame is not None
                results.append(selected_yuv_line_profile(frame, selection))
            return tuple(results)

        panel._set_status("Calculating native YUV line profile...")
        worker = TaskWorker(calculate)
        worker.signals.succeeded.connect(
            lambda _task_id, _document_id, _generation, result: panel._on_result(
                signature,
                cache_keys,
                result,
            )
        )
        worker.signals.failed.connect(panel._on_error)
        worker.signals.finished.connect(panel._on_finished)
        panel._worker = worker
        QThreadPool.globalInstance().start(worker)

    def _configure_line_channels(self, yuv: bool) -> None:
        panel = self.window.line_profile_panel
        model = panel.view_mode.model()
        separate_by_channel = model.item(2) if hasattr(model, "item") else None
        if yuv:
            buttons = (
                self._line_buttons_original["R"],
                self._line_buttons_original["G"],
                self._line_buttons_original["B"],
            )
            panel.channel_buttons = dict(zip(("Y", "U", "V"), buttons, strict=True))
            for name, button in panel.channel_buttons.items():
                button.setText(name)
                button.setStyleSheet(channel_button_style(channel_color(name)))
                button.show()
            for name in ("Gr", "Gb"):
                self._line_buttons_original[name].hide()
            # Existing Separate-by-channel grouping is RGB/Bayer-specific. WP-C1 keeps
            # Overlay/Separate-by-image with explicit Y/U/V controls rather than
            # presenting an empty or mislabeled grouping.
            if separate_by_channel is not None:
                separate_by_channel.setEnabled(False)
            if panel.view_mode.currentIndex() == 2:
                panel.view_mode.setCurrentIndex(0)
            return

        panel.channel_buttons = dict(self._line_buttons_original)
        for name, button in panel.channel_buttons.items():
            button.setText(name)
            button.setStyleSheet(channel_button_style(channel_color(name)))
            button.show()
        if separate_by_channel is not None:
            separate_by_channel.setEnabled(True)

    def _hide_line_channels(self) -> None:
        panel = self.window.line_profile_panel
        panel.channel_buttons = dict(self._line_buttons_original)
        for button in self._line_buttons_original.values():
            button.hide()

    def set_difference_documents(
        self,
        documents: list[ImageDocument],
        pair: tuple[str, str] | None,
        active_roi: RoiBounds | None = None,
    ) -> None:
        yuv_present = self._has_yuv(documents)
        supported = [document for document in documents if document.yuv_frame is None]
        safe_pair = pair
        if pair is not None and not set(pair).issubset(
            {document.document_id for document in supported}
        ):
            safe_pair = None
        self._difference_yuv_blocked = yuv_present and len(supported) < 2
        self._difference_set_documents_original(supported, safe_pair, active_roi)
        if self._difference_yuv_blocked:
            self._set_yuv_difference_status()

    def calculate_difference(
        self,
        _checked: bool = False,
        *,
        publish_result: bool = True,
    ) -> None:
        """Preserve the DifferencePanel slot/API signature while enforcing WP-C2."""

        if self._difference_yuv_blocked:
            self._set_yuv_difference_status()
            return
        self._difference_calculate_original(_checked, publish_result=publish_result)

    def _set_yuv_difference_status(self) -> None:
        self.window.difference_panel.status.setText(
            "Native YUV Difference is intentionally unsupported until WP-C2."
        )


def install_native_yuv_semantics(window: Any) -> NativeYuvSemanticsController:
    existing = window.__dict__.get("native_yuv_semantics_controller")
    if isinstance(existing, NativeYuvSemanticsController):
        return existing
    controller = NativeYuvSemanticsController(window)
    controller.install()
    return controller
