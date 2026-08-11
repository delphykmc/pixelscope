from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QSettings

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import COMPARISON_PAGE_SIZE, MainWindow
from pixelscope.core.comparison_set import (
    ComparisonSet,
    ComparisonSetError,
    ComparisonSetSource,
)
from pixelscope.core.image_document import ImageDocument
from pixelscope.io.raw_profile import RawProfile


def _production_window(qtbot: object) -> MainWindow:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    return window


def _ready_document(path: Path, value: int) -> ImageDocument:
    path.write_bytes(b"registered-test-source")
    return ImageDocument.from_array(
        np.full((4, 4), value, dtype=np.uint8),
        path.name,
        source_path=path,
    )


def _pending_document(path: Path) -> ImageDocument:
    path.write_bytes(b"pending-test-source")
    return ImageDocument.pending_document(path)


def _raw_profile() -> RawProfile:
    return RawProfile(
        name="gray10",
        width=4,
        height=4,
        stride_bytes=8,
        bit_depth=10,
        channel_layout="GRAY",
        black_level=64,
        white_level=1023,
    )


def _register(window: MainWindow, documents: list[ImageDocument]) -> None:
    for document in documents:
        window.add_document(document, select=False)


def test_save_uses_logical_selected_not_temporary_pick_set(
    qtbot: object,
    tmp_path: Path,
) -> None:
    QSettings().clear()
    documents = [
        _ready_document(tmp_path / f"image{i}.png", i) for i in range(3)
    ]
    window = _production_window(qtbot)
    _register(window, documents)
    window._select_document_ids([document.document_id for document in documents])
    review = window.review_selection_controller
    review.state.enter([document.document_id for document in documents])
    review.state.set_picked(documents[1].document_id, True)

    saved = window.comparison_set_controller.save_to_path(tmp_path / "set.pixelscope")

    assert [Path(source.path).name for source in saved.sources] == [
        "image0.png",
        "image1.png",
        "image2.png",
    ]
    assert review.active
    assert review.picked_ids == {documents[1].document_id}
    window.close()


def test_keep_selection_result_is_the_saved_comparison_set(
    qtbot: object,
    tmp_path: Path,
) -> None:
    QSettings().clear()
    documents = [
        _ready_document(tmp_path / f"image{i}.png", i) for i in range(4)
    ]
    window = _production_window(qtbot)
    _register(window, documents)
    window._select_document_ids([document.document_id for document in documents])
    review = window.review_selection_controller
    review.state.enter([document.document_id for document in documents])
    review.state.set_picked(documents[1].document_id, True)
    review.state.set_picked(documents[3].document_id, True)
    assert review.keep_picked()

    saved = window.comparison_set_controller.save_to_path(
        tmp_path / "curated.pixelscope"
    )

    assert [Path(source.path).name for source in saved.sources] == [
        "image1.png",
        "image3.png",
    ]
    window.close()


