from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMessageBox

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.comparison_set import (
    ComparisonSetError,
    Session,
    SessionDifference,
    SessionSource,
)
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineSelection
from pixelscope.core.roi import RoiBounds
from pixelscope.io.comparison_set_repository import ComparisonSetRepository


def _production_window(qtbot: object) -> MainWindow:
    QSettings().clear()
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    return window


def _ready_document(path: Path, value: int) -> ImageDocument:
    path.write_bytes(b"session-review-source")
    return ImageDocument.from_array(
        np.full((4, 4), value, dtype=np.uint8),
        path.name,
        source_path=path,
    )


def _workspace_snapshot(window: MainWindow) -> tuple[object, ...]:
    review = window.review_selection_controller
    return (
        tuple(window.documents),
        tuple(document.document_id for document in window.selected_documents),
        window._active_document_id,
        window._focus_document_id,
        review.active,
        frozenset(review.picked_ids),
    )


def _prepare_existing_workspace(window: MainWindow, tmp_path: Path) -> tuple[ImageDocument, ImageDocument]:
    a = _ready_document(tmp_path / "existing-a.png", 1)
    b = _ready_document(tmp_path / "existing-b.png", 2)
    window.add_document(a, select=False)
    window.add_document(b, select=False)
    window._select_document_ids([a.document_id, b.document_id])
    window.set_layout_mode("Multi View")
    window._set_focus_document(a.document_id)
    window._set_active_document(b)
    review = window.review_selection_controller
    review.state.enter([a.document_id, b.document_id])
    review.state.set_picked(a.document_id, True)
    return a, b


