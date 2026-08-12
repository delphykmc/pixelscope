from __future__ import annotations

from types import MethodType
from typing import Any

from PySide6.QtCore import Qt, QTimer
from shiboken6 import isValid


def _install_restore_feedback_lifetime_guard(controller: Any) -> None:
    original_begin = controller._begin_restore_feedback

    def begin(self: Any) -> None:
        original_begin()
        dialog = self._restore_dialog
        if dialog is None or not isValid(dialog):
            self._restore_dialog = None
            return

        def destroyed(*_args: object) -> None:
            if self._restore_dialog is dialog:
                self._restore_dialog = None
                self._restore_difference_target = None

        dialog.destroyed.connect(destroyed)  # type: ignore[attr-defined]
        dialog.repaint()

    def finish(self: Any, *, delay_ms: int = 120) -> None:
        dialog = self._restore_dialog
        if dialog is None or not isValid(dialog):
            self._restore_dialog = None
            self._restore_difference_target = None
            return
        dialog.set_progress("Session restored", 1, 1, "Ready")
        dialog.repaint()

        def close_dialog() -> None:
            if self._restore_dialog is not dialog:
                return
            if isValid(dialog):
                dialog.finish()
            if self._restore_dialog is dialog:
                self._restore_dialog = None
            self._restore_difference_target = None

        QTimer.singleShot(delay_ms, close_dialog)

    def abort(self: Any) -> None:
        dialog = self._restore_dialog
        self._restore_dialog = None
        self._restore_difference_target = None
        if dialog is not None and isValid(dialog):
            dialog.finish()

    controller._begin_restore_feedback = MethodType(begin, controller)
    controller._finish_restore_feedback = MethodType(finish, controller)
    controller._abort_restore_feedback = MethodType(abort, controller)


def _invalidate_broken_difference_pair(window: Any) -> None:
    source_ids = window._difference_source_ids
    if source_ids is None:
        return
    selected_ids = {
        str(item.data(0, Qt.ItemDataRole.UserRole))
        for item in window.document_list.document_items()
        if item.isSelected()
    }
    if set(source_ids).issubset(selected_ids):
        return

    difference = window._difference_document
    difference_id = difference.document_id if difference is not None else None
    panel = window.difference_panel
    if panel._worker is not None:
        panel._cancel_worker()
    panel._display_timer.stop()

    window._difference_document = None
    window._difference_source_ids = None
    window._six_image_diff_restore_state = None
    if difference_id is not None:
        window._multi_display_order = [
            document_id
            for document_id in window._multi_display_order
            if document_id != difference_id
        ]
        if window._focus_document_id == difference_id:
            window._focus_document_id = None

    diff_action = getattr(window, "diff_action", None)
    if diff_action is not None:
        diff_action.blockSignals(True)
        diff_action.setChecked(False)
        diff_action.blockSignals(False)


def _install_difference_selection_guard(window: Any) -> None:
    original = window._selection_changed
    try:
        window.document_list.itemSelectionChanged.disconnect(original)
    except (RuntimeError, TypeError):
        return

    def guarded_selection_changed() -> None:
        _invalidate_broken_difference_pair(window)
        original()

    window._session_guarded_selection_changed = guarded_selection_changed
    window.document_list.itemSelectionChanged.connect(guarded_selection_changed)


def install_session_interaction_guard(window: Any) -> None:
    """Harden Session feedback lifetime and Diff-bound Files selection changes."""

    controller = getattr(window, "session_controller", None)
    if controller is None:
        raise RuntimeError("Session controller must be installed before its interaction guard")
    if getattr(window, "_session_interaction_guard_installed", False):
        return
    _install_restore_feedback_lifetime_guard(controller)
    _install_difference_selection_guard(window)
    window._session_interaction_guard_installed = True
