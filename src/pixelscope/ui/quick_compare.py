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

from pixelscope.io.path_discovery import discover_image_inputs
from pixelscope.ui.design_tokens import TOKENS
from pixelscope.ui.lifecycle_hooks import OwnerCallback


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


def install_quick_compare_workflow(window: Any) -> QuickCompareController:
    existing = getattr(window, "quick_compare_controller", None)
    if isinstance(existing, QuickCompareController):
        return existing
    controller = QuickCompareController(window)
    window.quick_compare_controller = controller
    return controller
