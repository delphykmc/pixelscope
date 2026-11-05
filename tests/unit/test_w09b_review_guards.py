"""W09b reviewer blockers: capture fencing and canonical restore transaction."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from pixelscope.core.review_record import ReviewValidationError
from pixelscope.ui.review_capture_adapter import (
    AttestedFinding,
    CaptureGuiFence,
    StagedFinding,
    assert_same_capture_context,
)
from pixelscope.ui.review_main_window_adapter import MainWindowReviewRestoreAuthority
from pixelscope.ui.review_restore_controller import RestorePlan
from pixelscope.ui.review_window_integration import NamedReviewCoordinator


class Combo:
    def __init__(self, items):
        self.items = list(items)
        self.index = 0

    def findData(self, value):
        return next((i for i, (_, data) in enumerate(self.items) if data == value), -1)

    def findText(self, value):
        return next((i for i, (text, _) in enumerate(self.items) if text == value), -1)

    def setCurrentIndex(self, index):
        self.index = index

    def setCurrentText(self, value):
        self.index = self.findText(value)

    def currentText(self):
        return self.items[self.index][0]

    def currentData(self):
        return self.items[self.index][1]

    def blockSignals(self, _):
        return False


class Spin:
    def __init__(self, low=0, high=1000, value=1):
        self.low, self.high, self._value = low, high, value

    def minimum(self):
        return self.low

    def maximum(self):
        return self.high

    def value(self):
        return self._value

    def setValue(self, value):
        self._value = value

    def blockSignals(self, _):
        return False


class Difference:
    def __init__(self, documents):
        self.documents = {d.document_id: d for d in documents}
        ids = tuple(self.documents)
        self.a_selector = Combo([(item, item) for item in ids])
        self.b_selector = Combo([(item, item) for item in ids])
        self.b_selector.setCurrentIndex(1)
        self.channel = Combo([("Gray", "Gray"), ("All", "All")])
        self.mode = Combo([("Absolute", "Absolute"), ("Mask", "Mask")])
        self.region = Combo([("Full image", "Full image"), ("Active ROI", "Active ROI")])
        self.gain = Spin(1, 1000)
        self.threshold = Spin(0, 1000)
        self._display_timer = NS(stop=lambda: None)
        self._cancel_worker = lambda: None
        self._cancel_preview_worker = lambda: None
        self._update_channels = lambda: None
        self._clear_metrics = lambda: None
        self.calculate_difference = MagicMock()
        self.last_result = None

    def selected_documents(self):
        a = self.documents.get(self.a_selector.currentData())
        b = self.documents.get(self.b_selector.currentData())
        return (a, b) if a is not None and b is not None and a is not b else None


class Window:
    def __init__(self, paths, keys):
        self._closing = False
        self._channel_split_active = False
        self._layout_mode = "Multi View"
        self._raw_profiles = {}
        self._difference_document = None
        self._difference_source_ids = None
        self._shared_roi = None
        self._shared_line = None
        self._document_id_by_path = {}
        self.documents = {}
        self.mutations = 0
        self.sources = []
        for idx, path in enumerate(paths):
            identity = self._path_key(path)
            document_id = "doc-" + str(idx)
            self._document_id_by_path[identity] = document_id
            doc = NS(
                document_id=document_id,
                generation=0,
                source=object(),
                loading_state="ready",
                reference_shape=(4, 5),
            )
            self.documents[document_id] = doc
            self.sources.append(doc)
        self.difference_panel = Difference(self.sources)
        self.multi_compare_view = NS(
            begin_review_restore=MagicMock(),
            cancel_review_restore=MagicMock(),
        )
        self.comparison_analysis_panel = NS(bind_review_source_keys=MagicMock())
        self.diff_action = NS(blockSignals=lambda _: False, setChecked=lambda _: None)
        self.sync_action = NS(blockSignals=lambda _: False, setChecked=MagicMock())
        self._update_action_states = MagicMock()
        self._profile = NS(copy=lambda deep: NS(copy=lambda deep: None))
        self._force_pending = False

    def _path_key(self, path):
        return str(Path(path).resolve()).casefold()

    def _register_input(self, inp, *, resolve_raw_profile=False):
        self.mutations += 1
        return self._document_id_by_path[self._path_key(inp.path)]

    def _mark_document_for_reload(self, document_id, profile):
        if self._force_pending:
            doc = self.documents[document_id]
            doc.source = None
            doc.loading_state = "pending"

    def _select_document_ids(self, ids):
        self.mutations += 1
        self._chosen_ids = ids

    def _set_focus_document(self, document_id):
        self.mutations += 1

    def current_comparison_documents(self):
        return self.sources

    def clear_roi(self):
        self._shared_roi = None

    def _apply_shared_roi(self, bounds, *, allow_channel_split):
        self._shared_roi = bounds
        return True

    def _shared_line_changed(self, line):
        self._shared_line = line


def make_plan(paths):
    keys = tuple(str(uuid4()) for _ in paths)
    source_shape = NS(reference_shape=(4, 5), profile_signature="s")
    review = NS(
        document_id=str(uuid4()),
        sources=tuple(NS(source_key=k, native_signature=source_shape) for k in keys),
    )
    view = NS(
        layout_kind="Side by Side",
        presentation_mode="originals",
        primary_source_key=keys[0],
        sync_enabled=False,
        source_shapes_ref={key: (4, 5) for key in keys},
    )
    finding = NS(
        source_keys=keys,
        view_state=view,
        channel="All",
        difference_intent=None,
        roi_ref=None,
        line_ref=None,
        display_gain=1.0,
    )
    candidates = tuple(
        NS(
            approved=NS(source_key=key, path=path, profile=NS(copy=lambda deep: None)),
            verified=True,
            still_current=lambda: True,
        )
        for key, path in zip(keys, paths, strict=True)
    )
    return review, RestorePlan(11, finding, candidates)


def test_duplicate_candidate_paths_fail_before_any_workspace_mutation(tmp_path):
    path = tmp_path / "same.raw"
    review, plan = make_plan((path, path))
    window = Window((path, path), plan.finding.source_keys)
    authority = MainWindowReviewRestoreAuthority(window, review)
    with pytest.raises(ValueError, match="canonical path"):
        authority.prepare(plan)
    assert window.mutations == 0


def test_already_resident_restore_applies_complete_pair_and_line_without_timer(tmp_path):
    paths = (tmp_path / "a.raw", tmp_path / "b.raw")
    review, plan = make_plan(paths)
    keys = plan.finding.source_keys
    intent = NS(
        reference_key=keys[1],
        target_key=keys[0],
        channel="Gray",
        mode="Mask",
        gain=4,
        threshold=12,
        region="Active ROI",
    )
    plan = replace(
        plan,
        finding=NS(
            **{
                **vars(plan.finding),
                "difference_intent": intent,
                "roi_ref": (1, 1, 2, 2),
                "line_ref": (0, 0, 4, 3),
            }
        ),
    )
    window = Window(paths, keys)
    authority = MainWindowReviewRestoreAuthority(window, review)
    prepared = authority.prepare(plan)
    w04 = NS(status="applied", reason=None, partial_state=False)
    with patch(
        "pixelscope.ui.review_main_window_adapter.native_profile_signature", return_value="s"
    ), patch(
        "pixelscope.ui.review_main_window_adapter.restore_review_view_state", return_value=w04
    ), patch(
        "pixelscope.ui.review_main_window_adapter.display_gain_state",
        return_value=NS(set_gain=lambda _: None),
    ):
        report = authority.commit(prepared, plan)
    assert report.status == "applied", report
    pair = window.difference_panel.selected_documents()
    assert pair is not None
    assert tuple(d.document_id for d in pair) == ("doc-1", "doc-0")
    assert window.difference_panel.mode.currentText() == "Mask"
    assert window.difference_panel.channel.currentText() == "Gray"
    assert window.difference_panel.region.currentText() == "Active ROI"
    assert window.difference_panel.gain.value() == 4
    assert window.difference_panel.threshold.value() == 12
    assert (
        window._shared_line.x1,
        window._shared_line.y1,
        window._shared_line.x2,
        window._shared_line.y2,
    ) == (0, 0, 4, 3)
    window.difference_panel.calculate_difference.assert_not_called()
    window.multi_compare_view.begin_review_restore.assert_called_once_with(11)
    window.sync_action.setChecked.assert_called_once_with(False)
    window._update_action_states.assert_called_once_with()


def test_new_foreground_load_is_pending_until_owner_terminal(tmp_path):
    paths = (tmp_path / "a.raw", tmp_path / "b.raw")
    review, plan = make_plan(paths)
    window = Window(paths, plan.finding.source_keys)
    window._force_pending = True
    authority = MainWindowReviewRestoreAuthority(window, review)
    prepared = authority.prepare(plan)
    w04 = NS(status="applied", reason=None, partial_state=False)
    with patch(
        "pixelscope.ui.review_main_window_adapter.native_profile_signature", return_value="s"
    ), patch(
        "pixelscope.ui.review_main_window_adapter.restore_review_view_state", return_value=w04
    ), patch(
        "pixelscope.ui.review_main_window_adapter.display_gain_state",
        return_value=NS(set_gain=lambda _: None),
    ):
        first = authority.commit(prepared, plan)
        assert first.status == "pending"
        for doc in window.sources:
            doc.source = object()
            doc.loading_state = "ready"
        second = authority.retry(plan)
    assert second.status == "applied"


def test_finding_capture_refuses_roi_page_primary_and_w04_revisions():
    fixed = CaptureGuiFence(
        finding_id="f",
        source_ids=("a", "b"),
        selection_ids=("a", "b"),
        generations=(1, 2),
        page_start=0,
        current_index=0,
        focus_document_id="a",
        primary_id="a",
        active_document_id="b",
        roi=(0, 0, 2, 2),
        line=(0, 0, 4, 3),
        w04="saved",
        pair_ids=("a", "b"),
        difference_controls=("Gray", "Mask", 3, 12, "Active ROI"),
        display_gain=1.0,
        w02_presented="token",
        w02_current="token",
    )
    for changes in (
        {"roi": (1, 1, 2, 2)},
        {"selection_ids": ("b", "a")},
        {"primary_id": "b"},
        {"w04": "new zoom"},
        {"w02_current": None},
    ):
        with pytest.raises(ReviewValidationError, match="context changed"):
            assert_same_capture_context(fixed, replace(fixed, **changes))


def test_late_gui_capture_callback_does_not_persist_changed_roi():
    fence = CaptureGuiFence(
        finding_id="id",
        source_ids=("a",),
        selection_ids=("a",),
        generations=(1,),
        page_start=0,
        current_index=0,
        focus_document_id="a",
        primary_id="a",
        active_document_id="a",
        roi=(0, 0, 2, 2),
        line=None,
        w04="old",
        pair_ids=(),
        difference_controls=(),
        display_gain=1.0,
        w02_presented=None,
        w02_current=None,
    )
    finding = NS(id="id")
    binding = NS()
    stage = StagedFinding(finding, (binding,))
    owner = object.__new__(NamedReviewCoordinator)
    owner._closed = False
    owner._capture_epoch = 5
    owner._capture_task_id = "task"
    owner._capture_stage = stage
    owner._capture_fence = fence
    owner._window_ref = lambda: NS(_closing=False)
    owner.library = NS(add=MagicMock())
    messages = []
    owner._error = messages.append
    attested = AttestedFinding(finding, (), (binding,))
    with patch(
        "pixelscope.ui.review_window_integration.capture_gui_fence",
        return_value=replace(fence, roi=(1, 1, 2, 2)),
    ):
        owner._capture_succeeded("task", None, 5, attested)
    owner.library.add.assert_not_called()
    assert messages and "context changed" in messages[0]


def test_unsupported_native_channel_preflight_has_zero_mutation(tmp_path):
    paths = (tmp_path / "a.raw", tmp_path / "b.raw")
    review, plan = make_plan(paths)
    plan = replace(plan, finding=NS(**{**vars(plan.finding), "channel": "R"}))
    window = Window(paths, plan.finding.source_keys)
    authority = MainWindowReviewRestoreAuthority(window, review)
    with pytest.raises(ValueError, match="native channel"):
        authority.prepare(plan)
    assert window.mutations == 0


def test_line_rejection_after_commit_never_claims_applied(tmp_path):
    paths = (tmp_path / "a.raw", tmp_path / "b.raw")
    review, plan = make_plan(paths)
    plan = replace(
        plan,
        finding=NS(**{**vars(plan.finding), "line_ref": (0, 0, 4, 3)}),
    )
    window = Window(paths, plan.finding.source_keys)
    window._shared_line_changed = lambda _line: None
    authority = MainWindowReviewRestoreAuthority(window, review)
    prepared = authority.prepare(plan)
    with patch(
        "pixelscope.ui.review_main_window_adapter.native_profile_signature",
        return_value="s",
    ), patch(
        "pixelscope.ui.review_main_window_adapter.restore_review_view_state",
        return_value=NS(status="applied", reason=None, partial_state=False),
    ), patch(
        "pixelscope.ui.review_main_window_adapter.display_gain_state",
        return_value=NS(set_gain=lambda _: None),
    ):
        report = authority.commit(prepared, plan)
    assert report.status == "unavailable"
    assert report.partial_state
    assert "Line" in report.reason