def test_large_pending_save_does_not_acquire_loading_or_residency_authority(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    QSettings().clear()
    documents = [
        _pending_document(tmp_path / f"image{i:02d}.png") for i in range(20)
    ]
    window = _production_window(qtbot)
    _register(window, documents)
    load_requests: list[str] = []
    monkeypatch.setattr(
        window,
        "_ensure_loaded",
        lambda document: load_requests.append(document.document_id),
    )
    window._select_document_ids([document.document_id for document in documents])
    load_requests.clear()
    review = window.review_selection_controller
    review.state.enter([document.document_id for document in documents])
    review.state.set_picked(documents[8].document_id, True)
    before_protected = set(window._residency_protected_document_ids())
    before_sources = [document.source for document in documents]

    saved = window.comparison_set_controller.save_to_path(
        tmp_path / "large-save.pixelscope"
    )

    assert len(saved.sources) == 20
    assert load_requests == []
    assert [document.source for document in documents] == before_sources
    assert set(window._residency_protected_document_ids()) == before_protected
    assert review.active
    assert review.picked_ids == {documents[8].document_id}
    window.close()


def test_open_restores_order_active_primary_layout_and_keeps_other_registered(
    qtbot: object,
    tmp_path: Path,
) -> None:
    QSettings().clear()
    documents = [
        _ready_document(tmp_path / f"image{i}.png", i) for i in range(4)
    ]
    extra = _ready_document(tmp_path / "extra.png", 9)
    window = _production_window(qtbot)
    _register(window, [*documents, extra])
    window._select_document_ids(
        [
            documents[2].document_id,
            documents[0].document_id,
            documents[1].document_id,
        ]
    )
    window.set_layout_mode("Multi View")
    window._set_focus_document(documents[0].document_id)
    window._set_active_document(documents[1])
    target = tmp_path / "set.pixelscope"
    window.comparison_set_controller.save_to_path(target)

    window._select_document_ids([extra.document_id])
    window.set_layout_mode("Single View")
    loaded, missing = window.comparison_set_controller.open_from_path(target)

    assert loaded == 3
    assert missing == ()
    assert [document.document_id for document in window.selected_documents] == [
        documents[2].document_id,
        documents[0].document_id,
        documents[1].document_id,
    ]
    assert extra.document_id in window.documents
    assert window._active_document_id == documents[1].document_id
    assert window._focus_document_id == documents[0].document_id
    assert window._layout_mode == "Multi View"
    window.close()


def test_open_derives_later_page_from_saved_active_before_restoring_primary(
    qtbot: object,
    tmp_path: Path,
) -> None:
    QSettings().clear()
    documents = [
        _ready_document(tmp_path / f"image{i:02d}.png", i) for i in range(15)
    ]
    window = _production_window(qtbot)
    _register(window, documents)
    artifact = ComparisonSet(
        sources=tuple(
            ComparisonSetSource(str(document.source_path)) for document in documents
        ),
        active_path=str(documents[8].source_path),
        primary_path=str(documents[10].source_path),
        layout_mode="Multi View",
    )
    target = tmp_path / "later-page.pixelscope"
    window.comparison_set_controller.repository.save(target, artifact)

    loaded, missing = window.comparison_set_controller.open_from_path(target)

    assert loaded == 15
    assert missing == ()
    assert window._page_start == 6
    assert [
        document.document_id for document in window.current_comparison_documents()
    ] == [document.document_id for document in documents[6:12]]
    assert window._active_document_id == documents[8].document_id
    assert window._focus_document_id == documents[10].document_id
    window.close()


def test_open_partial_missing_loads_valid_subset_and_invalidates_curation(
    qtbot: object,
    tmp_path: Path,
) -> None:
    QSettings().clear()
    first = _ready_document(tmp_path / "first.png", 1)
    second = _ready_document(tmp_path / "second.png", 2)
    window = _production_window(qtbot)
    _register(window, [first, second])
    window._select_document_ids([first.document_id, second.document_id])
    review = window.review_selection_controller
    review.state.enter([first.document_id, second.document_id])
    review.state.set_picked(first.document_id, True)
    artifact = ComparisonSet(
        sources=(
            ComparisonSetSource(str(second.source_path)),
            ComparisonSetSource(str(tmp_path / "missing.png")),
        )
    )
    target = tmp_path / "partial.pixelscope"
    window.comparison_set_controller.repository.save(target, artifact)

    loaded, missing = window.comparison_set_controller.open_from_path(target)

    assert loaded == 1
    assert missing == ((tmp_path / "missing.png").resolve(),)
    assert [document.document_id for document in window.selected_documents] == [
        second.document_id
    ]
    assert not review.active
    window.close()


def _semantic_invalid_payload(case: str, tmp_path: Path) -> dict[str, object]:
    source = str((tmp_path / "saved.png").resolve())
    payload: dict[str, object] = {
        "kind": "pixelscope-comparison-set",
        "schema_version": 1,
        "sources": [{"path": source}],
        "layout_mode": "Multi View",
    }
    if case == "future-schema":
        payload["schema_version"] = 2
    elif case == "wrong-kind":
        payload["kind"] = "other"
    elif case == "invalid-layout":
        payload["layout_mode"] = "Grid"
    elif case == "blank-active":
        payload["active_path"] = "   "
    elif case == "invalid-raw-profile":
        payload["sources"] = [{"path": source, "raw_profile": {"name": "bad"}}]
    elif case == "relative-source":
        payload["sources"] = [{"path": "relative.png"}]
    else:
        raise AssertionError(f"unknown invalid payload case: {case}")
    return payload


@pytest.mark.parametrize(
    "case",
    [
        "future-schema",
        "wrong-kind",
        "invalid-layout",
        "blank-active",
        "invalid-raw-profile",
        "relative-source",
    ],
)
def test_semantically_invalid_open_is_transactional_and_preserves_curation(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    QSettings().clear()
    first = _ready_document(tmp_path / "current-a.png", 1)
    second = _ready_document(tmp_path / "current-b.png", 2)
    window = _production_window(qtbot)
    _register(window, [first, second])
    window._select_document_ids([first.document_id, second.document_id])
    window.set_layout_mode("Multi View")
    window._set_focus_document(first.document_id)
    window._set_active_document(second)
    review = window.review_selection_controller
    review.state.enter([first.document_id, second.document_id])
    review.state.set_picked(first.document_id, True)
    before_registered = set(window.documents)
    before_selected = [document.document_id for document in window.selected_documents]
    before_active = window._active_document_id
    before_primary = window._focus_document_id
    before_review = (
        review.state.active,
        review.state.baseline_selected_ids,
        set(review.state.picked_ids),
    )
    target = tmp_path / f"invalid-{case}.pixelscope"
    target.write_text(
        json.dumps(_semantic_invalid_payload(case, tmp_path)),
        encoding="utf-8",
    )
    registration_calls = 0
    load_calls = 0

    def unexpected_register(*_args: object, **_kwargs: object) -> None:
        nonlocal registration_calls
        registration_calls += 1
        return None

    def unexpected_load(*_args: object, **_kwargs: object) -> None:
        nonlocal load_calls
        load_calls += 1
        return None

    monkeypatch.setattr(window, "_register_input", unexpected_register)
    monkeypatch.setattr(window, "_ensure_loaded", unexpected_load)

    with pytest.raises(ComparisonSetError):
        window.comparison_set_controller.open_from_path(target)

    assert set(window.documents) == before_registered
    assert [document.document_id for document in window.selected_documents] == before_selected
    assert window._active_document_id == before_active
    assert window._focus_document_id == before_primary
    assert (
        review.state.active,
        review.state.baseline_selected_ids,
        set(review.state.picked_ids),
    ) == before_review
    assert registration_calls == 0
    assert load_calls == 0
    window.close()


def test_corrupt_or_zero_loadable_set_leaves_workspace_unchanged(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    QSettings().clear()
    document = _ready_document(tmp_path / "current.png", 1)
    window = _production_window(qtbot)
    _register(window, [document])
    window._select_document_ids([document.document_id])
    before_registered = set(window.documents)
    before_selected = [item.document_id for item in window.selected_documents]

    broken = tmp_path / "broken.pixelscope"
    broken.write_text("{bad", encoding="utf-8")
    with pytest.raises(ComparisonSetError):
        window.comparison_set_controller.open_from_path(broken)
    assert set(window.documents) == before_registered
    assert [item.document_id for item in window.selected_documents] == before_selected

    unavailable = tmp_path / "unavailable.pixelscope"
    window.comparison_set_controller.repository.save(
        unavailable,
        ComparisonSet(
            sources=(ComparisonSetSource(str(tmp_path / "gone.png")),)
        ),
    )
    monkeypatch.setattr(
        "pixelscope.ui.comparison_set.QMessageBox.warning",
        lambda *args: None,
    )
    loaded, _missing = window.comparison_set_controller.open_from_path(unavailable)
    assert loaded == 0
    assert set(window.documents) == before_registered
    assert [item.document_id for item in window.selected_documents] == before_selected
    window.close()


def test_large_open_keeps_foreground_work_bounded_to_active_comparison_page(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    QSettings().clear()
    documents = [
        _pending_document(tmp_path / f"image{i:02d}.png") for i in range(50)
    ]
    window = _production_window(qtbot)
    _register(window, documents)
    target = tmp_path / "large.pixelscope"
    active_index = 49
    artifact = ComparisonSet(
        sources=tuple(
            ComparisonSetSource(str(document.source_path)) for document in documents
        ),
        active_path=str(documents[active_index].source_path),
        layout_mode="Multi View",
    )
    window.comparison_set_controller.repository.save(target, artifact)
    requested: list[str] = []
    monkeypatch.setattr(
        window,
        "_ensure_loaded",
        lambda document: requested.append(document.document_id),
    )

    loaded, missing = window.comparison_set_controller.open_from_path(target)

    assert loaded == 50
    assert missing == ()
    assert window._page_start == 48
    assert [
        document.document_id for document in window.current_comparison_documents()
    ] == [
        documents[48].document_id,
        documents[49].document_id,
    ]
    assert set(requested) == {
        documents[48].document_id,
        documents[49].document_id,
    }
    assert len(requested) <= COMPARISON_PAGE_SIZE
    assert not set(documents[:48]).intersection(
        window._residency_protected_document_ids()
    )
    window.close()


def test_saved_resolved_raw_profile_is_restored_without_resolution_dialog(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    QSettings().clear()
    raw_path = tmp_path / "image.raw"
    raw_path.write_bytes(b"\x00" * 32)
    window = _production_window(qtbot)
    profile = _raw_profile()
    artifact = ComparisonSet(
        sources=(ComparisonSetSource(str(raw_path), profile.dict()),),
        layout_mode="Single View",
    )
    target = tmp_path / "raw.pixelscope"
    window.comparison_set_controller.repository.save(target, artifact)
    monkeypatch.setattr(window, "_ensure_loaded", lambda _document: None)
    prompt_count = 0

    def unexpected_prompt(*_args: object, **_kwargs: object) -> None:
        nonlocal prompt_count
        prompt_count += 1
        return None

    monkeypatch.setattr(window, "_confirm_raw_profile", unexpected_prompt)

    loaded, missing = window.comparison_set_controller.open_from_path(target)

    assert loaded == 1
    assert missing == ()
    selected = window.selected_documents[0]
    assert window._raw_profiles[selected.document_id] == profile
    assert selected.raw_profile == profile
    assert prompt_count == 0
    window.close()


def test_unresolved_raw_remains_lazy_until_existing_foreground_resolution_path(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    QSettings().clear()
    raw_path = tmp_path / "unresolved.raw"
    raw_path.write_bytes(b"\x00" * 32)
    window = _production_window(qtbot)
    target = tmp_path / "unresolved.pixelscope"
    window.comparison_set_controller.repository.save(
        target,
        ComparisonSet(sources=(ComparisonSetSource(str(raw_path)),)),
    )
    foreground_ids: list[str] = []
    monkeypatch.setattr(
        window,
        "_ensure_loaded",
        lambda document: foreground_ids.append(document.document_id),
    )

    loaded, missing = window.comparison_set_controller.open_from_path(target)

    assert loaded == 1
    assert missing == ()
    selected = window.selected_documents[0]
    assert selected.document_id not in window._raw_profiles
    assert foreground_ids == [selected.document_id]
    window.close()
