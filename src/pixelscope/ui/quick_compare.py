from __future__ import annotations

import weakref
from pathlib import Path
from typing import Any, cast

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtGui import (
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QWidget,
)

from pixelscope.core.comparison_presets import (
    ComparisonPair,
    ComparisonPlan,
    ComparisonPreset,
    plan_comparison,
)
from pixelscope.io.path_discovery import discover_image_inputs
from pixelscope.ui.design_tokens import TOKENS
from pixelscope.ui.lifecycle_hooks import OwnerCallback
from pixelscope.ui.presentation_controls import install_comparison_preset_controls


class QuickCompareController(QObject):
    """Issue #77 WP-C interaction controller without parallel selection state."""

    _THREE_VIEW_VARIANTS = ("Equal", "Focus")

    def __init__(self, window: Any) -> None:
        super().__init__(window)
        self._window_ref = weakref.ref(window)
        self._view_ref = weakref.ref(window.multi_compare_view)
        self._three_view_context: tuple[frozenset[str], bool] | None = None
        self._three_view_override: str | None = None
        self._pending_difference_pair: tuple[str, str] | None = None
        self._difference_retry_count = 0
        self._protected_difference_pair: tuple[str, str] | None = None
        self._sequential_drop_anchor_id: str | None = None
        self._app: QApplication | None = None

        self._original_prepare = OwnerCallback(
            window.multi_compare_view._prepare_viewers_for_documents
        )
        self._original_fixed_geometry = OwnerCallback(window.multi_compare_view._fixed_geometry)
        self._original_render_selection = OwnerCallback(window._render_selection)

        self._difference_retry_timer = QTimer(self)
        self._difference_retry_timer.setInterval(50)
        self._difference_retry_timer.timeout.connect(  # type: ignore[attr-defined]
            self._try_pending_difference
        )
        window.difference_panel.map_cached.connect(self._quick_difference_cached)

        self._build_three_view_controls()
        self._install_three_view_geometry()
        self._install_render_hook()
        self._install_input_filter()
        self.comparison_presets = ComparisonPresetController(window, self)

    @property
    def window(self) -> Any:
        window = self._window_ref()
        if window is None:
            raise RuntimeError("Quick Compare window was destroyed")
        return window

    @property
    def view(self) -> Any:
        view = self._view_ref()
        if view is None:
            raise RuntimeError("Quick Compare view was destroyed")
        return view

    def _build_three_view_controls(self) -> None:
        group = QWidget(self.window.presentation_controls)
        group.setObjectName("threeViewVariantControl")
        layout = QHBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(TOKENS.spacing_xs)
        label = QLabel("3 View", group)
        equal = QToolButton(group)
        focus = QToolButton(group)
        equal.setText("Equal")
        focus.setText("Focus")
        for button in (equal, focus):
            button.setCheckable(True)
            button.setAutoRaise(True)
        buttons = QButtonGroup(group)
        buttons.setExclusive(True)
        buttons.addButton(equal)
        buttons.addButton(focus)
        equal.clicked.connect(  # type: ignore[attr-defined]
            lambda: self.set_three_view_variant("Equal")
        )
        focus.clicked.connect(  # type: ignore[attr-defined]
            lambda: self.set_three_view_variant("Focus")
        )
        layout.addWidget(label)
        layout.addWidget(equal)
        layout.addWidget(focus)
        group.hide()

        command_layout = self.window.presentation_controls_layout
        stretch_index = command_layout.count()
        for index in range(command_layout.count()):
            item = command_layout.itemAt(index)
            if item is not None and item.spacerItem() is not None:
                stretch_index = index
                break
        command_layout.insertWidget(stretch_index, group)
        metric_owner = getattr(self.window, "_command_row_metric_refresh", None)
        refresh = getattr(metric_owner, "refresh", None)
        if callable(refresh):
            refresh()

        self.three_view_group = group
        self.three_view_label = label
        self.three_view_equal = equal
        self.three_view_focus = focus
        self._sync_three_view_buttons("Equal")

    def _install_three_view_geometry(self) -> None:
        self.view._prepare_viewers_for_documents = OwnerCallback(
            self._prepare_viewers_for_documents
        )
        self.view._fixed_geometry = OwnerCallback(self._fixed_geometry)

    def _prepare_viewers_for_documents(self, documents: list[Any]) -> None:
        self._original_prepare(documents)
        target = documents[: self.view.capacity]
        context = (
            frozenset(str(document.document_id) for document in target),
            any(document.channel_layout == "DIFFERENCE" for document in target),
        )
        if context != self._three_view_context:
            self._three_view_context = context
            self._three_view_override = None
        self._sync_three_view_buttons(self._effective_three_view_variant())

    def _fixed_geometry(self, count: int) -> Any:
        if count == 3 and self._effective_three_view_variant() == "Equal":
            return (
                ((0, 0, 1, 1), (0, 1, 1, 1), (0, 2, 1, 1)),
                (1,),
                (1, 1, 1),
            )
        return self._original_fixed_geometry(count)

    def _install_render_hook(self) -> None:
        self.window._render_selection = OwnerCallback(self._render_selection)

    def _render_selection(self, preserve_view: bool = False) -> None:
        self._original_render_selection(preserve_view)
        self._update_three_view_controls()
        presets = getattr(self, "comparison_presets", None)
        if isinstance(presets, ComparisonPresetController):
            presets.on_workspace_rendered()

    def _install_input_filter(self) -> None:
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            raise RuntimeError("Quick Compare requires QApplication")
        app.installEventFilter(self)
        self._app = app
        surfaces = [
            self.window.central_stack,
            self.window.viewer,
            self.window.multi_compare_view,
            self.window.viewer._graphics,
            self.window.viewer._graphics.viewport(),
        ]
        surfaces.extend(viewer._graphics for viewer in self.window.multi_compare_view.viewers)
        surfaces.extend(
            viewer._graphics.viewport() for viewer in self.window.multi_compare_view.viewers
        )
        for surface in surfaces:
            if isinstance(surface, QWidget):
                surface.setAcceptDrops(True)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        event_type = event.type()
        if event_type == QEvent.Type.DragLeave and self._is_image_surface(watched):
            cast(QDragLeaveEvent, event).accept()
            return True
        if event_type in (
            QEvent.Type.DragEnter,
            QEvent.Type.DragMove,
            QEvent.Type.Drop,
        ) and self._is_image_surface(watched):
            drop_event = cast(QDragEnterEvent | QDragMoveEvent | QDropEvent, event)
            paths = self._local_paths(drop_event)
            if paths:
                if event_type in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
                    drop_event.acceptProposedAction()
                    return True
                if self.handle_image_drop(paths):
                    drop_event.acceptProposedAction()
                    return True

        if watched is self.window and event_type == QEvent.Type.Close:
            self._clear_pending_difference(clear_protected=True)
            self._uninstall_input_filter()
            self.comparison_presets.shutdown()

        # QApplication can route internal Qt objects (for example QWidgetItem) through
        # an application-level filter. Calling QObject.eventFilter() with those Python
        # wrappers raises in PySide6; the default QObject implementation is a no-op.
        return False

    def _uninstall_input_filter(self) -> None:
        app = getattr(self, "_app", None)
        if isinstance(app, QApplication):
            app.removeEventFilter(self)
        self._app = None

    def _is_image_surface(self, watched: QObject) -> bool:
        if not isinstance(watched, QWidget):
            return False
        central = self.window.central_stack
        return watched is central or central.isAncestorOf(watched)

    @staticmethod
    def _local_paths(event: QDragEnterEvent | QDragMoveEvent | QDropEvent) -> list[Path]:
        mime = event.mimeData()
        if not mime.hasUrls():
            return []
        return [Path(url.toLocalFile()) for url in mime.urls() if url.isLocalFile()]

    def handle_image_drop(self, paths: list[Path]) -> bool:
        if not paths:
            return False

        registration = getattr(self.window, "large_folder_registration_controller", None)
        enqueue = getattr(registration, "enqueue", None)
        if callable(enqueue):
            # Classification can block on SMB. Discovery already distinguishes
            # direct files from registration-only folders on its worker thread.
            enqueue(paths, direct_completion=self._apply_registered_drop)
            return True

        # Standalone MainWindow/tests retain a synchronous fallback, but production
        # image-surface D&D shares RegistrationController with the Files view.
        if any(path.is_dir() for path in paths):
            self.window._handle_dropped_paths(paths)
            return True
        files = [path for path in paths if path.is_file()]
        if not files:
            return False
        document_ids = self.window._register_inputs(
            discover_image_inputs(files),
            resolve_raw_profiles=True,
        )
        if not document_ids:
            self.window.statusBar().showMessage("Quick Compare: no supported images", 4000)
            return True
        self._apply_registered_drop(document_ids)
        return True

    def _apply_registered_drop(self, document_ids: list[str]) -> None:
        previous_ids = [document.document_id for document in self.window.selected_documents]
        previous_set = set(previous_ids)
        unique_dropped: list[str] = []
        seen: set[str] = set()
        for document_id in document_ids:
            if document_id not in seen:
                unique_dropped.append(document_id)
                seen.add(document_id)
        additions = [
            document_id for document_id in unique_dropped if document_id not in previous_set
        ]
        merged = [*previous_ids, *additions]
        pair = self._quick_difference_pair(previous_ids, unique_dropped, merged)
        if additions:
            self.window._select_document_ids(
                merged,
                preserve_view=bool(previous_ids),
                reveal_document_id=additions[-1] if previous_ids else None,
            )
        reloads = self.window._refresh_reopened_selected_documents(
            [document_id for document_id in unique_dropped if document_id in previous_set]
        )

        added = len(additions)
        if pair is not None:
            self.window.statusBar().showMessage(
                "Quick Compare: displaying sources · calculating Difference in background…",
                4000,
            )
        elif added:
            self.window.statusBar().showMessage(
                f"Quick Compare: added {added} image(s) · {len(merged)} selected",
                4000,
            )
        elif reloads:
            self.window.statusBar().showMessage(
                f"Quick Compare: reloading {len(reloads)} image(s)",
                3500,
            )
        else:
            self.window.statusBar().showMessage(
                "Quick Compare: source ready · drop another image to compare",
                3500,
            )

        if pair is not None:
            self._schedule_difference(pair)

    def consider_registered_files_drop(
        self, previous_ids: list[str], dropped_ids: list[str]
    ) -> None:
        """Apply the same passive Quick Compare pairing to explicit Files drops.

        RegistrationController remains the single registration authority.
        Ordinary tree selection, folder discovery and reopens do not trigger
        unsolicited Difference calculations.
        """

        selected_ids = [document.document_id for document in self.window.selected_documents]
        if not any(document_id not in previous_ids for document_id in dropped_ids):
            return
        unique_dropped = list(dict.fromkeys(dropped_ids))
        pair = self._quick_difference_pair(previous_ids, unique_dropped, selected_ids)
        if pair is not None:
            self._schedule_difference(pair)

    def _quick_difference_pair(
        self,
        previous_ids: list[str],
        dropped_ids: list[str],
        merged_ids: list[str],
    ) -> tuple[str, str] | None:
        existing = self.window._difference_source_ids
        if existing is not None and set(existing).issubset(set(merged_ids)):
            self._sequential_drop_anchor_id = None
            return None
        protected = self._protected_difference_pair
        if protected is not None:
            still_selected = set(protected).issubset(set(merged_ids))
            in_flight = (
                self._pending_difference_pair == protected
                or self.window.difference_panel._worker is not None
            )
            if still_selected and in_flight:
                self._sequential_drop_anchor_id = None
                return None
            self._protected_difference_pair = None
        if len(dropped_ids) == 2 and dropped_ids[0] != dropped_ids[1]:
            self._sequential_drop_anchor_id = None
            return dropped_ids[0], dropped_ids[1]
        if len(dropped_ids) != 1:
            self._sequential_drop_anchor_id = None
            return None

        dropped_id = dropped_ids[0]
        anchor_id = self._sequential_drop_anchor_id
        if (
            anchor_id is not None
            and anchor_id != dropped_id
            and anchor_id in merged_ids
            and dropped_id in merged_ids
        ):
            self._sequential_drop_anchor_id = None
            return anchor_id, dropped_id
        if len(previous_ids) == 1 and len(merged_ids) == 2 and dropped_id != previous_ids[0]:
            self._sequential_drop_anchor_id = None
            return previous_ids[0], dropped_id
        self._sequential_drop_anchor_id = dropped_id
        return None

    def _schedule_difference(self, pair: tuple[str, str]) -> None:
        self._pending_difference_pair = pair
        self._protected_difference_pair = pair
        self._difference_retry_count = 0
        # Yield to Qt first: source image updates/paint have priority over
        # starting Difference computation on the analysis worker pool.
        self._difference_retry_timer.start()

    def _try_pending_difference(self) -> None:
        pair = self._pending_difference_pair
        if pair is None:
            self._difference_retry_timer.stop()
            return
        selected_ids = {document.document_id for document in self.window.selected_documents}
        if not set(pair).issubset(selected_ids):
            self._clear_pending_difference(clear_protected=True)
            return
        existing = self.window._difference_source_ids
        if existing is not None and existing != pair and set(existing).issubset(selected_ids):
            self._clear_pending_difference(clear_protected=True)
            return

        comparison = self.window.current_comparison_documents()
        comparison_ids = {document.document_id for document in comparison}
        if not set(pair).issubset(comparison_ids):
            self.window.statusBar().showMessage(
                "Quick Compare: Difference requires both dropped sources on the current page",
                4500,
            )
            self._clear_pending_difference(clear_protected=True)
            return

        pair_documents = [self.window.documents.get(document_id) for document_id in pair]
        if any(document is None for document in pair_documents):
            self._clear_pending_difference(clear_protected=True)
            return
        if any(document.preview is None for document in pair_documents):
            self._difference_retry_count += 1
            if self._difference_retry_count >= 200:
                self.window.statusBar().showMessage(
                    "Quick Compare: Difference unavailable because a source did not finish loading",
                    5000,
                )
                self._clear_pending_difference(clear_protected=True)
            else:
                self._difference_retry_timer.start()
            return

        panel = self.window.difference_panel
        panel.set_documents(comparison, pair, self.window._shared_roi)
        selected_pair = panel.selected_documents()
        if (
            selected_pair is not None
            and tuple(document.document_id for document in selected_pair) == pair
            and panel.calculate.isEnabled()
        ):
            self._clear_pending_difference(clear_protected=False)
            if panel.has_cached_map():
                self._protected_difference_pair = None
                self.window._update_action_states()
            else:
                panel.calculate_difference(publish_result=False)
            return

        message = panel.status.text().strip() or "Difference is unavailable for the dropped pair"
        self.window.statusBar().showMessage(f"Quick Compare: {message}", 5000)
        self._clear_pending_difference(clear_protected=True)

    def _clear_pending_difference(self, *, clear_protected: bool) -> None:
        self._pending_difference_pair = None
        self._difference_retry_count = 0
        self._difference_retry_timer.stop()
        if clear_protected:
            self._protected_difference_pair = None

    def _quick_difference_cached(self, request_pair: object) -> None:
        if not isinstance(request_pair, tuple) or len(request_pair) != 2:
            return
        if request_pair == self._protected_difference_pair:
            self._protected_difference_pair = None
            self.window.statusBar().showMessage(
                "Difference ready in background · select Diff to display", 4000
            )

    def _effective_three_view_variant(self) -> str:
        if self._three_view_override in self._THREE_VIEW_VARIANTS:
            return self._three_view_override
        if self._three_view_context is not None and self._three_view_context[1]:
            return "Focus"
        return "Equal"

    def set_three_view_variant(self, variant: str) -> None:
        if variant not in self._THREE_VIEW_VARIANTS:
            raise ValueError(f"unsupported 3-view variant: {variant}")
        if self.view._document_count != 3:
            return
        state = self.view.capture_view_state()
        self._three_view_override = variant
        self._sync_three_view_buttons(variant)
        self.view._arranged_count = -1
        self.view._arrange_viewers(3)
        self.view._layout.activate()
        self.view.restore_view_state(state)

    def _sync_three_view_buttons(self, variant: str) -> None:
        for button, name in (
            (self.three_view_equal, "Equal"),
            (self.three_view_focus, "Focus"),
        ):
            button.blockSignals(True)
            button.setChecked(variant == name)
            button.blockSignals(False)

    def _update_three_view_controls(self) -> None:
        visible = (
            self.window.central_stack.currentWidget() is self.window.multi_compare_view
            and self.view._document_count == 3
        )
        self.three_view_group.setVisible(visible)
        self._sync_three_view_buttons(self._effective_three_view_variant())