def test_session_open_reads_artifact_once_and_uses_same_active_payload(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window = _production_window(qtbot)
    a = _ready_document(tmp_path / "a.png", 1)
    b = _ready_document(tmp_path / "b.png", 2)
    window.add_document(a, select=False)
    window.add_document(b, select=False)
    window._select_document_ids([a.document_id, b.document_id])
    window._set_active_document(b)
    target = tmp_path / "single-read.pixelscope"
    window.session_controller.save_to_path(target)

    class SingleReadRepository(ComparisonSetRepository):
        def __init__(self) -> None:
            self.load_count = 0

        def load(self, path: str | Path) -> Session:
            self.load_count += 1
            if self.load_count > 1:
                raise AssertionError("Session artifact was read more than once")
            return super().load(path)

    repository = SingleReadRepository()
    window.session_controller.repository = repository

    loaded, missing = window.session_controller.open_from_path(target)

    assert loaded == 2
    assert missing == ()
    assert repository.load_count == 1
    assert window._active_document_id == b.document_id
    window.close()


@pytest.mark.parametrize(
    "case",
    [
        "roi-string",
        "line-fraction",
        "gain-fraction",
        "gain-bool",
        "threshold-nan",
        "invalid-channel",
    ],
)
def test_semantic_invalid_session_is_rejected_before_workspace_mutation(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    window = _production_window(qtbot)
    _prepare_existing_workspace(window, tmp_path)
    before = _workspace_snapshot(window)

    incoming_a = tmp_path / "incoming-a.png"
    incoming_b = tmp_path / "incoming-b.png"
    incoming_a.write_bytes(b"incoming-a")
    incoming_b.write_bytes(b"incoming-b")
    payload: dict[str, object] = {
        "kind": "pixelscope-session",
        "schema_version": 1,
        "registered_sources": [
            {"path": str(incoming_a.resolve())},
            {"path": str(incoming_b.resolve())},
        ],
        "selected_paths": [str(incoming_a.resolve()), str(incoming_b.resolve())],
        "active_path": str(incoming_b.resolve()),
        "primary_path": str(incoming_a.resolve()),
        "layout_mode": "Multi View",
        "display_gain": 1.0,
        "split_channels": False,
        "roi": {"x": 0, "y": 0, "width": 2, "height": 2},
        "line": {"x1": 0, "y1": 0, "x2": 2, "y2": 0},
        "difference": {
            "image_a_path": str(incoming_a.resolve()),
            "image_b_path": str(incoming_b.resolve()),
            "channel": "All",
            "mode": "Absolute",
            "threshold": 10.0,
            "gain": 1,
            "region": "Full image",
        },
    }
    malformed = copy.deepcopy(payload)
    assert isinstance(malformed["roi"], dict)
    assert isinstance(malformed["line"], dict)
    assert isinstance(malformed["difference"], dict)
    if case == "roi-string":
        malformed["roi"]["x"] = "1"
    elif case == "line-fraction":
        malformed["line"]["x2"] = 1.5
    elif case == "gain-fraction":
        malformed["difference"]["gain"] = 1.5
    elif case == "gain-bool":
        malformed["difference"]["gain"] = True
    elif case == "threshold-nan":
        malformed["difference"]["threshold"] = float("nan")
    else:
        malformed["difference"]["channel"] = "Y"

    target = tmp_path / f"invalid-{case}.pixelscope"
    target.write_text(json.dumps(malformed), encoding="utf-8")
    registration_calls: list[object] = []
    load_calls: list[object] = []
    original_register = window._register_input
    original_ensure = window._ensure_loaded

    def observed_register(*args: object, **kwargs: object) -> object:
        registration_calls.append(args)
        return original_register(*args, **kwargs)

    def observed_ensure(document: object) -> None:
        load_calls.append(document)
        original_ensure(document)

    monkeypatch.setattr(window, "_register_input", observed_register)
    monkeypatch.setattr(window, "_ensure_loaded", observed_ensure)

    with pytest.raises(ComparisonSetError):
        window.session_controller.open_from_path(target)

    assert registration_calls == []
    assert load_calls == []
    assert _workspace_snapshot(window) == before
    window.close()


def test_zero_successful_registration_leaves_existing_workspace_and_picks_unchanged(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = _production_window(qtbot)
    _prepare_existing_workspace(window, tmp_path)
    before = _workspace_snapshot(window)

    incoming = tmp_path / "incoming.png"
    incoming.write_bytes(b"incoming")
    session = Session(
        registered_sources=(SessionSource(str(incoming)),),
        selected_paths=(str(incoming),),
        active_path=str(incoming),
    )
    target = tmp_path / "registration-failure.pixelscope"
    window.session_controller.repository.save(target, session)
    monkeypatch.setattr(window, "_register_input", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *_args, **_kwargs: None)

    loaded, missing = window.session_controller.open_from_path(target)

    assert loaded == 0
    assert missing == (incoming.resolve(),)
    assert _workspace_snapshot(window) == before
    window.close()


def test_off_page_difference_pair_is_the_only_additional_foreground_dependency(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = [tmp_path / f"image-{index:02d}.png" for index in range(12)]
    for path in paths:
        path.write_bytes(b"pending-session-source")
    session = Session(
        registered_sources=tuple(SessionSource(str(path)) for path in paths),
        selected_paths=tuple(str(path) for path in paths),
        active_path=str(paths[0]),
        layout_mode="Multi View",
        difference=SessionDifference(
            image_a_path=str(paths[10]),
            image_b_path=str(paths[11]),
            channel="Gray",
        ),
    )
    target = tmp_path / "off-page-difference.pixelscope"

    window = _production_window(qtbot)
    window.session_controller.repository.save(target, session)
    requested: list[str] = []

    def make_ready(document: ImageDocument) -> None:
        requested.append(document.document_id)
        document.source = np.full((4, 4), 1, dtype=np.uint8)
        document.preview = np.full((4, 4), 1, dtype=np.uint8)
        document.channel_layout = "GRAY"
        document.bit_depth = 8
        document.loading_state = "ready"

    monkeypatch.setattr(window, "_ensure_loaded", make_ready)
    calculations: list[tuple[str, str]] = []
    monkeypatch.setattr(
        window.difference_panel,
        "calculate_difference",
        lambda: calculations.append(
            (
                str(window.difference_panel.a_selector.currentData()),
                str(window.difference_panel.b_selector.currentData()),
            )
        ),
    )

    loaded, missing = window.session_controller.open_from_path(target)

    assert loaded == 12
    assert missing == ()
    selected = window.selected_documents
    expected_page = {document.document_id for document in selected[:6]}
    expected_pair = (selected[10].document_id, selected[11].document_id)
    assert set(requested) == expected_page | set(expected_pair)
    assert len(requested) == 8
    qtbot.waitUntil(lambda: bool(calculations))  # type: ignore[attr-defined]
    assert calculations[-1] == expected_pair
    assert window._difference_source_ids == expected_pair
    window.close()


def test_pair_incompatible_saved_difference_channel_is_not_silently_substituted(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = _production_window(qtbot)
    a = _ready_document(tmp_path / "gray-a.png", 1)
    b = _ready_document(tmp_path / "gray-b.png", 2)
    window.add_document(a, select=False)
    window.add_document(b, select=False)
    window._select_document_ids([a.document_id, b.document_id])
    session = Session(
        registered_sources=(SessionSource(str(a.source_path)), SessionSource(str(b.source_path))),
        selected_paths=(str(a.source_path), str(b.source_path)),
        active_path=str(a.source_path),
        difference=SessionDifference(
            image_a_path=str(a.source_path),
            image_b_path=str(b.source_path),
            channel="Mosaic",
        ),
    )
    target = tmp_path / "incompatible-channel.pixelscope"
    window.session_controller.repository.save(target, session)
    calculations: list[object] = []
    monkeypatch.setattr(
        window.difference_panel,
        "calculate_difference",
        lambda: calculations.append(object()),
    )

    loaded, missing = window.session_controller.open_from_path(target)

    assert loaded == 2
    assert missing == ()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.session_controller._pending_difference is None
    )
    assert calculations == []
    assert window._difference_source_ids is None
    assert "not available" in window.statusBar().currentMessage()
    window.close()