class ComparisonPresetController(QObject):
    """W05 runtime-only presentation overlay; Files/Page and Analysis stay canonical.

    Installed through the existing Quick Compare composition entrypoint; no
    MainWindow, Session, registration controller, or W04 viewer hook is replaced.
    """

    def __init__(self, window: Any, quick_compare: QuickCompareController) -> None:
        super().__init__(window)
        self._window_ref = weakref.ref(window)
        self._quick_ref = weakref.ref(quick_compare)
        self._closed = False
        self._syncing = False
        self._preset = ComparisonPreset.WORKSPACE
        self._pair: ComparisonPair | None = None
        self._page_binding: tuple[tuple[str, int, int], ...] | None = None
        self._original_view_state: Any = None
        (
            self.group,
            self.preset_combo,
            self.reference_combo,
            self.target_combo,
            self.status_label,
        ) = install_comparison_preset_controls(window)
        self.preset_combo.currentIndexChanged.connect(self._choose_preset)
        self.reference_combo.currentIndexChanged.connect(self._choose_reference)
        self.target_combo.currentIndexChanged.connect(self._choose_target)
        window.diff_action.toggled.connect(self._external_diff_toggled)
        self.on_workspace_rendered()

    @property
    def window(self) -> Any:
        window = self._window_ref()
        if window is None:
            raise RuntimeError("Comparison preset window was destroyed")
        return window

    @property
    def preset(self) -> ComparisonPreset:
        return self._preset

    @property
    def pair(self) -> ComparisonPair | None:
        return self._pair

    def _page(self) -> list[Any]:
        return self.window.current_comparison_documents()

    def _binding(self) -> tuple[tuple[str, int, int], ...]:
        return tuple(
            (document.document_id, id(document), document.generation)
            for document in self._page()
        )

    def _sync_roles(self) -> None:
        """Aliases change; data roles remain exact ImageDocument IDs."""
        page = self._page()
        ids = [document.document_id for document in page]
        self._syncing = True
        try:
            if self._pair is None or not self._pair.valid_on(ids):
                self._pair = ComparisonPair(ids[0], ids[1]) if len(ids) >= 2 else None
            for combo, selected in (
                (self.reference_combo, self._pair.reference_id if self._pair else None),
                (self.target_combo, self._pair.target_id if self._pair else None),
            ):
                combo.blockSignals(True)
                combo.clear()
                for index, document in enumerate(page):
                    combo.addItem(f"{index + 1}: {document.display_name}", document.document_id)
                combo.setCurrentIndex(combo.findData(selected))
                combo.setEnabled(len(page) >= 2)
                combo.blockSignals(False)
            self.preset_combo.blockSignals(True)
            self.preset_combo.setCurrentIndex(self.preset_combo.findData(self._preset.value))
            self.preset_combo.blockSignals(False)
        finally:
            self._syncing = False

    def _state(self, preset: ComparisonPreset) -> ComparisonPlan:
        page = self._page()
        ids = [document.document_id for document in page]
        panel = self.window.difference_panel
        selected = panel.selected_documents()
        selected_ids = (
            tuple(document.document_id for document in selected) if selected else ()
        )
        matching = self._pair is not None and selected_ids == self._pair.source_ids
        cached = bool(matching and panel.has_cached_map())
        pending = bool(
            matching
            and panel._worker is not None
            and panel._worker_key is not None
            and panel._worker_key[0] == panel._cache_key()
        )
        old_pair = getattr(self.window, "_difference_source_ids", None)
        stale = bool(matching and not cached and old_pair == selected_ids)
        return plan_comparison(
            ids, preset, self._pair, cached_valid=cached,
            pending=pending, stale=stale,
        )

    def _status(self, plan: ComparisonPlan) -> None:
        message = plan.explanation
        if not message and plan.show_difference:
            message = "Cached valid Difference"
        elif not message and plan.pair is not None:
            message = "Reference A / Target B (not Primary or Active)"
        self.status_label.setText(
            "Cached" if plan.show_difference else plan.difference_state.replace("-", " ").title()
            if plan.preset in (ComparisonPreset.AB_DIFF, ComparisonPreset.DIFF_FOCUS)
            else ""
        )
        self.status_label.setToolTip(message)
        if message and (
            not plan.available
            or plan.difference_state in ("pending", "stale", "not-calculated")
        ):
            self.window.statusBar().showMessage(message, 4500)

    def _project(self) -> None:
        if self._closed or self._preset is ComparisonPreset.WORKSPACE:
            return
        page = self._page()
        plan = self._state(self._preset)
        self._status(plan)
        if not plan.available:
            return
        by_id = {document.document_id: document for document in page}
        # An unavailable Diff Focus must evict the old derived tile immediately;
        # presenting its current A/B originals is a safe, explicit fallback.
        presentation_ids = (
            plan.pair.source_ids
            if self._preset is ComparisonPreset.DIFF_FOCUS and not plan.show_difference
            and plan.pair is not None
            else plan.source_ids
        )
        visible = [by_id[source_id] for source_id in presentation_ids]
        if plan.show_difference:
            panel = self.window.difference_panel
            cached = panel.cached_display_for_current()
            if cached is None or self._pair is None:
                self.status_label.setText("Not calculated")
                return
            mapping = panel.mapping_snapshot_for_payload(cached[1], cached[2])
            self.window._store_difference_document(
                *cached, mapping, switch_to_result=False,
            )
            difference = getattr(self.window, "_difference_document", None)
            if (
                difference is None
                or self.window._difference_source_ids != self._pair.source_ids
            ):
                self.status_label.setText("Stale")
                return
            visible = [difference] if self._preset is ComparisonPreset.DIFF_FOCUS else [
                *visible, difference
            ]
        view = self.window.multi_compare_view
        saved = view.capture_view_state() if view.occupied_viewers else self._original_view_state
        capacity = 1 if len(visible) == 1 else 2 if len(visible) == 2 else 4
        kind = (
            "Single" if capacity == 1 else "Side by Side" if capacity == 2
            else "Grid 2x2" if len(visible) == 4 else "Focus + 2"
        )
        # Source-only Primary remains MainWindow-owned; W05 merely presents tiles.
        primary_id = getattr(self.window, "_focus_document_id", None)
        focus_id = primary_id if primary_id in plan.source_ids else (
            plan.source_ids[0] if plan.source_ids else visible[0].document_id
        )
        view.set_capacity(capacity)
        view.set_layout_kind(kind, focus_id)
        slot_by_id = {document.document_id: index + 1 for index, document in enumerate(page)}
        view.set_documents(
            visible, 0, len(page), self.window._shared_roi, self.window._shared_line,
            preserve_view=True, slot_by_id=slot_by_id,
        )
        self.window.central_stack.setCurrentWidget(view)
        if saved is not None and view.sync_enabled:
            view.restore_view_state(saved)
        elif not view.sync_enabled:
            # W04's source-verified per-source engine is NOT usable without W09
            # bindings. Do not invent UUIDs or mark unverified restore as applied.
            self.status_label.setToolTip(
                "Sync Off: only currently retained viewer transforms are preserved; "
                "hidden-source physical zoom restore requires W04 owner handoff."
            )
        quick = self._quick_ref()
        if quick is not None:
            quick._update_three_view_controls()
        self.window._update_action_states()

    def _activate(self, preset: ComparisonPreset) -> None:
        if self._closed:
            return
        if preset is ComparisonPreset.WORKSPACE:
            self._preset = preset
            self._page_binding = None
            self.window._render_selection(preserve_view=True)
            return
        # MultiCompareView's current live restore shares an anchor range even
        # when Sync is Off; W04's verified per-source adapter needs W09 bindings.
        # Reject instead of destroying independent physical centers/zoom.
        if not self.window.multi_compare_view.sync_enabled:
            self.window.statusBar().showMessage(
                "Comparison preset unavailable with Sync Off: per-source restore "
                "requires the W04 runtime binding handoff", 5500,
            )
            return
        plan = self._state(preset)
        if not plan.available:
            self._status(plan)
            self._sync_roles()
            return
        if self._preset is ComparisonPreset.WORKSPACE:
            view = self.window.multi_compare_view
            self._original_view_state = (
                view.capture_view_state() if view.occupied_viewers else None
            )
        if self.window.diff_action.isChecked():
            self.window.diff_action.setChecked(False)
        if self._pair is not None:
            lifecycle = self.window.difference_curation_lifecycle
            if not lifecycle.select_preset_pair(self._pair.source_ids):
                self.window.statusBar().showMessage(
                    "Pair is not loaded on the current Comparison Page", 4500
                )
                return
        self.window.multi_compare_view.cancel_review_restore()
        self._preset = preset
        self._page_binding = self._binding()
        self._project()

    def set_preset(self, preset: ComparisonPreset) -> None:
        """Typed explicit entrypoint; also used by the command-row combobox."""
        if not isinstance(preset, ComparisonPreset):
            raise ValueError("unknown Comparison Preset")
        self._activate(preset)
        self._sync_roles()

    def _choose_preset(self, _index: int) -> None:
        if self._syncing:
            return
        value = self.preset_combo.currentData()
        try:
            preset = ComparisonPreset(str(value))
        except ValueError:
            return
        self.set_preset(preset)

    def _change_pair(
        self, *, reference_id: str | None = None, target_id: str | None = None
    ) -> None:
        if self._closed or self._syncing or self._pair is None:
            return
        if (
            self._preset is not ComparisonPreset.WORKSPACE
            and not self.window.multi_compare_view.sync_enabled
        ):
            self.window.statusBar().showMessage(
                "Pair change blocked with Sync Off to preserve independent view state", 4500,
            )
            self._sync_roles()
            return
        pair = ComparisonPair(
            reference_id or self._pair.reference_id,
            target_id or self._pair.target_id,
        )
        if not pair.valid_on([doc.document_id for doc in self._page()]):
            self.window.statusBar().showMessage(
                "Reference and Target must be distinct page sources", 4000
            )
            self._sync_roles()
            return
        if self.window.diff_action.isChecked():
            self.window.diff_action.setChecked(False)
        lifecycle = self.window.difference_curation_lifecycle
        if not lifecycle.select_preset_pair(pair.source_ids):
            self.window.statusBar().showMessage("Pair is not loaded", 4000)
            self._sync_roles()
            return
        self._pair = pair
        self._sync_roles()
        if self._preset is not ComparisonPreset.WORKSPACE:
            self._project()

    def _choose_reference(self, _index: int) -> None:
        reference_id = self.reference_combo.currentData()
        if reference_id is not None:
            self._change_pair(reference_id=str(reference_id))

    def _choose_target(self, _index: int) -> None:
        target_id = self.target_combo.currentData()
        if target_id is not None:
            self._change_pair(target_id=str(target_id))

    def _external_diff_toggled(self, checked: bool) -> None:
        # The established toolbar/explicit Calculate contract outranks W05.
        if not self._closed and checked and self._preset is not ComparisonPreset.WORKSPACE:
            self._preset = ComparisonPreset.WORKSPACE
            self._page_binding = None
            self._sync_roles()

    def on_workspace_rendered(self) -> None:
        if self._closed:
            return
        if (
            self._preset is not ComparisonPreset.WORKSPACE
            and self._page_binding != self._binding()
        ):
            self._preset = ComparisonPreset.WORKSPACE
            self._page_binding = None
            self.window.statusBar().showMessage(
                "Comparison preset dismissed: page source or generation changed", 4500
            )
        if (
            self._preset is not ComparisonPreset.WORKSPACE
            and not self.window.multi_compare_view.sync_enabled
        ):
            self._preset = ComparisonPreset.WORKSPACE
            self._page_binding = None
            self.window.statusBar().showMessage(
                "Temporary preset dismissed: Sync Off cannot restore hidden-source view state",
                4500,
            )
        self._sync_roles()
        if (
            self._preset is not ComparisonPreset.WORKSPACE
            and not self.window.diff_action.isChecked()
        ):
            self._project()

    def shutdown(self) -> None:
        if self._closed:
            return
        self._closed = True
        # Children are owned by the MainWindow; no background work belongs to W05.
        self._page_binding = None
        self._original_view_state = None



def install_quick_compare_workflow(window: Any) -> QuickCompareController:
    existing = getattr(window, "quick_compare_controller", None)
    if isinstance(existing, QuickCompareController):
        return existing
    controller = QuickCompareController(window)
    window.quick_compare_controller = controller
    return controller
